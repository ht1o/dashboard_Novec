"""
prophet_forecaster.py
=====================
Dashboard 360 Novec — Phase 3 ML Pipeline
Prédiction de séries temporelles par domaine avec Prophet.

Architecture :
  SQL Server (Silver)  →  ProphetForecaster  →  dict de DataFrames Gold
  CSV fallback (--csv)                          (forecast_infra, forecast_itsm, ...)

  Chargement :
    • Primaire  : pd.read_sql() via SQLAlchemy (même pattern qu'Isolation Forest)
    • Fallback  : CSV Silver si engine=None ou flag --csv

KPIs couverts (priorité 🔴→🟢) :
  🔴 Infrastructure  : Disk_Moyen_Pct, Latence_Moyenne_ms, Disponibilite_Pct   (par serveur)
  🔴 ITSM            : Volume_Total, Backlog_Total
  🟡 Cybersécurité   : MFA_Adoption_Pct, Taux_Phishing_Moyen_Pct,
                       RGPD_Conformite_Pct, Systemes_Patches_Moyen_Pct
  🟡 ITAM            : Vetuste_Moyen_Pct, CMDB_Couverture_Pct
  🟢 Applications    : Adoption_PowerBI_Pct, Temps_Reponse_Moyen_ms,
                       Qualite_Donnees_Pct                               (par app)
  🟢 Gouvernance     : Adoption_Digital_Pct, Ecart_Budget_Moyen_Pct     (par département)
"""

import logging
import os
import sys
import argparse
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Résolution des chemins (identique à isolation_forest_detector.py) ─────────
_HERE     = os.path.dirname(os.path.abspath(__file__))   # ml/forecasting
_ROOT     = os.path.dirname(os.path.dirname(_HERE))      # dashboard360_novec
_DATA_SIM = os.path.join(_ROOT, "data_simulation")

for _p in [_DATA_SIM]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from config import get_db_engine
except ImportError:
    def get_db_engine():
        logger.warning("config.py introuvable — mode CSV activé automatiquement")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Configuration centralisée
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ForecastConfig:
    """
    Paramètres Prophet par domaine / KPI.

    Champs clés :
      horizon_days          : nombre de jours de prédiction
      changepoint_prior     : 0.05 = conservateur (évite le surajustement)
      weekly_seasonality    : True pour ITSM (pic lundi) / Infra horaire
      yearly_seasonality    : False si série < 2 ans
      alert_threshold       : seuil RAG Rouge (valeur absolue ou % selon KPI)
      alert_direction       : 'above' si alerte quand yhat > seuil, 'below' sinon
    """
    horizon_days: int = 30
    changepoint_prior: float = 0.05
    weekly_seasonality: bool = False
    yearly_seasonality: bool = False
    daily_seasonality: bool = False
    alert_threshold: Optional[float] = None
    alert_direction: str = "above"        # 'above' | 'below'
    contamination: float = 0.05           # non utilisé ici, héritage pipeline
    freq: str = "D"                       # 'D' journalier, 'MS' début de mois


