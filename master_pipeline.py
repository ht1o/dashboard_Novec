# =============================================================================
# master_pipeline.py
# Dashboard 360° Novec — Orchestrateur CLI de secours
#
# RÔLE APRÈS REFACTORING :
#   Orchestrateur de fallback — chaîne les 3 flows en séquence
#   sans dépendre du serveur Prefect ni des triggers automatiques.
#
#   Utile pour :
#     - --full-init au premier démarrage
#     - Tests locaux sans Prefect server
#     - Rejeu manuel d'un domaine spécifique
#     - CI/CD (pas de Prefect server en pipeline CI)
#
# LA LOGIQUE MÉTIER EST DANS :
#   bronze_flow.py  — génération Bronze (données simulées)
#   silver_flow.py  — validation + transformation Silver
#   ml_flow.py      — détection + prédiction + scoring Gold
#
# EN PRODUCTION :
#   serve.py orchestre automatiquement les 3 flows via Prefect
#   Automations (triggers). master_pipeline.py n'est pas utilisé
#   en production normale.
#
# Usage :
#   python master_pipeline.py --full-init
#   python master_pipeline.py --full-init --dry-run
#   python master_pipeline.py --full-init --backfill-days 30
#   python master_pipeline.py --bronze --daily
#   python master_pipeline.py --silver --monthly
#   python master_pipeline.py --ml
#   python master_pipeline.py --ml --skip-scoring
# =============================================================================

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

# ── Résolution des chemins ────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_LOGS = os.path.join(_ROOT, "logs")
os.environ["PREFECT_API_URL"] = ""          # désactive la connexion au serveur
os.environ["PREFECT_SERVER_ALLOW_EPHEMERAL_MODE"] = "1"  # mode local


if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ── Logging ───────────────────────────────────────────────────────────────────
Path(_LOGS).mkdir(parents=True, exist_ok=True)
_log_file = Path(_LOGS) / f"master_pipeline_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_log_file, encoding="utf-8"),
    ],
)
logger = logging.getLogger("master_pipeline")

# ── Import des flows ──────────────────────────────────────────────────────────
try:
    from flows.bronze_flow import (
        bronze_full_flow,
        bronze_infra_flow,
        bronze_hourly_flow,
        bronze_daily_flow,
        bronze_monthly_flow,
    )
    from flows.silver_flow import (
        silver_full_flow,
        silver_daily_flow,
        silver_monthly_flow,
    )
    from flows.ml_flow import ml_flow

    FLOWS_OK = True
except ImportError as exc:
    FLOWS_OK = False
    logger.error("Import des flows échoué : %s", exc)
    logger.error("Vérifiez que bronze_flow.py, silver_flow.py et ml_flow.py sont présents.")


# =============================================================================
# RAPPORT DE RUN GLOBAL
# =============================================================================

def _print_global_report(
    run_id:     str,
    started_at: datetime,
    flow_name:  str,
    results:    dict,
) -> None:
    """Rapport consolidé après un run complet."""
    finished_at = datetime.utcnow()
    duration    = int((finished_at - started_at).total_seconds())
    status      = results.get("status", "unknown")
    status_icon = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(status, "⚪")
    rag         = results.get("risk_rag", "")
    rag_icon    = {"ROUGE": "🔴", "AMBRE": "🟡", "VERT": "🟢"}.get(rag, "⚪")

    print()
    print("═" * 68)
    print(f"  {flow_name.upper()}")
    print(f"  {status_icon} {status.upper():<10} │ Run: {run_id} │ Durée: {duration}s")
    print("═" * 68)

    # Bronze
    if "bronze_rows" in results:
        print(f"  Lignes Bronze générées       : {results['bronze_rows']:>8}")

    # Silver
    if "silver_validated" in results:
        print(f"  Domaines Bronze validés      : {results['silver_validated']:>8}")
    if "silver_transformed" in results:
        print(f"  Domaines Silver transformés  : {results['silver_transformed']:>8}")

    # ML
    if results.get("if_anomalies") is not None:
        print(f"  IF anomalies détectées       : {results['if_anomalies']:>8}")
    if results.get("zscore_alertes") is not None:
        print(f"  ZScore alertes (R/A)         : {results['zscore_alertes']:>8}")
    if results.get("prophet_predictions") is not None:
        print(f"  Prophet prédictions          : {results['prophet_predictions']:>8}")
    if results.get("arima_predictions") is not None:
        print(f"  ARIMA prédictions            : {results['arima_predictions']:>8}")
    if results.get("risk_score") is not None:
        print(f"  IT Risk Score global         : "
              f"{results['risk_score']:>6.1f}/100  {rag_icon} {rag}")

    # Erreurs
    errors = results.get("errors", [])
    if errors:
        print()
        print("  ── Erreurs non bloquantes ─────────────────────────────")
        for err in errors:
            print(f"  ⚠️  {err}")

    print("═" * 68)
    logger.info("[%s] Run %s — %s — durée %ss",
                flow_name, run_id, status.upper(), duration)


