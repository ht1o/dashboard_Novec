# =============================================================================
# ml/pipeline.py
# Dashboard 360° Novec — Orchestrateur ML global (Étape D)
# Ordre : Détection (IF + ZScore) → Prédiction (Prophet + ARIMA) → Scoring
# =============================================================================

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import date, datetime
from pathlib import Path
from prefect.cache_policies import NO_CACHE

# ── Résolution des chemins (pattern identique aux autres modules) ─────────────
import os
_HERE     = os.path.dirname(os.path.abspath(__file__))   # ml/
_ROOT     = os.path.dirname(_HERE)                        # dashboard360_novec/
_DATA_SIM = os.path.join(_ROOT, "data_simulation")

for _p in [_ROOT, _DATA_SIM]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from config import get_db_engine
except ImportError:
    def get_db_engine():
        logger.warning("config.py introuvable")
        return None

# ── Imports modules ML ────────────────────────────────────────────────────────
from ml.anomaly_detection.isolation_forest_detector import (
    IsolationForestDetector,
    load_from_sql,
    load_from_csv,
    save_results as save_if_results,
)
from ml.anomaly_detection.zscore_detector import ZScoreDetector
from ml.forecasting.prophet_forecaster import ProphetForecaster
from ml.forecasting.arima_forecaster import ARIMAForecaster
from ml.scoring.it_risk_score import compute_it_risk_score, _print_report

try:
    from prefect import flow, task
    PREFECT_AVAILABLE = True
except ImportError:
    # Graceful degradation sans Prefect
    PREFECT_AVAILABLE = False
    def flow(**kwargs):
        def decorator(fn):
            return fn
        return decorator
    def task(**kwargs):
        def decorator(fn):
            return fn
        return decorator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# RÉSUMÉ D'EXÉCUTION — accumulé pendant le run
# =============================================================================

