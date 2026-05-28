# =============================================================================
# ml/forecasting/arima_forecaster.py
# Dashboard 360° Novec — Prédictions ARIMA (Étape B)
# Complément à ProphetForecaster pour séries courtes / stationnaires
# =============================================================================

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

try:
    import pmdarima as pm
    from pmdarima import auto_arima
except ImportError as exc:
    raise ImportError("pmdarima manquant — pip install pmdarima") from exc

from sqlalchemy.engine import Engine
from sqlalchemy import text

try:
    from data_simulation.config import get_db_engine
except ImportError:
    get_db_engine = None

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")

# =============================================================================
# CONSTANTES
# =============================================================================

SILVER_TABLES: dict[str, str] = {
    "infra":        "Silver.silver_infrastructure",
    "itsm":         "Silver.silver_itsm",
    "cybersec":     "Silver.silver_cybersecurity",
    "apps":         "Silver.silver_applications",
    "itam":         "Silver.silver_itam",
    "parc_auto":    "Silver.silver_parc_auto",
    "maintenance":  "Silver.silver_maintenance",
    "gouvernance":  "Silver.silver_gouvernance",
}

GOLD_FORECAST_TABLES: dict[str, str] = {
    "infra":        "Gold.forecast_infra",
    "itsm":         "Gold.forecast_itsm",
    "cybersec":     "Gold.forecast_cybersec",
    "apps":         "Gold.forecast_apps",
    "itam":         "Gold.forecast_itam",
    "parc_auto":    "Gold.forecast_parc_auto",
    "maintenance":  "Gold.forecast_maintenance",
    "gouvernance":  "Gold.forecast_gouvernance",
}


GROUP_KEYS: dict[str, Optional[str]] = {
    "infra":        "ServerName",
    "itsm":         None,
    "cybersec":     None,
    "apps":         "Application_Name",
    "itam":         None,
    "parc_auto":    None,
    "maintenance":  None,
    "gouvernance":  "Departement",
}

CSV_FALLBACK_DIR = Path("silver_dataset")

# =============================================================================
# CONFIGURATION DES KPIs ARIMA
# =============================================================================

@dataclass
class ARIMAConfig:
    domain:      str
    kpi:         str
    horizon:     int
    freq:        str
    group_col:   Optional[str] = None
    is_pct:      bool = False
    direction:   str = "above"
    rouge_thr:   Optional[float] = None
    ambre_thr:   Optional[float] = None


ARIMA_CONFIGS: list[ARIMAConfig] = [
    # ITAM — mensuel
    ARIMAConfig("itam",        "TCO_Moyen_Par_Poste_MAD", horizon=3,  freq="MS", is_pct=False),
    ARIMAConfig("itam",        "Conformite_Licences_Pct", horizon=6,  freq="MS", is_pct=True,
                direction="below", rouge_thr=75, ambre_thr=85),

    # MAINTENANCE — mensuel
    ARIMAConfig("maintenance", "Ratio_Preventif_Pct",     horizon=3,  freq="MS", is_pct=True,
                direction="below", rouge_thr=60, ambre_thr=70),
    ARIMAConfig("maintenance", "Total_Ruptures_Stock",    horizon=3,  freq="MS", is_pct=False,
                direction="above", rouge_thr=4, ambre_thr=2),

    # PARC AUTO — mensuel agrégé
    ARIMAConfig("parc_auto",   "Taux_Sinistralite_Pct",   horizon=1,  freq="MS", is_pct=True,
                direction="above", rouge_thr=5, ambre_thr=3),

    # GOUVERNANCE — mensuel par département
    ARIMAConfig("gouvernance", "Cout_IT_Par_Employe_MAD", horizon=6,  freq="MS", is_pct=False,
                group_col="Departement"),
]


# =============================================================================
# DDL DES TABLES GOLD (forecast_maintenance, forecast_parc_auto)
# Colonne GroupKey incluse dès la création
# =============================================================================