# =============================================================================
# FULL INIT — Bronze + Silver + ML en séquence
# =============================================================================

def run_full_init(backfill_days: int, dry_run: bool) -> dict:
    """
    Initialisation complète — chaîne les 3 flows en séquence.

    Ordre :
      1. bronze_full_flow   — génère tous les domaines dans l'ordre causal
      2. silver_full_flow   — valide + transforme tous les domaines
      3. ml_flow            — détection + prédiction + scoring

    Un échec bloquant à une étape arrête les étapes suivantes.
    """
    run_id     = str(uuid.uuid4())[:8]
    started_at = datetime.utcnow()
    all_errors = []
    results    = {"status": "running", "errors": []}

    logger.info("═" * 68)
    logger.info("  MASTER PIPELINE — Full Init")
    logger.info("  Run: %s | backfill_days=%d | dry_run=%s", run_id, backfill_days, dry_run)
    logger.info("═" * 68)

    # ── ÉTAPE 1 — BRONZE ─────────────────────────────────────────────────────
    logger.info("[MASTER] ── ÉTAPE 1 — Génération Bronze ──")
    try:
        bronze_result = bronze_full_flow(backfill_days=backfill_days, dry_run=dry_run)
        results["bronze_rows"] = bronze_result.get("rows", 0)
        all_errors.extend(bronze_result.get("errors", []))
        logger.info("[MASTER] Bronze ✅ %d lignes", results["bronze_rows"])
    except Exception as exc:
        msg = f"Bronze flow critique : {exc}"
        logger.error("[MASTER] %s", msg, exc_info=True)
        results["status"] = "failed"
        results["errors"] = [msg]
        _print_global_report(run_id, started_at, "master_full_init", results)
        return results

    # ── ÉTAPE 2 — SILVER ─────────────────────────────────────────────────────
    logger.info("[MASTER] ── ÉTAPE 2 — Validation + Transformation Silver ──")
    try:
        silver_result = silver_full_flow(dry_run=dry_run)
        results["silver_validated"]   = silver_result.get("validated", 0)
        results["silver_transformed"] = silver_result.get("transformed", 0)
        all_errors.extend(silver_result.get("failed", []))

        if silver_result.get("status") == "failed":
            msg = f"Silver flow bloquant : {silver_result.get('error', 'inconnu')}"
            logger.error("[MASTER] %s", msg)
            results["status"] = "failed"
            results["errors"] = all_errors + [msg]
            _print_global_report(run_id, started_at, "master_full_init", results)
            return results

        logger.info("[MASTER] Silver ✅ %d transformés", results["silver_transformed"])
    except Exception as exc:
        msg = f"Silver flow critique : {exc}"
        logger.error("[MASTER] %s", msg, exc_info=True)
        results["status"] = "failed"
        results["errors"] = all_errors + [msg]
        _print_global_report(run_id, started_at, "master_full_init", results)
        return results

    # ── ÉTAPE 3 — ML ─────────────────────────────────────────────────────────
    logger.info("[MASTER] ── ÉTAPE 3 — Pipeline ML Gold ──")
    try:
        ml_result = ml_flow(dry_run=dry_run)
        results["if_anomalies"]        = ml_result.get("if_anomalies", 0)
        results["zscore_alertes"]      = ml_result.get("zscore_alertes", 0)
        results["prophet_predictions"] = ml_result.get("prophet_predictions", 0)
        results["arima_predictions"]   = ml_result.get("arima_predictions", 0)
        results["risk_score"]          = ml_result.get("risk_score")
        results["risk_rag"]            = ml_result.get("risk_rag")
        all_errors.extend(ml_result.get("errors", []))
        logger.info("[MASTER] ML ✅ Score=%.1f RAG=%s",
                    results.get("risk_score") or 0, results.get("risk_rag", "N/A"))
    except Exception as exc:
        msg = f"ML flow critique : {exc}"
        logger.error("[MASTER] %s", msg, exc_info=True)
        all_errors.append(msg)

    # ── FINALISATION ─────────────────────────────────────────────────────────
    results["status"] = "success" if not all_errors else "partial"
    results["errors"] = all_errors
    _print_global_report(run_id, started_at, "master_full_init", results)
    return results


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