class RunSummary:
    """Accumule les métriques du pipeline pour le rapport final et pipeline_runs."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.started_at = datetime.utcnow()
        self.finished_at: datetime | None = None
        self.status = "running"
        self.error_message: str | None = None

        # Résultats étape par étape
        self.if_anomalies_detectees    = 0
        self.zscore_alertes_generees   = 0
        self.prophet_predictions        = 0
        self.arima_predictions          = 0
        self.risk_score_global: float | None = None
        self.risk_score_rag: str | None = None
        self.step_errors: list[str] = []

    def finalize(self, status: str = "success"):
        self.finished_at = datetime.utcnow()
        self.status = status

    @property
    def duration_seconds(self) -> int | None:
        if self.finished_at:
            return int((self.finished_at - self.started_at).total_seconds())
        return None

    def to_dict(self) -> dict:
        return {
            "Run_Id":                   self.run_id,
            "Triggered_By":             "manual",
            "Started_At":               self.started_at,
            "Finished_At":              self.finished_at,
            "Duration_Seconds":         self.duration_seconds,
            "Status":                   self.status,
            "Error_Message":            self.error_message,
            "IF_Anomalies_Detectees":   self.if_anomalies_detectees,
            "ZScore_Alertes_Generees":  self.zscore_alertes_generees,
            "Prophet_Predictions":      self.prophet_predictions,
            "ARIMA_Predictions":        self.arima_predictions,
            "Risk_Score_Global":        self.risk_score_global,
            "Risk_Score_RAG":           self.risk_score_rag,
        }

    def print_report(self):
        status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(self.status, "⚪")
        print()
        print("=" * 65)
        print(f"  PIPELINE ML — Dashboard 360° Novec  {status_icon} {self.status.upper()}")
        print("=" * 65)
        print(f"  Run ID        : {self.run_id}")
        print(f"  Démarré       : {self.started_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"  Durée         : {self.duration_seconds}s")
        print()
        print(f"  IF anomalies détectées   : {self.if_anomalies_detectees:>6}")
        print(f"  ZScore alertes générées  : {self.zscore_alertes_generees:>6}")
        print(f"  Prophet prédictions      : {self.prophet_predictions:>6}")
        print(f"  ARIMA prédictions        : {self.arima_predictions:>6}")
        if self.risk_score_global is not None:
            rag_icon = {"ROUGE": "🔴", "AMBRE": "🟡", "VERT": "🟢"}.get(self.risk_score_rag, "⚪")
            print(f"  IT Risk Score global     : {self.risk_score_global:>5.1f} / 100  {rag_icon} {self.risk_score_rag}")
        if self.step_errors:
            print()
            print("  Erreurs non bloquantes :")
            for err in self.step_errors:
                print(f"    ⚠️  {err}")
        print("=" * 65)


# =============================================================================
# TÂCHES PREFECT (ou fonctions simples si Prefect absent)
# =============================================================================

@task(name="IF_Detection", retries=1, cache_policy=NO_CACHE)
def task_isolation_forest(engine, use_csv: bool, dry_run: bool, summary: RunSummary):
    """
    Étape 1a — Détection Isolation Forest.
    Écrit Gold.anomalies_if_details et Gold.anomalies_detected (replace).
    """
    logger.info("── [1a] Isolation Forest Detector ──")
    try:
        if use_csv or engine is None:
            data = load_from_csv()
        else:
            data = load_from_sql(engine)

        detector = IsolationForestDetector()
        results = detector.run_all(data)

        if results.empty:
            logger.warning("[IF] Aucun résultat — étape ignorée")
            return 0

        nb_anomalies = int((results["Anomalie_IF"] == 1).sum())
        logger.info("[IF] %d anomalies détectées sur %d observations", nb_anomalies, len(results))

        if not dry_run:
            save_if_results(results, engine=engine if not use_csv else None)

        summary.if_anomalies_detectees = nb_anomalies
        return nb_anomalies

    except Exception as exc:
        msg = f"Isolation Forest échoué : {exc}"
        logger.error("[IF] %s", msg)
        summary.step_errors.append(msg)
        return 0


@task(name="ZScore_Detection", retries=1, cache_policy=NO_CACHE)
def task_zscore(engine, dry_run: bool, summary: RunSummary):
    """
    Étape 1b — Détection Z-Score.
    Écrit dans Gold.anomalies_detected (append — IF a déjà écrit en replace).
    """
    logger.info("── [1b] ZScore Detector ──")
    try:
        detector = ZScoreDetector(engine=engine)
        results = detector.run_all()
        nb = detector.save_results(results, dry_run=dry_run)
        summary.zscore_alertes_generees = nb
        logger.info("[ZScore] %d anomalies ROUGE/AMBRE sauvegardées", nb)
        return nb

    except Exception as exc:
        msg = f"ZScore échoué : {exc}"
        logger.error("[ZScore] %s", msg)
        summary.step_errors.append(msg)
        return 0


@task(name="Prophet_Forecast", retries=1, cache_policy=NO_CACHE)
def task_prophet(engine, dry_run: bool, summary: RunSummary):
    """
    Étape 2a — Prédictions Prophet.
    Écrit Gold.forecast_* (DELETE/KPI + append) + Gold.prophet_alerts (append).
    """
    logger.info("── [2a] Prophet Forecaster ──")
    try:
        forecaster = ProphetForecaster(engine=engine)
        results = forecaster.run_all()

        nb_total = sum(len(df) for key, df in results.items() if key != "alerts")
        nb_alerts = len(results.get("alerts", []))
        logger.info("[Prophet] %d prédictions + %d alertes", nb_total, nb_alerts)

        if not dry_run and engine is not None:
            _save_prophet_results(engine, results)

        summary.prophet_predictions = nb_total
        return nb_total

    except Exception as exc:
        msg = f"Prophet échoué : {exc}"
        logger.error("[Prophet] %s", msg)
        summary.step_errors.append(msg)
        return 0


def _save_prophet_results(engine, results: dict):
    """
    Persiste les résultats Prophet dans les tables Gold forecast.

    Stratégie cyclique (alignée avec master_pipeline._save_prophet) :
      - forecast_* : DELETE par KPI (évite les doublons sur UNIQUE KPI+DS)
        puis INSERT en append — l'historique des autres KPIs (ex: ARIMA) est préservé.
      - prophet_alerts : append direct + Date_Calcul pour traçabilité.
    """
    import pandas as pd
    from sqlalchemy import text

    TABLE_MAP = {
        "infra":       ("forecast_infra",       "Gold", "server_name"),
        "itsm":        ("forecast_itsm",         "Gold", None),
        "cybersec":    ("forecast_cybersec",      "Gold", None),
        "itam":        ("forecast_itam",          "Gold", None),
        "apps":        ("forecast_apps",          "Gold", "application_name"),
        "gouvernance": ("forecast_gouvernance",   "Gold", "departement"),
    }

    RENAME = {
        "ds": "DS", "yhat": "Yhat", "yhat_lower": "Yhat_Lower",
        "yhat_upper": "Yhat_Upper", "trend": "Trend",
        "trend_lower": "Trend_Lower", "trend_upper": "Trend_Upper",
        "rag_status": "Statut_RAG", "risk_score": "Risk_Score",
        "is_forecast": "Is_Forecast", "kpi": "KPI",
    }
    now = datetime.utcnow()

    for domain, (table_name, schema, entity_col) in TABLE_MAP.items():
        df: pd.DataFrame = results.get(domain)
        if df is None or df.empty:
            continue

        # Normaliser les colonnes pour correspondre au schéma Gold
        df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})

        # Colonnes additionnelles
        if "Source_Modele" not in df.columns:
            df["Source_Modele"] = "Prophet"
        if "Date_Calcul" not in df.columns:
            df["Date_Calcul"] = now

        # Colonne entité → GroupKey ou colonne dédiée
        if entity_col and entity_col in df.columns:
            df = df.rename(columns={entity_col: entity_col.title().replace("_", "")
                                    if entity_col not in df.columns else entity_col})

        # ── CORRECTION : DELETE par KPI puis append ────────────────────────
        # On supprime uniquement les lignes du KPI qu'on va réinsérer,
        # sans toucher aux KPIs écrits par ARIMA dans la même table.
        # Remplace l'ancienne stratégie if_exists="replace" qui détruisait
        # toute la table (données ARIMA perdues + GroupKey supprimée).
        if "KPI" in df.columns:
            kpis = df["KPI"].unique().tolist()
            try:
                with engine.begin() as conn:
                    for kpi in kpis:
                        conn.execute(
                            text(f"DELETE FROM {schema}.{table_name} WHERE KPI = :kpi"),
                            {"kpi": kpi},
                        )
                        logger.info(
                            "[Prophet] DELETE KPI=%s dans %s.%s avant INSERT",
                            kpi, schema, table_name
                        )
            except Exception as exc:
                logger.warning(
                    "[Prophet] DELETE KPI KO sur %s.%s : %s", schema, table_name, exc
                )

        try:
            # ── CORRECTION : replace → append ─────────────────────────────
            df.to_sql(table_name, engine, schema=schema, if_exists="append", index=False)
            logger.info("[Prophet] ✅ %d lignes → %s.%s", len(df), schema, table_name)
        except Exception as exc:
            logger.warning("[Prophet] SQL KO %s.%s : %s", schema, table_name, exc)

    # Alertes Prophet → Gold.prophet_alerts
    alerts = results.get("alerts")
    if alerts is not None and not alerts.empty:
        alerts = alerts.copy()
        alerts["Est_Active"] = 1
        if "Date_Calcul" not in alerts.columns:
            alerts["Date_Calcul"] = now
        try:
            # ── CORRECTION : replace → append ─────────────────────────────
            alerts.to_sql("prophet_alerts", engine, schema="Gold",
                          if_exists="append", index=False)
            logger.info("[Prophet] ✅ %d alertes → Gold.prophet_alerts", len(alerts))
        except Exception as exc:
            logger.warning("[Prophet] SQL KO prophet_alerts : %s", exc)


@task(name="ARIMA_Forecast", retries=1, cache_policy=NO_CACHE)
def task_arima(engine, dry_run: bool, summary: RunSummary):
    """
    Étape 2b — Prédictions ARIMA.
    Écrit Gold.forecast_itam, forecast_gouvernance, forecast_maintenance, forecast_parc_auto (append).
    """
    logger.info("── [2b] ARIMA Forecaster ──")
    try:
        forecaster = ARIMAForecaster(engine=engine)
        results = forecaster.run_all()
        written = forecaster.save_results(results, dry_run=dry_run)
        nb_total = sum(written.values())
        summary.arima_predictions = nb_total
        logger.info("[ARIMA] %d prédictions sauvegardées", nb_total)
        return nb_total

    except Exception as exc:
        msg = f"ARIMA échoué : {exc}"
        logger.error("[ARIMA] %s", msg)
        summary.step_errors.append(msg)
        return 0


@task(name="IT_Risk_Score", retries=1, cache_policy=NO_CACHE)
def task_risk_score(engine, dry_run: bool, summary: RunSummary):
    """
    Étape 3 — IT Risk Score.
    Dépend des étapes 1 ET 2 — TOUJOURS en dernier.
    Lit Gold.anomalies_detected + Gold.prophet_alerts + Gold.forecast_*.
    Écrit Gold.it_risk_score (DELETE+INSERT idempotent).
    """
    logger.info("── [3] IT Risk Score ──")

    if engine is None:
        msg = "Risk Score requiert SQL Server — ignoré (engine=None)"
        logger.warning("[RiskScore] %s", msg)
        summary.step_errors.append(msg)
        return None

    try:
        result = compute_it_risk_score(engine, date_key=date.today(), dry_run=dry_run)
        summary.risk_score_global = result["Score_Global"]
        summary.risk_score_rag    = result["Statut_RAG_Global"]
        logger.info(
            "[RiskScore] Score_Global=%.1f RAG=%s",
            result["Score_Global"], result["Statut_RAG_Global"]
        )
        return result

    except Exception as exc:
        msg = f"Risk Score échoué : {exc}"
        logger.error("[RiskScore] %s", msg)
        summary.step_errors.append(msg)
        return None


# =============================================================================
# SAUVEGARDE DU RUN DANS Gold.pipeline_runs
# =============================================================================

def _save_pipeline_run(engine, summary: RunSummary) -> None:
    """Persiste le résumé du run dans Gold.pipeline_runs."""
    if engine is None:
        return
    import pandas as pd
    try:
        df = pd.DataFrame([summary.to_dict()])
        df.to_sql("pipeline_runs", engine, schema="Gold", if_exists="append", index=False)
        logger.info("[Pipeline] Run %s enregistré dans Gold.pipeline_runs", summary.run_id)
    except Exception as exc:
        logger.warning("[Pipeline] Impossible d'enregistrer le run : %s", exc)


# =============================================================================
# FLOW PREFECT — ORCHESTRATEUR PRINCIPAL
# =============================================================================

@flow(name="Dashboard360_ML_Pipeline")
def run_pipeline(
    use_csv: bool = False,
    dry_run: bool = False,
    skip_scoring: bool = False,
) -> RunSummary:
    """
    Pipeline ML complet — Dashboard 360° Novec.

    Ordre d'exécution strict (dépendances causales) :
      1. Détection (IF + ZScore)           → écrit Gold.anomalies_*
      2. Prédiction (Prophet + ARIMA)      → écrit Gold.forecast_* + Gold.prophet_alerts
      3. Scoring (IT Risk Score)           → lit anomalies + forecast → écrit Gold.it_risk_score

    NE PAS modifier l'ordre — le Risk Score dépend des deux premières étapes.

    Parameters
    ----------
    use_csv     : forcer la lecture CSV (sans SQL Server)
    dry_run     : exécute le pipeline sans écrire en base
    skip_scoring: saute l'étape 3 (utile en test si Gold incomplète)
    """
    run_id = str(uuid.uuid4())[:8]
    summary = RunSummary(run_id)

    logger.info("════════════════════════════════════════════════")
    logger.info("  PIPELINE ML — Dashboard 360° Novec")
    logger.info("  Run ID : %s | dry_run=%s | use_csv=%s", run_id, dry_run, use_csv)
    logger.info("════════════════════════════════════════════════")

    # Connexion base
    engine = None
    if not use_csv:
        engine = get_db_engine()
        if engine is None:
            logger.warning("[Pipeline] SQL Server indisponible — mode CSV activé")
            use_csv = True

    # ──────────────────────────────────────────────────────────────────────────
    # ÉTAPE 1 — DÉTECTION (IF puis ZScore)
    # Dépendance : ZScore doit écrire en APPEND après IF (replace)
    # ──────────────────────────────────────────────────────────────────────────
    logger.info("[Pipeline] === ÉTAPE 1 — Détection des anomalies ===")

    # 1a — Isolation Forest (écrit en REPLACE → vide la table)
    task_isolation_forest(engine, use_csv, dry_run, summary)

    # 1b — ZScore (écrit en APPEND → complète la table)
    task_zscore(engine, dry_run, summary)

    # ──────────────────────────────────────────────────────────────────────────
    # ÉTAPE 2 — PRÉDICTION (Prophet puis ARIMA)
    # Prophet : DELETE/KPI + append sur ses tables
    # ARIMA   : append sur ses tables
    # ──────────────────────────────────────────────────────────────────────────
    logger.info("[Pipeline] === ÉTAPE 2 — Prédictions ===")

    task_prophet(engine, dry_run, summary)
    task_arima(engine, dry_run, summary)

    # ──────────────────────────────────────────────────────────────────────────
    # ÉTAPE 3 — SCORING (dépend des deux premières — TOUJOURS EN DERNIER)
    # ──────────────────────────────────────────────────────────────────────────
    if not skip_scoring:
        logger.info("[Pipeline] === ÉTAPE 3 — IT Risk Score ===")
        task_risk_score(engine, dry_run, summary)
    else:
        logger.info("[Pipeline] === ÉTAPE 3 ignorée (--skip-scoring) ===")

    # ──────────────────────────────────────────────────────────────────────────
    # FINALISATION
    # ──────────────────────────────────────────────────────────────────────────
    status = "success" if not summary.step_errors else "partial"
    summary.finalize(status=status)

    if not dry_run:
        _save_pipeline_run(engine, summary)

    summary.print_report()
    return summary


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Dashboard 360° Novec — Pipeline ML complet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python ml/pipeline.py                         # run normal
  python ml/pipeline.py --dry-run               # sans écriture SQL
  python ml/pipeline.py --csv                   # données CSV, sans SQL Server
  python ml/pipeline.py --dry-run --skip-scoring # test détection + forecast uniquement
        """,
    )
    parser.add_argument("--dry-run",      action="store_true",
                        help="Exécute le pipeline sans écrire en base")
    parser.add_argument("--csv",          action="store_true",
                        help="Forcer la lecture depuis les CSV Silver")
    parser.add_argument("--skip-scoring", action="store_true",
                        help="Ignorer l'étape IT Risk Score (utile en debug)")
    args = parser.parse_args()

    summary = run_pipeline(
        use_csv=args.csv,
        dry_run=args.dry_run,
        skip_scoring=args.skip_scoring,
    )

    # Code de sortie : 0 = succès, 1 = partial/failed
    exit_code = 0 if summary.status == "success" else 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()