_FORECAST_TABLE_DDL = """
IF OBJECT_ID('{schema_table}', 'U') IS NULL
BEGIN
    CREATE TABLE {schema_table} (
        Id               INT IDENTITY(1,1) PRIMARY KEY,
        KPI              NVARCHAR(100)   NOT NULL,
        DS               DATE            NOT NULL,
        Yhat             FLOAT,
        Yhat_Lower       FLOAT,
        Yhat_Upper       FLOAT,
        Trend            FLOAT,
        Trend_Lower      FLOAT,
        Trend_Upper      FLOAT,
        Is_Forecast      BIT             NOT NULL DEFAULT 1,
        Statut_RAG       NVARCHAR(10),
        Risk_Score       FLOAT,
        Source_Modele    NVARCHAR(20)    DEFAULT 'ARIMA',
        Date_Calcul      DATETIME2       DEFAULT GETUTCDATE(),
        CONSTRAINT {uq_name} UNIQUE (KPI, DS)
    );
END
"""

# DDL pour ajouter GroupKey si la table existe déjà sans cette colonne
# (migration safe — IF NOT EXISTS via sys.columns)
_ADD_GROUPKEY_DDL = """
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('{schema_table}')
    AND name = 'GroupKey'
)
BEGIN
    ALTER TABLE {schema_table} ADD GroupKey NVARCHAR(100) NULL;
END
"""

_EXTRA_TABLES_CONFIG = [
    {
        "table":   "Gold.forecast_maintenance",
        "uq_name": "UQ_FM_KPI_DS",
    },
    {
        "table":   "Gold.forecast_parc_auto",
        "uq_name": "UQ_FPA_KPI_DS",
    },
]

# Tables partagées où GroupKey doit aussi être présent
_SHARED_TABLES_NEEDING_GROUPKEY = [
    "Gold.forecast_gouvernance",
    "Gold.forecast_itam",
]


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def _ensure_gold_tables(engine: Engine) -> None:
    """
    Crée les tables Gold dédiées ARIMA si elles n'existent pas,
    et ajoute la colonne GroupKey sur toutes les tables concernées
    (création + tables partagées existantes).
    """
    with engine.begin() as conn:
        # 1. Création des tables ARIMA-only (avec UNIQUE déjà défini)
        for cfg in _EXTRA_TABLES_CONFIG:
            ddl = _FORECAST_TABLE_DDL.format(
                schema_table=cfg["table"],
                uq_name=cfg["uq_name"],
            )
            try:
                conn.execute(text(ddl))
                logger.info("[ARIMA] Table %s vérifiée/créée", cfg["table"])
            except Exception as exc:
                logger.warning("[ARIMA] Impossible de créer %s : %s", cfg["table"], exc)

        # 2. Ajout colonne GroupKey (migration idempotente) sur toutes les tables concernées
        all_tables_needing_groupkey = (
            [c["table"] for c in _EXTRA_TABLES_CONFIG]
            + _SHARED_TABLES_NEEDING_GROUPKEY
        )
        for table in all_tables_needing_groupkey:
            ddl = _ADD_GROUPKEY_DDL.format(schema_table=table)
            try:
                conn.execute(text(ddl))
                logger.info("[ARIMA] GroupKey vérifié/ajouté sur %s", table)
            except Exception as exc:
                logger.warning("[ARIMA] Impossible d'ajouter GroupKey sur %s : %s", table, exc)