def main() -> None:
    if not FLOWS_OK:
        print("❌ Flows non disponibles. Vérifiez bronze_flow.py, silver_flow.py, ml_flow.py")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Dashboard 360° Novec — Orchestrateur CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
MODE FULL INIT (recommandé au premier démarrage) :
  --full-init                     Chaîne Bronze + Silver + ML

MODE UNITAIRE (rejouer un flow seul) :
  --bronze --all                  Bronze complet
  --bronze --infra                Bronze infrastructure uniquement
  --bronze --daily                Bronze quotidien (ITSM + Cyber + Apps)
  --bronze --hourly               Bronze horaire (Parc Auto)
  --bronze --monthly              Bronze mensuel (ITAM + Maint + Gouv)
  --silver --all                  Silver complet
  --silver --daily                Silver quotidien
  --silver --monthly              Silver mensuel
  --ml                            Pipeline ML Gold complet

OPTIONS COMMUNES :
  --dry-run                       Sans écriture SQL
  --backfill-days N               Jours à rétro-générer (défaut : 1, full-init : 30)
  --skip-scoring                  Ignorer IT Risk Score (ML uniquement)
  --skip-forecast                 Ignorer Prophet + ARIMA (ML uniquement)

EXEMPLES :
  python master_pipeline.py --full-init
  python master_pipeline.py --full-init --dry-run
  python master_pipeline.py --full-init --backfill-days 30
  python master_pipeline.py --bronze --daily --dry-run
  python master_pipeline.py --silver --daily
  python master_pipeline.py --ml --skip-scoring

NOTE :
  En production, utilisez serve.py qui orchestre les flows
  automatiquement via les triggers Prefect.
        """,
    )

    # Mode principal
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--full-init", action="store_true",
                            help="Initialisation complète Bronze + Silver + ML")
    mode_group.add_argument("--bronze",    action="store_true",
                            help="Flow Bronze uniquement")
    mode_group.add_argument("--silver",    action="store_true",
                            help="Flow Silver uniquement")
    mode_group.add_argument("--ml",        action="store_true",
                            help="Flow ML Gold uniquement")

    # Sous-options Bronze / Silver
    parser.add_argument("--all",     action="store_true", help="Tous les domaines")
    parser.add_argument("--infra",   action="store_true", help="Infrastructure uniquement")
    parser.add_argument("--daily",   action="store_true", help="Cadence quotidienne")
    parser.add_argument("--hourly",  action="store_true", help="Cadence horaire (Parc Auto)")
    parser.add_argument("--monthly", action="store_true", help="Cadence mensuelle")

    # Options communes
    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--backfill-days", type=int, default=1, metavar="N")
    parser.add_argument("--skip-scoring",  action="store_true")
    parser.add_argument("--skip-forecast", action="store_true")

    args = parser.parse_args()

    # ── Full Init ─────────────────────────────────────────────────────────────
    if args.full_init:
        days = args.backfill_days if args.backfill_days > 1 else 30
        result = run_full_init(backfill_days=days, dry_run=args.dry_run)
        sys.exit(0 if result["status"] in ("success", "partial") else 1)

    # ── Bronze ────────────────────────────────────────────────────────────────
    if args.bronze:
        if args.all or not any([args.infra, args.daily, args.hourly, args.monthly]):
            bronze_full_flow(backfill_days=args.backfill_days, dry_run=args.dry_run)
        elif args.infra:
            bronze_infra_flow(backfill_days=args.backfill_days, dry_run=args.dry_run)
        elif args.daily:
            bronze_daily_flow(dry_run=args.dry_run)
        elif args.hourly:
            bronze_hourly_flow(dry_run=args.dry_run)
        elif args.monthly:
            bronze_monthly_flow(dry_run=args.dry_run)
        sys.exit(0)

    # ── Silver ────────────────────────────────────────────────────────────────
    if args.silver:
        if args.all or not any([args.daily, args.monthly]):
            result = silver_full_flow(dry_run=args.dry_run)
        elif args.daily:
            result = silver_daily_flow(dry_run=args.dry_run)
        elif args.monthly:
            result = silver_monthly_flow(dry_run=args.dry_run)
        else:
            result = silver_full_flow(dry_run=args.dry_run)
        sys.exit(0 if result.get("status") in ("success", "dry_run") else 1)

    # ── ML ────────────────────────────────────────────────────────────────────
    if args.ml:
        result = ml_flow(
            dry_run=args.dry_run,
            skip_forecast=args.skip_forecast,
            skip_scoring=args.skip_scoring,
        )
        sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()