# Table de configuration par (domaine, kpi)
FORECAST_CONFIGS: dict[tuple[str, str], ForecastConfig] = {
    # ── Infrastructure ──────────────────────────────────────────────────────
    ("infra", "Disk_Moyen_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=80.0,
        alert_direction="above",
        freq="D",
    ),
    ("infra", "Latence_Moyenne_ms"): ForecastConfig(
        horizon_days=7,
        changepoint_prior=0.05,
        weekly_seasonality=True,
        alert_threshold=50.0,
        alert_direction="above",
        freq="D",
    ),
    ("infra", "Disponibilite_Pct"): ForecastConfig(
        horizon_days=7,
        changepoint_prior=0.05,
        weekly_seasonality=True,
        alert_threshold=95.0,
        alert_direction="below",
        freq="D",
    ),
    # ── ITSM ────────────────────────────────────────────────────────────────
    ("itsm", "Volume_Total"): ForecastConfig(
        horizon_days=7,
        changepoint_prior=0.05,
        weekly_seasonality=True,    # pic lundi
        alert_threshold=None,
        freq="D",
    ),
    ("itsm", "Backlog_Total"): ForecastConfig(
        horizon_days=14,
        changepoint_prior=0.05,
        weekly_seasonality=True,
        alert_threshold=50.0,
        alert_direction="above",
        freq="D",
    ),
    # ── Cybersécurité ────────────────────────────────────────────────────────
    ("cybersec", "MFA_Adoption_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=70.0,
        alert_direction="below",
        freq="D",
    ),
    ("cybersec", "Taux_Phishing_Moyen_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=20.0,
        alert_direction="above",
        freq="D",
    ),
    ("cybersec", "RGPD_Conformite_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=90.0,
        alert_direction="below",
        freq="D",
    ),
    ("cybersec", "Systemes_Patches_Moyen_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=90.0,
        alert_direction="below",
        freq="D",
    ),
    # ── ITAM ─────────────────────────────────────────────────────────────────
    ("itam", "Vetuste_Moyen_Pct"): ForecastConfig(
        horizon_days=180,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=40.0,
        alert_direction="above",
        freq="MS",
    ),
    ("itam", "CMDB_Couverture_Pct"): ForecastConfig(
        horizon_days=180,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=75.0,
        alert_direction="below",
        freq="MS",
    ),
    # ── Applications ─────────────────────────────────────────────────────────
    ("apps", "Adoption_PowerBI_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=None,
        freq="D",
    ),
    ("apps", "Temps_Reponse_Moyen_ms"): ForecastConfig(
        horizon_days=7,
        changepoint_prior=0.05,
        weekly_seasonality=True,
        alert_threshold=200.0,
        alert_direction="above",
        freq="D",
    ),
    ("apps", "Qualite_Donnees_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=90.0,
        alert_direction="below",
        freq="D",
    ),
    # ── Gouvernance ──────────────────────────────────────────────────────────
    ("gouvernance", "Adoption_Digital_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=None,
        freq="MS",
    ),
    ("gouvernance", "Ecart_Budget_Moyen_Pct"): ForecastConfig(
        horizon_days=90,
        changepoint_prior=0.05,
        weekly_seasonality=False,
        alert_threshold=10.0,
        alert_direction="above",
        freq="MS",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Utilitaires
# ─────────────────────────────────────────────────────────────────────────────

def _rag_status(row: pd.Series, cfg: ForecastConfig) -> str:
    """Calcule le statut RAG pour une ligne de forecast.

    Utilise yhat_upper (scénario pessimiste) pour les alertes 'above'
    et yhat_lower pour les alertes 'below'.
    """
    if cfg.alert_threshold is None:
        return "VERT"

    if cfg.alert_direction == "above":
        pessimistic = row["yhat_upper"]
        if pessimistic >= cfg.alert_threshold:
            if row["yhat"] >= cfg.alert_threshold:
                return "ROUGE"
            return "AMBRE"
    else:  # below
        pessimistic = row["yhat_lower"]
        if pessimistic <= cfg.alert_threshold:
            if row["yhat"] <= cfg.alert_threshold:
                return "ROUGE"
            return "AMBRE"
    return "VERT"


def _normalize_score(yhat: float, yhat_lower: float, yhat_upper: float,
                     alert_threshold: Optional[float],
                     direction: str) -> float:
    """Normalise la prédiction en score de risque [0, 1].

    Score 0 = aucun risque, 1 = risque maximal.
    """
    if alert_threshold is None:
        return 0.0
    spread = max(abs(yhat_upper - yhat_lower), 1e-6)
    if direction == "above":
        dist = (yhat - alert_threshold) / spread
    else:
        dist = (alert_threshold - yhat) / spread
    return float(np.clip(0.5 + 0.5 * dist, 0.0, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Classe principale
# ─────────────────────────────────────────────────────────────────────────────


# ── Table de correspondance domaine → table SQL Silver ────────────────────────
# Miroir exact du schéma visible dans SQL Server Management Studio
SILVER_TABLES: dict[str, str] = {
    "infra":       "Silver.silver_infrastructure",
    "itsm":        "Silver.silver_itsm",
    "cybersec":    "Silver.silver_cybersecurity",
    "itam":        "Silver.silver_itam",
    "apps":        "Silver.silver_applications",
    "gouvernance": "Silver.silver_gouvernance",
}

# Noms des fichiers CSV de secours (chemin relatif depuis _ROOT/silver_dataset/)
SILVER_CSV: dict[str, str] = {
    "infra":       "silver_infra.csv",
    "itsm":        "silver_itsm.csv",
    "cybersec":    "silver_cybersec.csv",
    "itam":        "silver_itam.csv",
    "apps":        "silver_apps.csv",
    "gouvernance": "silver_gouvernance.csv",
}


class ProphetForecaster:
    """
    Entraîne un modèle Prophet par (entité × KPI) et produit les prédictions
    Gold avec colonnes RAG et score de risque.

    Chargement des données :
      • SQL Server (primaire) : pd.read_sql() via l'engine SQLAlchemy
      • CSV (fallback)        : si engine=None ou si la requête SQL échoue

    Usage SQL (recommandé) :
        from config import get_db_engine
        engine    = get_db_engine()
        forecaster = ProphetForecaster(engine=engine)
        results   = forecaster.run_all()

    Usage CSV (debug / hors réseau) :
        forecaster = ProphetForecaster()          # engine=None → fallback CSV
        results    = forecaster.run_all()
        # ou : python prophet_forecaster.py --csv
    """

    def __init__(self, engine=None, silver_dir: str = None):
        """
        Paramètres
        ----------
        engine     : SQLAlchemy engine issu de get_db_engine().
                     Si None, lecture depuis les CSV Silver.
        silver_dir : répertoire des CSV fallback.
                     Par défaut : <_ROOT>/silver_dataset/
        """
        self.engine     = engine
        self.silver_dir = Path(silver_dir) if silver_dir else Path(_ROOT) / "silver_dataset"
        self._loaded: dict[str, pd.DataFrame] = {}

        if self.engine is not None:
            logger.info("ProphetForecaster — source : SQL Server (Dashboard360_Bronze)")
        else:
            logger.info("ProphetForecaster — source : CSV (%s)", self.silver_dir)

    # ── Chargement des Silver ──────────────────────────────────────────────

    def _load(self, domain: str, date_col: str = "DateKey") -> pd.DataFrame:
        """
        Charge la table Silver d'un domaine, avec cache en mémoire.

        Stratégie :
          1. Si engine disponible → SELECT * FROM Silver.<table> via pd.read_sql()
          2. Sinon (ou si SQL échoue) → lecture du CSV de secours
        """
        if domain in self._loaded:
            return self._loaded[domain]

        # ── Tentative SQL ──────────────────────────────────────────────────
        if self.engine is not None:
            sql_table = SILVER_TABLES[domain]
            try:
                logger.info("  SQL → %s", sql_table)
                df = pd.read_sql(f"SELECT * FROM {sql_table}", self.engine)
                df[date_col] = pd.to_datetime(df[date_col])
                self._loaded[domain] = df
                logger.info("  ✓ %s chargé depuis SQL (%d lignes)", sql_table, len(df))
                return df
            except Exception as exc:
                logger.warning("  SQL échoué pour %s (%s) — fallback CSV", sql_table, exc)

        # ── Fallback CSV ───────────────────────────────────────────────────
        csv_file = self.silver_dir / SILVER_CSV[domain]
        logger.info("  CSV → %s", csv_file)
        df = pd.read_csv(csv_file, parse_dates=[date_col])
        df[date_col] = pd.to_datetime(df[date_col])
        self._loaded[domain] = df
        logger.info("  ✓ %s chargé depuis CSV (%d lignes)", csv_file.name, len(df))
        return df

    # ── Entraînement + prédiction pour une série ──────────────────────────

    def _fit_predict(
        self,
        series: pd.Series,       # index = DatetimeIndex, values = float
        cfg: ForecastConfig,
        label: str,
    ) -> pd.DataFrame:
        """
        Entraîne Prophet sur `series` et retourne un DataFrame forecast
        avec colonnes : ds, yhat, yhat_lower, yhat_upper, rag_status, risk_score.
        """
        # — Préparer le format Prophet (ds / y) ——
        df_train = (
            series.dropna()
            .reset_index()
            .rename(columns={"index": "ds", series.name: "y"})
        )
        df_train.columns = ["ds", "y"]
        df_train["ds"] = pd.to_datetime(df_train["ds"])

        if len(df_train) < 5:
            logger.warning("Série trop courte pour %s (%d pts) — ignorée", label, len(df_train))
            return pd.DataFrame()

        # — Initialiser Prophet ——
        model = Prophet(
            changepoint_prior_scale=cfg.changepoint_prior,
            yearly_seasonality=cfg.yearly_seasonality,
            weekly_seasonality=cfg.weekly_seasonality,
            daily_seasonality=cfg.daily_seasonality,
            interval_width=0.80,        # intervalles à 80 % (moins larges, plus utiles)
        )

        # Saisonnalité mensuelle pour les séries mensuelles courtes
        if cfg.freq == "MS":
            model.add_seasonality(name="monthly", period=30.5, fourier_order=3)

        model.fit(df_train)

        # — Génération du futur ——
        periods = cfg.horizon_days
        if cfg.freq == "MS":
            periods = max(1, cfg.horizon_days // 30)

        future = model.make_future_dataframe(periods=periods, freq=cfg.freq)
        forecast = model.predict(future)

        # — Sélection et enrichissement ——
        cols = ["ds", "yhat", "yhat_lower", "yhat_upper", "trend",
                "trend_lower", "trend_upper"]
        result = forecast[cols].copy()

        # Clamp physique [0, 100] pour les pourcentages
        for col in ("yhat", "yhat_lower", "yhat_upper"):
            if "Pct" in label or "pct" in label.lower():
                result[col] = result[col].clip(0, 100)

        # Statut RAG + score de risque
        result["rag_status"] = result.apply(lambda r: _rag_status(r, cfg), axis=1)
        result["risk_score"] = result.apply(
            lambda r: _normalize_score(
                r["yhat"], r["yhat_lower"], r["yhat_upper"],
                cfg.alert_threshold, cfg.alert_direction
            ),
            axis=1,
        )

        # Distinguer historique vs prédiction
        last_date = df_train["ds"].max()
        result["is_forecast"] = result["ds"] > last_date

        logger.info("  ✓ %s → %d jours prédits | RAG Rouge : %d pts",
                    label,
                    result["is_forecast"].sum(),
                    (result["rag_status"] == "ROUGE").sum())
        return result

    # ── Domaines ──────────────────────────────────────────────────────────

    def forecast_infrastructure(self) -> pd.DataFrame:
        """Prédictions par serveur × KPI pour l'infrastructure."""
        df = self._load("infra")

        kpis = ["Disk_Moyen_Pct", "Latence_Moyenne_ms", "Disponibilite_Pct"]
        servers = df["ServerName"].unique()
        frames = []

        for server in servers:
            sub = df[df["ServerName"] == server].set_index("DateKey")
            for kpi in kpis:
                cfg = FORECAST_CONFIGS[("infra", kpi)]
                label = f"{server}::{kpi}"
                series = sub[kpi].rename(kpi)
                res = self._fit_predict(series, cfg, label)
                if res.empty:
                    continue
                res.insert(0, "server_name", server)
                res.insert(1, "kpi", kpi)
                res.insert(2, "domain", "Infrastructure")
                frames.append(res)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def forecast_itsm(self) -> pd.DataFrame:
        """Prédictions des volumes et backlog ITSM (agrégé global)."""
        df = self._load("itsm")
        df = df.set_index("DateKey").sort_index()

        kpis = ["Volume_Total", "Backlog_Total"]
        frames = []

        for kpi in kpis:
            cfg = FORECAST_CONFIGS[("itsm", kpi)]
            series = df[kpi].rename(kpi)
            res = self._fit_predict(series, cfg, f"ITSM::{kpi}")
            if res.empty:
                continue
            res.insert(0, "kpi", kpi)
            res.insert(1, "domain", "ITSM")
            frames.append(res)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def forecast_cybersec(self) -> pd.DataFrame:
        """Prédictions des indicateurs cybersécurité (agrégé global)."""
        df = self._load("cybersec")
        df = df.set_index("DateKey").sort_index()

        kpis = [
            "MFA_Adoption_Pct",
            "Taux_Phishing_Moyen_Pct",
            "RGPD_Conformite_Pct",
            "Systemes_Patches_Moyen_Pct",
        ]
        frames = []

        for kpi in kpis:
            cfg = FORECAST_CONFIGS[("cybersec", kpi)]
            series = df[kpi].rename(kpi)
            res = self._fit_predict(series, cfg, f"Cybersec::{kpi}")
            if res.empty:
                continue
            res.insert(0, "kpi", kpi)
            res.insert(1, "domain", "Cybersécurité")
            frames.append(res)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def forecast_itam(self) -> pd.DataFrame:
        """Prédictions ITAM mensuelles (agrégé global)."""
        df = self._load("itam")
        df = df.set_index("DateKey").sort_index()

        kpis = ["Vetuste_Moyen_Pct", "CMDB_Couverture_Pct"]
        frames = []

        for kpi in kpis:
            cfg = FORECAST_CONFIGS[("itam", kpi)]
            series = df[kpi].rename(kpi)
            res = self._fit_predict(series, cfg, f"ITAM::{kpi}")
            if res.empty:
                continue
            res.insert(0, "kpi", kpi)
            res.insert(1, "domain", "ITAM")
            frames.append(res)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def forecast_applications(self) -> pd.DataFrame:
        """Prédictions par application × KPI."""
        df = self._load("apps")

        kpis = ["Adoption_PowerBI_Pct", "Temps_Reponse_Moyen_ms", "Qualite_Donnees_Pct"]
        apps = df["Application_Name"].unique()
        frames = []

        for app in apps:
            sub = df[df["Application_Name"] == app].set_index("DateKey").sort_index()
            for kpi in kpis:
                cfg = FORECAST_CONFIGS[("apps", kpi)]
                label = f"{app}::{kpi}"
                series = sub[kpi].rename(kpi)
                res = self._fit_predict(series, cfg, label)
                if res.empty:
                    continue
                res.insert(0, "application_name", app)
                res.insert(1, "kpi", kpi)
                res.insert(2, "domain", "Applications")
                frames.append(res)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def forecast_gouvernance(self) -> pd.DataFrame:
        """Prédictions par département × KPI pour la gouvernance."""
        df = self._load("gouvernance")

        kpis = ["Adoption_Digital_Pct", "Ecart_Budget_Moyen_Pct"]
        depts = df["Departement"].unique()
        frames = []

        for dept in depts:
            sub = df[df["Departement"] == dept].set_index("DateKey").sort_index()
            for kpi in kpis:
                cfg = FORECAST_CONFIGS[("gouvernance", kpi)]
                label = f"{dept}::{kpi}"
                series = sub[kpi].rename(kpi)
                res = self._fit_predict(series, cfg, label)
                if res.empty:
                    continue
                res.insert(0, "departement", dept)
                res.insert(1, "kpi", kpi)
                res.insert(2, "domain", "Gouvernance")
                frames.append(res)

        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    # ── Résumé des alertes actives ─────────────────────────────────────────

    @staticmethod
    def build_alert_summary(forecasts: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Extrait toutes les prédictions futures en statut AMBRE ou ROUGE
        et retourne un DataFrame Gold d'alertes triées par risque.

        Colonnes de sortie :
          domain, entity, kpi, first_alert_date, rag_status, risk_score,
          yhat, yhat_lower, yhat_upper
        """
        rows = []
        for domain, df in forecasts.items():
            if df.empty:
                continue
            future = df[df["is_forecast"] & df["rag_status"].isin(["AMBRE", "ROUGE"])].copy()
            if future.empty:
                continue

            # Identifier la colonne "entité" selon le domaine
            entity_col = {
                "infra": "server_name",
                "apps": "application_name",
                "gouvernance": "departement",
            }.get(domain, None)

            for _, row in future.iterrows():
                entity = row[entity_col] if entity_col and entity_col in row.index else "Global"
                rows.append({
                    "domain": row.get("domain", domain),
                    "entity": entity,
                    "kpi": row["kpi"],
                    "first_alert_date": row["ds"],
                    "rag_status": row["rag_status"],
                    "risk_score": round(row["risk_score"], 4),
                    "yhat": round(row["yhat"], 2),
                    "yhat_lower": round(row["yhat_lower"], 2),
                    "yhat_upper": round(row["yhat_upper"], 2),
                })

        if not rows:
            return pd.DataFrame()

        alert_df = pd.DataFrame(rows)
        # Garder la première date d'alerte par (entité × KPI)
        alert_df = (
            alert_df
            .sort_values(["rag_status", "risk_score", "first_alert_date"],
                         ascending=[True, False, True])
            .drop_duplicates(subset=["domain", "entity", "kpi"], keep="first")
            .reset_index(drop=True)
        )
        return alert_df

    # ── Point d'entrée principal ───────────────────────────────────────────

    def run_all(self, export_dir: Optional[str] = None) -> dict[str, pd.DataFrame]:
        """
        Lance toutes les prédictions et retourne un dictionnaire :
          {
            "infra"       : DataFrame,
            "itsm"        : DataFrame,
            "cybersec"    : DataFrame,
            "itam"        : DataFrame,
            "apps"        : DataFrame,
            "gouvernance" : DataFrame,
            "alerts"      : DataFrame  ← résumé Gold des alertes actives
          }

        Si `export_dir` est fourni, chaque DataFrame est sauvegardé en CSV.
        """
        logger.info("══════════════════════════════════════════")
        logger.info("  Prophet Forecaster — Dashboard 360 Novec")
        logger.info("══════════════════════════════════════════")

        runners = {
            "infra":       self.forecast_infrastructure,
            "itsm":        self.forecast_itsm,
            "cybersec":    self.forecast_cybersec,
            "itam":        self.forecast_itam,
            "apps":        self.forecast_applications,
            "gouvernance": self.forecast_gouvernance,
        }

        results: dict[str, pd.DataFrame] = {}
        for name, fn in runners.items():
            logger.info("── Domaine : %s", name.upper())
            try:
                results[name] = fn()
            except Exception as exc:
                logger.error("Erreur domaine %s : %s", name, exc)
                results[name] = pd.DataFrame()

        results["alerts"] = self.build_alert_summary(results)

        # Résumé console
        logger.info("══════════════════════════════════════════")
        for name, df in results.items():
            logger.info("  %-15s → %6d lignes", name, len(df))
        logger.info("══════════════════════════════════════════")

        if export_dir:
            out = Path(export_dir)
            out.mkdir(parents=True, exist_ok=True)
            for name, df in results.items():
                if not df.empty:
                    path = out / f"forecast_{name}.csv"
                    df.to_csv(path, index=False)
                    logger.info("Exporté → %s", path)

        return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. Exécution autonome (test / démo)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prophet Forecaster — Dashboard 360 Novec")
    parser.add_argument("--csv", action="store_true",
                        help="Forcer la lecture depuis les CSV Silver (sans SQL Server)")
    parser.add_argument("--silver-dir", default=None,
                        help="Répertoire des CSV Silver (défaut : <root>/silver_dataset/)")
    parser.add_argument("--export-dir", default=None,
                        help="Répertoire d'export des CSV Gold (optionnel)")
    args = parser.parse_args()

    engine = None
    if not args.csv:
        engine = get_db_engine()
        if engine is None:
            logger.warning("SQL Server non disponible — basculement sur CSV")

    forecaster = ProphetForecaster(engine=engine, silver_dir=args.silver_dir)
    results = forecaster.run_all(export_dir=args.export_dir)

    alerts = results.get("alerts", pd.DataFrame())
    if not alerts.empty:
        print("\n── Alertes Prophet actives (top 10) ──")
        print(alerts.head(10).to_string(index=False))
    else:
        print("\nAucune alerte active détectée.")