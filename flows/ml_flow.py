# =============================================================================
# ml_flow.py
# Dashboard 360° Novec — Flow Prefect : Pipeline ML Gold
#
# Responsabilité UNIQUE : exécuter les algorithmes ML sur les données Silver
# et écrire les résultats dans les tables Gold.
#
# Ordre d'exécution strict (dépendances causales) :
#   1. Isolation Forest  → Gold.anomalies_if_details + Gold.anomalies_detected (replace)
#   2. ZScore            → Gold.anomalies_detected (append)
#   3. Prophet           → Gold.forecast_* (DELETE/KPI + append) + Gold.prophet_alerts
#   4. ARIMA             → Gold.forecast_* (append)
#   5. IT Risk Score     → Gold.it_risk_score (DELETE + INSERT)
#                          ↑ dépend de 1+2+3+4 — TOUJOURS EN DERNIER
#
# Déclenché automatiquement par Prefect Automation après silver_flow SUCCESS.
#
# Usage CLI :
#   python ml_flow.py
#   python ml_flow.py --dry-run
#   python ml_flow.py --skip-scoring
#   python ml_flow.py --skip-forecast     # IF + ZScore uniquement
#   python ml_flow.py --csv               # lecture depuis CSV Silver
# =============================================================================

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

# ── Résolution des chemins ────────────────────────────────────────────────────
_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_SIM = os.path.join(_ROOT, "data_simulation")
_ML       = os.path.join(_ROOT, "ml")
_LOGS     = os.path.join(_ROOT, "logs")

for _p in [_ROOT, _DATA_SIM, _ML]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Logging ───────────────────────────────────────────────────────────────────
from novec_logger import get_logger
logger = get_logger("ml")

# ── Config DB ─────────────────────────────────────────────────────────────────
try:
    from config import get_db_engine
except ImportError:
    def get_db_engine():
        return None

# ── Prefect ───────────────────────────────────────────────────────────────────
try:
    from prefect import flow, task
    from prefect.cache_policies import NO_CACHE
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    NO_CACHE = None
    def flow(**kw):
        def d(fn): return fn
        return d
    def task(**kw):
        def d(fn): return fn
        return d


def _should_skip_ml() -> bool:
    """Vérifie si un autre run ml_flow est déjà en cours."""
    if not PREFECT_AVAILABLE:
        return False
    try:
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.filters import (
            FlowRunFilter,
            FlowRunFilterState,
            FlowRunFilterStateName,
            FlowFilter,
            FlowFilterName,
        )
        import asyncio

        async def _check():
            async with get_client() as client:
                running = await client.read_flow_runs(
                    flow_run_filter=FlowRunFilter(
                        state=FlowRunFilterState(
                            name=FlowRunFilterStateName(any_=["Running"])
                        ),
                    ),
                    flow_filter=FlowFilter(
                        name=FlowFilterName(any_=["novec_ml"])
                    ),
                )
                return len(running)

        nb_running = asyncio.run(_check())
        if nb_running > 1:
            logger.warning(
                "[ML] %d runs 'novec_ml' déjà en cours → doublon, skip.",
                nb_running
            )
            return True
        return False
    except Exception as exc:
        logger.debug("[ML] Garde anti-doublons KO (%s) → on continue", exc)
        return False    
    
# =============================================================================
# TÂCHES ML — une par algorithme
# =============================================================================