def _compute_risk_score(
    yhat: float,
    cfg: ARIMAConfig,
) -> tuple[float, str]:
    """Calcule Risk_Score [0,1] et Statut_RAG pour une prédiction."""
    if cfg.rouge_thr is None or cfg.ambre_thr is None:
        return 0.10, "VERT"

    if cfg.direction == "above":
        if yhat >= cfg.rouge_thr:
            excess = min((yhat - cfg.rouge_thr) / max(cfg.rouge_thr * 0.10, 1), 1.0)
            return round(min(0.80 + excess * 0.20, 1.0), 4), "ROUGE"
        elif yhat >= cfg.ambre_thr:
            ratio = (yhat - cfg.ambre_thr) / max(cfg.rouge_thr - cfg.ambre_thr, 1e-9)
            return round(0.40 + ratio * 0.30, 4), "AMBRE"
        else:
            return round(min(yhat / max(cfg.ambre_thr, 1e-9) * 0.40, 0.39), 4), "VERT"

    else:  # "below"
        if yhat <= cfg.rouge_thr:
            excess = min((cfg.rouge_thr - yhat) / max(cfg.rouge_thr * 0.10, 1), 1.0)
            return round(min(0.80 + excess * 0.20, 1.0), 4), "ROUGE"
        elif yhat <= cfg.ambre_thr:
            ratio = (cfg.ambre_thr - yhat) / max(cfg.ambre_thr - cfg.rouge_thr, 1e-9)
            return round(0.40 + ratio * 0.30, 4), "AMBRE"
        else:
            ratio = max(0, cfg.ambre_thr - yhat) / max(cfg.ambre_thr, 1e-9)
            return round(ratio * 0.40, 4), "VERT"