@task(
    name="ml_isolation_forest",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_isolation_forest(engine, use_csv: bool, dry_run: bool) -> dict:
    """
    Étape 1a — Isolation Forest.

    Lit les tables Silver (SQL ou CSV).
    Écrit Gold.anomalies_if_details (replace) + Gold.anomalies_detected (replace).
    Le replace est intentionnel : IF repart toujours de zéro,
    ZScore complétera en append juste après.

    Retourne : {"anomalies": int, "observations": int, "status": str}
    """
    logger.info("[ML][IF] Isolation Forest Detector")
    try:
        from ml.anomaly_detection.isolation_forest_detector import (
            IsolationForestDetector,
            load_from_sql,
            load_from_csv,
            save_results,
        )

        data = load_from_csv() if (use_csv or engine is None) else load_from_sql(engine)

        detector = IsolationForestDetector()
        results  = detector.run_all(data)

        if results.empty:
            logger.warning("[ML][IF] Aucun résultat")
            return {"anomalies": 0, "observations": 0, "status": "empty"}

        nb_anomalies = int((results["Anomalie_IF"] == 1).sum())
        nb_total     = len(results)
        logger.info("[ML][IF] %d anomalies / %d observations", nb_anomalies, nb_total)

        if not dry_run:
            save_results(results, engine=None if use_csv else engine)
            logger.info("[ML][IF] ✅ Résultats sauvegardés → Gold.anomalies_*")

        return {"anomalies": nb_anomalies, "observations": nb_total, "status": "ok"}

    except Exception as exc:
        logger.error("[ML][IF] Échec : %s", exc, exc_info=True)
        return {"anomalies": 0, "observations": 0, "status": "error", "error": str(exc)}


@task(
    name="ml_zscore",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_zscore(engine, dry_run: bool) -> dict:
    """
    Étape 1b — ZScore Detector.

    Écrit dans Gold.anomalies_detected en APPEND (après le replace de IF).
    Génère les alertes ROUGE et AMBRE par domaine et par KPI.

    Retourne : {"alertes": int, "status": str}
    """
    logger.info("[ML][ZScore] ZScore Detector")
    try:
        from ml.anomaly_detection.zscore_detector import ZScoreDetector

        detector = ZScoreDetector(engine=engine)
        results  = detector.run_all()
        nb       = detector.save_results(results, dry_run=dry_run)

        logger.info("[ML][ZScore] ✅ %d alertes ROUGE/AMBRE sauvegardées", nb)
        return {"alertes": nb, "status": "ok"}

    except Exception as exc:
        logger.error("[ML][ZScore] Échec : %s", exc, exc_info=True)
        return {"alertes": 0, "status": "error", "error": str(exc)}


@task(
    name="ml_prophet",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_prophet(engine, dry_run: bool) -> dict:
    """
    Étape 2a — Prophet Forecaster.

    Stratégie d'écriture : DELETE par KPI puis INSERT en append.
    Préserve les données ARIMA dans les mêmes tables forecast_*.
    Écrit aussi Gold.prophet_alerts en append.

    Retourne : {"predictions": int, "alerts": int, "status": str}
    """
    logger.info("[ML][Prophet] Prophet Forecaster")
    try:
        from ml.forecasting.prophet_forecaster import ProphetForecaster

        forecaster = ProphetForecaster(engine=engine)
        results    = forecaster.run_all()

        nb_preds  = sum(len(df) for k, df in results.items() if k != "alerts")
        nb_alerts = len(results.get("alerts", []))

        logger.info("[ML][Prophet] %d prédictions + %d alertes générées", nb_preds, nb_alerts)

        if not dry_run and engine is not None:
            _save_prophet_results(engine, results)
            logger.info("[ML][Prophet] ✅ Résultats sauvegardés → Gold.forecast_*")

        return {"predictions": nb_preds, "alerts": nb_alerts, "status": "ok"}

    except Exception as exc:
        logger.error("[ML][Prophet] Échec : %s", exc, exc_info=True)
        return {"predictions": 0, "alerts": 0, "status": "error", "error": str(exc)}


def _save_prophet_results(engine, results: dict) -> None:
    """
    Persiste les prédictions Prophet dans Gold.forecast_* et Gold.prophet_alerts.

    Stratégie DELETE/KPI + append :
      - Supprime uniquement les KPIs Prophet avant de réinsérer
      - Préserve les prédictions ARIMA dans les mêmes tables
    """
    import pandas as pd
    from sqlalchemy import text

    TABLE_MAP = {
        "infra":       "forecast_infra",
        "itsm":        "forecast_itsm",
        "cybersec":    "forecast_cybersec",
        "itam":        "forecast_itam",
        "apps":        "forecast_apps",
        "gouvernance": "forecast_gouvernance",
    }
    RENAME = {
        "ds": "DS", "yhat": "Yhat", "yhat_lower": "Yhat_Lower",
        "yhat_upper": "Yhat_Upper", "trend": "Trend",
        "trend_lower": "Trend_Lower", "trend_upper": "Trend_Upper",
        "rag_status": "Statut_RAG", "risk_score": "Risk_Score",
        "is_forecast": "Is_Forecast", "kpi": "KPI",
    }
    now = datetime.utcnow()

    for domain, table_name in TABLE_MAP.items():
        df: pd.DataFrame = results.get(domain)
        if df is None or df.empty:
            continue

        df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})
        df["Source_Modele"] = "Prophet"
        df["Date_Calcul"]   = now

        # DELETE par KPI — préserve les lignes ARIMA
        if "KPI" in df.columns:
            kpis = df["KPI"].unique().tolist()
            try:
                with engine.begin() as conn:
                    for kpi in kpis:
                        conn.execute(
                            text(f"DELETE FROM Gold.{table_name} WHERE KPI = :kpi"),
                            {"kpi": kpi},
                        )
            except Exception as exc:
                logger.warning("[Prophet] DELETE KPI KO sur Gold.%s : %s", table_name, exc)

        try:
            df.to_sql(table_name, engine, schema="Gold", if_exists="append", index=False)
            logger.info("[Prophet] ✅ %d lignes → Gold.%s", len(df), table_name)
        except Exception as exc:
            logger.warning("[Prophet] KO Gold.%s : %s", table_name, exc)

    # Alertes Prophet
    alerts = results.get("alerts")
    if alerts is not None and not alerts.empty:
        alerts = alerts.copy()
        alerts["Est_Active"]  = 1
        alerts["Date_Calcul"] = now
        try:
            alerts.to_sql("prophet_alerts", engine, schema="Gold",
                          if_exists="append", index=False)
            logger.info("[Prophet] ✅ %d alertes → Gold.prophet_alerts", len(alerts))
        except Exception as exc:
            logger.warning("[Prophet] KO Gold.prophet_alerts : %s", exc)


@task(
    name="ml_arima",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_arima(engine, dry_run: bool) -> dict:
    """
    Étape 2b — ARIMA Forecaster.

    Écrit Gold.forecast_itam, forecast_gouvernance,
    forecast_maintenance, forecast_parc_auto en append.
    Cohabite avec Prophet dans les mêmes tables via GroupKey.

    Retourne : {"predictions": int, "tables": dict, "status": str}
    """
    logger.info("[ML][ARIMA] ARIMA Forecaster")
    try:
        from ml.forecasting.arima_forecaster import ARIMAForecaster

        forecaster = ARIMAForecaster(engine=engine)
        results    = forecaster.run_all()
        written    = forecaster.save_results(results, dry_run=dry_run)
        nb         = sum(written.values())

        logger.info("[ML][ARIMA] ✅ %d prédictions sauvegardées", nb)
        return {"predictions": nb, "tables": written, "status": "ok"}

    except Exception as exc:
        logger.error("[ML][ARIMA] Échec : %s", exc, exc_info=True)
        return {"predictions": 0, "tables": {}, "status": "error", "error": str(exc)}


@task(
    name="ml_risk_score",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_risk_score(engine, dry_run: bool) -> dict:
    """
    Étape 3 — IT Risk Score.

    DOIT être exécuté après IF + ZScore + Prophet + ARIMA.
    Lit Gold.anomalies_detected + Gold.prophet_alerts + Gold.forecast_*.
    Calcule un score global 0-100 avec statut RAG par domaine.
    Écrit Gold.it_risk_score (DELETE + INSERT idempotent).

    Retourne : {"score": float, "rag": str, "status": str}
    """
    logger.info("[ML][RiskScore] IT Risk Score")

    if engine is None:
        logger.warning("[ML][RiskScore] SQL Server requis — ignoré (engine=None)")
        return {"score": None, "rag": None, "status": "skipped"}

    try:
        from ml.scoring.it_risk_score import compute_it_risk_score

        result = compute_it_risk_score(engine, date_key=date.today(), dry_run=dry_run)
        score  = result["Score_Global"]
        rag    = result["Statut_RAG_Global"]

        rag_icon = {"ROUGE": "🔴", "AMBRE": "🟡", "VERT": "🟢"}.get(rag, "⚪")
        logger.info("[ML][RiskScore] ✅ Score=%.1f %s %s", score, rag_icon, rag)

        return {"score": score, "rag": rag, "status": "ok"}

    except Exception as exc:
        logger.error("[ML][RiskScore] Échec : %s", exc, exc_info=True)
        return {"score": None, "rag": None, "status": "error", "error": str(exc)}


# =============================================================================
# PERSISTANCE DU RUN ML
# =============================================================================

def _save_ml_run(engine, run_id: str, started_at: datetime, results: dict) -> None:
    """Persiste le résumé du run ML dans Gold.pipeline_runs."""
    if engine is None:
        return
    import pandas as pd
    try:
        now = datetime.utcnow()
        row = {
            "Run_Id":                  run_id,
            "Triggered_By":            "ml_flow",
            "Started_At":              started_at,
            "Finished_At":             now,
            "Duration_Seconds":        int((now - started_at).total_seconds()),
            "Status":                  results.get("status", "unknown"),
            "Error_Message":           "; ".join(results.get("errors", [])) or None,
            "IF_Anomalies_Detectees":  results.get("if_anomalies", 0),
            "ZScore_Alertes_Generees": results.get("zscore_alertes", 0),
            "Prophet_Predictions":     results.get("prophet_predictions", 0),
            "ARIMA_Predictions":       results.get("arima_predictions", 0),
            "Risk_Score_Global":       results.get("risk_score"),
            "Risk_Score_RAG":          results.get("risk_rag"),
        }
        pd.DataFrame([row]).to_sql(
            "pipeline_runs", engine, schema="Gold",
            if_exists="append", index=False,
        )
        logger.info("[ML] Run %s → Gold.pipeline_runs (%s)", run_id, results.get("status"))
    except Exception as exc:
        logger.warning("[ML] Impossible d'enregistrer le run : %s", exc)


def _print_ml_report(run_id: str, started_at: datetime, results: dict) -> None:
    """Affiche le rapport final du run ML."""
    finished_at = datetime.utcnow()
    duration    = int((finished_at - started_at).total_seconds())
    status      = results.get("status", "unknown")
    rag         = results.get("risk_rag", "")
    rag_icon    = {"ROUGE": "🔴", "AMBRE": "🟡", "VERT": "🟢"}.get(rag, "⚪")
    status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(status, "⚪")

    print()
    print("═" * 68)
    print(f"  ML FLOW — Dashboard 360° Novec")
    print(f"  {status_icon} {status.upper():<10} │ Run: {run_id} │ Durée: {duration}s")
    print("═" * 68)
    print(f"  IF anomalies détectées   : {results.get('if_anomalies', 0):>8}")
    print(f"  ZScore alertes (R/A)     : {results.get('zscore_alertes', 0):>8}")
    print(f"  Prophet prédictions      : {results.get('prophet_predictions', 0):>8}")
    print(f"  ARIMA prédictions        : {results.get('arima_predictions', 0):>8}")
    score = results.get("risk_score")
    if score is not None:
        print(f"  IT Risk Score global     : {score:>6.1f}/100  {rag_icon} {rag}")
    errors = results.get("errors", [])
    if errors:
        print()
        print("  ── Erreurs non bloquantes ─────────────────────────────")
        for err in errors:
            print(f"  ⚠️  {err}")
    print("═" * 68)
    logger.info("[ml_flow] Run %s — %s — durée %ss", run_id, status.upper(), duration)


# =============================================================================
# FLOW PREFECT PRINCIPAL
# =============================================================================

@flow(
    name="novec_ml",
    description=(
        "ML Gold — Détection (IF + ZScore) → Prédiction (Prophet + ARIMA) → Scoring. "
        "Déclenché par trigger Prefect après silver_flow SUCCESS."
    ),
    log_prints=True,
)
def ml_flow(
    use_csv:       bool = False,
    dry_run:       bool = False,
    skip_forecast: bool = False,
    skip_scoring:  bool = False,
) -> dict:
    """
    Flow ML complet — Dashboard 360° Novec.

    Paramètres
    ----------
    use_csv       : lire depuis CSV Silver (sans SQL Server)
    dry_run       : exécute sans écrire en base
    skip_forecast : saute Prophet + ARIMA (détection uniquement)
    skip_scoring  : saute IT Risk Score (utile en test)

    Ordre strict — NE PAS MODIFIER :
      1a. Isolation Forest  (replace anomalies_detected)
      1b. ZScore            (append anomalies_detected)
      2a. Prophet           (DELETE/KPI + append forecast_*)
      2b. ARIMA             (append forecast_*)
      3.  IT Risk Score     (dépend de 1+2 — TOUJOURS EN DERNIER)
    """
# ── GARDE ANTI-DOUBLONS ──────────────────────────────────────────────
    if _should_skip_ml():
        return {
            "status": "skipped",
            "errors": ["duplicate_run"],
            "if_anomalies": 0, "zscore_alertes": 0,
            "prophet_predictions": 0, "arima_predictions": 0,
            "risk_score": None, "risk_rag": None,
        }    
    run_id     = str(uuid.uuid4())[:8]
    started_at = datetime.utcnow()
    errors     = []

    logger.info("═" * 68)
    logger.info("  ML FLOW — Dashboard 360° Novec")
    logger.info("  Run: %s | dry_run=%s | use_csv=%s | skip_forecast=%s | skip_scoring=%s",
                run_id, dry_run, use_csv, skip_forecast, skip_scoring)
    logger.info("═" * 68)

    engine = None
    if not use_csv:
        engine = get_db_engine()
        if engine is None:
            logger.warning("[ML] SQL Server indisponible — mode CSV activé")
            use_csv = True

    metrics = {
        "if_anomalies":        0,
        "zscore_alertes":      0,
        "prophet_predictions": 0,
        "arima_predictions":   0,
        "risk_score":          None,
        "risk_rag":            None,
    }

    # ── ÉTAPE 1 — DÉTECTION ──────────────────────────────────────────────────
    logger.info("[ML] ── ÉTAPE 1 — Détection des anomalies ──")

    # 1a — Isolation Forest (replace — vide anomalies_detected)
    res_if = task_isolation_forest(engine=engine, use_csv=use_csv, dry_run=dry_run)
    if res_if["status"] == "error":
        errors.append(f"IF: {res_if.get('error', 'inconnu')}")
    metrics["if_anomalies"] = res_if["anomalies"]

    # 1b — ZScore (append — complète anomalies_detected)
    res_zs = task_zscore(engine=engine, dry_run=dry_run)
    if res_zs["status"] == "error":
        errors.append(f"ZScore: {res_zs.get('error', 'inconnu')}")
    metrics["zscore_alertes"] = res_zs["alertes"]

    # ── ÉTAPE 2 — PRÉDICTION ─────────────────────────────────────────────────
    if skip_forecast:
        logger.info("[ML] ── ÉTAPE 2 ignorée (--skip-forecast) ──")
    else:
        logger.info("[ML] ── ÉTAPE 2 — Prédictions ──")

        # 2a — Prophet (DELETE/KPI + append)
        res_prophet = task_prophet(engine=engine, dry_run=dry_run)
        if res_prophet["status"] == "error":
            errors.append(f"Prophet: {res_prophet.get('error', 'inconnu')}")
        metrics["prophet_predictions"] = res_prophet["predictions"]

        # 2b — ARIMA (append — cohabite avec Prophet)
        res_arima = task_arima(engine=engine, dry_run=dry_run)
        if res_arima["status"] == "error":
            errors.append(f"ARIMA: {res_arima.get('error', 'inconnu')}")
        metrics["arima_predictions"] = res_arima["predictions"]

    # ── ÉTAPE 3 — SCORING ────────────────────────────────────────────────────
    if skip_scoring:
        logger.info("[ML] ── ÉTAPE 3 ignorée (--skip-scoring) ──")
    else:
        logger.info("[ML] ── ÉTAPE 3 — IT Risk Score ──")
        res_risk = task_risk_score(engine=engine, dry_run=dry_run)
        if res_risk["status"] == "error":
            errors.append(f"RiskScore: {res_risk.get('error', 'inconnu')}")
        metrics["risk_score"] = res_risk["score"]
        metrics["risk_rag"]   = res_risk["rag"]

    # ── FINALISATION ─────────────────────────────────────────────────────────
    status = "success" if not errors else "partial"
    results = {**metrics, "status": status, "errors": errors}

    if not dry_run:
        _save_ml_run(engine, run_id, started_at, results)

    _print_ml_report(run_id, started_at, results)
    return results


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dashboard 360° Novec — ML Flow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python ml_flow.py                       # run complet
  python ml_flow.py --dry-run             # sans écriture SQL
  python ml_flow.py --skip-scoring        # détection + forecast uniquement
  python ml_flow.py --skip-forecast       # détection uniquement
  python ml_flow.py --csv                 # lecture depuis CSV Silver
        """,
    )
    parser.add_argument("--dry-run",       action="store_true",
                        help="Exécute sans écrire en base")
    parser.add_argument("--csv",           action="store_true",
                        help="Lire depuis CSV Silver (sans SQL Server)")
    parser.add_argument("--skip-forecast", action="store_true",
                        help="Ignorer Prophet + ARIMA")
    parser.add_argument("--skip-scoring",  action="store_true",
                        help="Ignorer IT Risk Score")

    args = parser.parse_args()

    result = ml_flow(
        use_csv=args.csv,
        dry_run=args.dry_run,
        skip_forecast=args.skip_forecast,
        skip_scoring=args.skip_scoring,
    )

    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()