def _delete_kpi_from_table(engine: Engine, gold_table: str, kpi: str) -> None:
    """
    Supprime les lignes existantes pour un KPI donné dans une table partagée.
    Utilisé avant INSERT pour éviter les violations de contrainte UNIQUE.
    """
    schema, table_name = gold_table.split(".")
    sql = f"DELETE FROM [{schema}].[{table_name}] WHERE KPI = :kpi"
    try:
        with engine.begin() as conn:
            result = conn.execute(text(sql), {"kpi": kpi})
            deleted = result.rowcount
            if deleted > 0:
                logger.info(
                    "[ARIMA] DELETE %d lignes (KPI=%s) dans %s avant re-insert",
                    deleted, kpi, gold_table
                )
    except Exception as exc:
        logger.warning("[ARIMA] DELETE KPI=%s dans %s KO : %s", kpi, gold_table, exc)


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class ARIMAForecaster:
    """
    Prédictions ARIMA pour les KPIs à séries courtes ou stationnaires.

    Stratégie d'écriture SQL :
    - forecast_parc_auto, forecast_maintenance → TRUNCATE puis INSERT
      (tables ARIMA-only, pas de risque de perte pour Prophet)
    - forecast_itam, forecast_gouvernance → DELETE par KPI puis INSERT
      (tables partagées avec Prophet, on ne touche qu'aux KPIs ARIMA)

    Usage :
        engine = get_db_engine()
        forecaster = ARIMAForecaster(engine)
        results = forecaster.run_all()
        forecaster.save_results(results)
    """

    def __init__(self, engine: Optional[Engine] = None):
        self.engine = engine
        self._results: dict[str, pd.DataFrame] = {}
        # Suivi des KPIs traités par table pour le DELETE ciblé
        self._kpis_by_table: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # CHARGEMENT DONNÉES SILVER
    # ------------------------------------------------------------------

    def _load_silver(self, domain_key: str) -> pd.DataFrame:
        table = SILVER_TABLES[domain_key]

        if self.engine is not None:
            try:
                df = pd.read_sql(f"SELECT * FROM {table}", self.engine)
                logger.info("[ARIMA] %s chargé (%d lignes)", table, len(df))
                return df
            except Exception as exc:
                logger.warning("[ARIMA] SQL KO (%s) → fallback CSV : %s", table, exc)

        csv_path = CSV_FALLBACK_DIR / f"{domain_key}_silver.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, parse_dates=["DateKey"])
            logger.info("[ARIMA] %s chargé depuis CSV (%d lignes)", csv_path, len(df))
            return df

        logger.error("[ARIMA] Aucune source pour %s", domain_key)
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # AJUSTEMENT AUTO-ARIMA
    # ------------------------------------------------------------------

    def _fit_forecast(
        self,
        series: pd.Series,
        horizon: int,
        freq: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        model = auto_arima(
            series,
            seasonal=False,
            information_criterion="aic",
            stepwise=True,
            suppress_warnings=True,
            error_action="ignore",
            max_p=4, max_q=4, max_d=2,
        )

        forecast, conf_int = model.predict(
            n_periods=horizon,
            return_conf_int=True,
            alpha=0.20,
        )

        return (
            np.array(forecast),
            np.array(conf_int[:, 0]),
            np.array(conf_int[:, 1]),
        )

    # ------------------------------------------------------------------
    # PRÉDICTION POUR UN KPI / GROUPE
    # ------------------------------------------------------------------

    def _forecast_series(
        self,
        df: pd.DataFrame,
        cfg: ARIMAConfig,
        group_value: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Génère les prédictions pour une série KPI.

        La colonne GroupKey est toujours présente dans le résultat
        (None si pas de groupement) pour cohérence avec le schéma Gold.
        """
        date_col = "DateKey" if "DateKey" in df.columns else df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)

        if group_value and cfg.group_col and cfg.group_col in df.columns:
            df = df[df[cfg.group_col] == group_value]

        if cfg.kpi not in df.columns:
            logger.warning("[ARIMA] KPI '%s' absent du domaine '%s'", cfg.kpi, cfg.domain)
            return pd.DataFrame()

        ts = df.set_index(date_col)[cfg.kpi].dropna()
        period_freq = "M" if cfg.freq == "MS" else cfg.freq
        ts.index = pd.DatetimeIndex(ts.index).to_period(period_freq).to_timestamp(how="start")
        ts = ts.groupby(ts.index).mean()

        if len(ts) < 4:
            logger.warning(
                "[ARIMA] %s/%s : série trop courte (%d pts) — ignoré",
                cfg.domain, cfg.kpi, len(ts)
            )
            return pd.DataFrame()

        now = datetime.utcnow()

        # --- Historique (Is_Forecast = 0) ---
        hist_records = []
        for ds, val in ts.items():
            risk_score, statut_rag = _compute_risk_score(val, cfg)
            hist_records.append({
                "KPI":           cfg.kpi,
                "DS":            ds.date(),
                "Yhat":          round(float(val), 4),
                "Yhat_Lower":    None,
                "Yhat_Upper":    None,
                "Trend":         None,
                "Trend_Lower":   None,
                "Trend_Upper":   None,
                "Is_Forecast":   0,
                "Statut_RAG":    statut_rag,
                "Risk_Score":    risk_score,
                "Source_Modele": "ARIMA",
                "Date_Calcul":   now,
                "GroupKey":      group_value,   # None si pas de groupement
            })

        # --- Prédictions futures (Is_Forecast = 1) ---
        try:
            yhat, lower, upper = self._fit_forecast(ts, cfg.horizon, cfg.freq)
        except Exception as exc:
            logger.error(
                "[ARIMA] Fit échoué %s/%s/%s : %s",
                cfg.domain, cfg.kpi, group_value, exc
            )
            return pd.DataFrame(hist_records)

        last_date = ts.index[-1]
        future_dates = pd.date_range(
            start=last_date + pd.DateOffset(months=1),
            periods=cfg.horizon,
            freq=cfg.freq,
        )

        if cfg.is_pct:
            yhat  = np.clip(yhat,  0, 100)
            lower = np.clip(lower, 0, 100)
            upper = np.clip(upper, 0, 100)

        fc_records = []
        for i, ds in enumerate(future_dates):
            risk_score, statut_rag = _compute_risk_score(float(yhat[i]), cfg)
            fc_records.append({
                "KPI":           cfg.kpi,
                "DS":            ds.date(),
                "Yhat":          round(float(yhat[i]), 4),
                "Yhat_Lower":    round(float(lower[i]), 4),
                "Yhat_Upper":    round(float(upper[i]), 4),
                "Trend":         None,
                "Trend_Lower":   None,
                "Trend_Upper":   None,
                "Is_Forecast":   1,
                "Statut_RAG":    statut_rag,
                "Risk_Score":    risk_score,
                "Source_Modele": "ARIMA",
                "Date_Calcul":   now,
                "GroupKey":      group_value,   # None si pas de groupement
            })

        return pd.DataFrame(hist_records + fc_records)

    # ------------------------------------------------------------------
    # PIPELINE PRINCIPAL
    # ------------------------------------------------------------------

    def run_all(self) -> dict[str, pd.DataFrame]:
        """
        Exécute toutes les configurations ARIMA_CONFIGS.

        Returns
        -------
        dict[str, pd.DataFrame]  — clés = noms de tables Gold
        """
        logger.info("[ARIMA] === Démarrage prédictions ARIMA (%d configs) ===", len(ARIMA_CONFIGS))

        if self.engine is not None:
            try:
                _ensure_gold_tables(self.engine)
            except Exception as exc:
                logger.warning("[ARIMA] Création/migration tables Gold impossible : %s", exc)

        accumulated: dict[str, list[pd.DataFrame]] = {t: [] for t in GOLD_FORECAST_TABLES.values()}
        self._kpis_by_table = {t: set() for t in GOLD_FORECAST_TABLES.values()}

        for cfg in ARIMA_CONFIGS:
            gold_table = GOLD_FORECAST_TABLES[cfg.domain]
            logger.info("[ARIMA] → %s / %s (horizon=%d)", cfg.domain, cfg.kpi, cfg.horizon)

            try:
                df_silver = self._load_silver(cfg.domain)
                if df_silver.empty:
                    continue

                if cfg.group_col and cfg.group_col in df_silver.columns:
                    groups = df_silver[cfg.group_col].unique()
                    for grp in groups:
                        df_fc = self._forecast_series(df_silver.copy(), cfg, group_value=str(grp))
                        if not df_fc.empty:
                            accumulated[gold_table].append(df_fc)
                            logger.info(
                                "[ARIMA]   %s/%s/%s → %d lignes",
                                cfg.domain, cfg.kpi, grp, len(df_fc)
                            )
                else:
                    df_fc = self._forecast_series(df_silver.copy(), cfg)
                    if not df_fc.empty:
                        accumulated[gold_table].append(df_fc)
                        logger.info(
                            "[ARIMA]   %s/%s → %d lignes",
                            cfg.domain, cfg.kpi, len(df_fc)
                        )

                self._kpis_by_table[gold_table].add(cfg.kpi)

            except Exception as exc:
                logger.error(
                    "[ARIMA] ✗ Config (%s/%s) échouée : %s",
                    cfg.domain, cfg.kpi, exc, exc_info=True
                )

        results: dict[str, pd.DataFrame] = {}
        for table, frames in accumulated.items():
            if frames:
                results[table] = pd.concat(frames, ignore_index=True)
                logger.info("[ARIMA] %s : %d lignes totales", table, len(results[table]))
            else:
                results[table] = pd.DataFrame()

        self._results = results
        logger.info("[ARIMA] === Prédictions ARIMA terminées ===")
        return results

    # ------------------------------------------------------------------
    # SAUVEGARDE
    # ------------------------------------------------------------------

    def save_results(
        self,
        results: Optional[dict[str, pd.DataFrame]] = None,
        dry_run: bool = False,
    ) -> dict[str, int]:
        """
        Sauvegarde les prédictions dans les tables Gold.forecast_*.

        Stratégie anti-doublon :
        - Tables ARIMA-only (parc_auto, maintenance) → TRUNCATE puis INSERT
        - Tables partagées (itam, gouvernance)       → DELETE par KPI puis INSERT

        Returns
        -------
        dict[str, int] : {table_name: nb_lignes_ecrites}
        """
        if results is None:
            results = self._results

        written: dict[str, int] = {}

        for gold_table, df in results.items():
            if df.empty:
                logger.info("[ARIMA] %s : vide — ignoré", gold_table)
                written[gold_table] = 0
                continue

            schema, table_name = gold_table.split(".")
            nb = len(df)

            if dry_run:
                logger.info("[ARIMA] --dry-run : %s → %d lignes (non écrites)", gold_table, nb)
                print(f"\n--- {gold_table} ({nb} lignes) ---")
                print(df.head(5).to_string())
                written[gold_table] = nb
                continue

            if self.engine is not None:
                try:
                    self._write_to_sql(df, gold_table, schema, table_name)
                    logger.info("[ARIMA] ✅ %d lignes → %s", nb, gold_table)
                    written[gold_table] = nb
                    continue
                except Exception as exc:
                    logger.warning("[ARIMA] SQL KO (%s) → fallback CSV : %s", gold_table, exc)

            # Fallback CSV (ne devrait plus être atteint avec le bon schéma)
            CSV_FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
            safe_name = gold_table.replace(".", "_").replace(" ", "_")
            csv_path = CSV_FALLBACK_DIR / f"arima_{safe_name}.csv"
            df.to_csv(csv_path, index=False)
            logger.info("[ARIMA] ✅ %d lignes → %s", nb, csv_path)
            written[gold_table] = nb

        return written

    def _write_to_sql(
    self,
    df: pd.DataFrame,
    gold_table: str,
    schema: str,
    table_name: str,
    ) -> None:
   
     kpis = df["KPI"].unique().tolist()

     with self.engine.begin() as conn:
        for kpi in kpis:
            conn.execute(
                text(f"DELETE FROM [{schema}].[{table_name}] WHERE KPI = :kpi"),
                {"kpi": kpi}
            )
            logger.info("[ARIMA] DELETE KPI=%s dans %s avant INSERT", kpi, gold_table)

     df.to_sql(
        table_name,
        self.engine,
        schema=schema,
        if_exists="append",
        index=False,
    )

    # ------------------------------------------------------------------
    # RAPPORT SYNTHÈSE
    # ------------------------------------------------------------------

    def summary(self, results: Optional[dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
        """Retourne un tableau synthèse par table Gold."""
        if results is None:
            results = self._results

        rows = []
        for table, df in results.items():
            if df.empty:
                rows.append({"Table": table, "Total": 0, "Historique": 0, "Forecast": 0,
                             "ROUGE": 0, "AMBRE": 0, "VERT": 0})
                continue
            rows.append({
                "Table":       table,
                "Total":       len(df),
                "Historique":  (df["Is_Forecast"] == 0).sum(),
                "Forecast":    (df["Is_Forecast"] == 1).sum(),
                "ROUGE":       (df["Statut_RAG"] == "ROUGE").sum(),
                "AMBRE":       (df["Statut_RAG"] == "AMBRE").sum(),
                "VERT":        (df["Statut_RAG"] == "VERT").sum(),
            })
        return pd.DataFrame(rows)


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    parser = argparse.ArgumentParser(description="Dashboard 360° — ARIMA Forecaster")
    parser.add_argument("--dry-run", action="store_true", help="Exécute sans écrire en base")
    parser.add_argument(
        "--domain", default=None,
        help="Domaine unique (ex: itam, maintenance, parc_auto, gouvernance)"
    )
    args = parser.parse_args()

    engine = get_db_engine() if get_db_engine else None
    forecaster = ARIMAForecaster(engine=engine)

    if args.domain:
        import ml.forecasting.arima_forecaster as _self_module
        filtered = [c for c in ARIMA_CONFIGS if c.domain == args.domain]
        if not filtered:
            print(f"❌ Domaine '{args.domain}' inconnu. Disponibles : itam, maintenance, parc_auto, gouvernance")
            exit(1)
        _self_module.ARIMA_CONFIGS = filtered

    results = forecaster.run_all()
    print("\n=== RÉSUMÉ ARIMA ===")
    print(forecaster.summary(results).to_string(index=False))

    written = forecaster.save_results(results, dry_run=args.dry_run)
    total = sum(written.values())
    print(f"\n✅ Total lignes sauvegardées : {total}")
    for table, n in written.items():
        print(f"   {table} : {n}")