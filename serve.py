# =============================================================================
# serve.py
# Dashboard 360° Novec — Orchestrateur Prefect Natif (refactorisé)
#
# Architecture après découpage :
#   bronze_flow.py  — génération Bronze (4 cadences)
#   silver_flow.py  — validation + transformation Silver
#   ml_flow.py      — détection + prédiction + scoring Gold
#
# serve.py enregistre les deployments Prefect.
#
# Les AUTOMATIONS (triggers) sont configurées directement depuis l'UI Prefect :
#   bronze_* SUCCESS → déclenche silver_flow
#   silver_* SUCCESS → déclenche ml_flow
#
# Cadences :
#   Mode RÉEL  : infra 30s | parc_auto 1h | daily 6h | monthly 1er/mois
#   Mode DÉMO  : infra 30s | parc_auto 60s | daily 2min | monthly 5min
#
# Silver et ML sont déclenchés par trigger — pas par schedule direct.
# Cela garantit qu'on ne transforme que des données fraîchement générées.
#
# Prérequis :
#   1. prefect server start
#   2. prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
#   3. python serve.py --demo
#
# Usage :
#   python serve.py --demo                    # Mode démo accéléré
#   python serve.py --demo --dry-run          # Démo sans écriture SQL
#   python serve.py --demo --skip-ml          # Démo sans ML Gold
#   python serve.py --demo --no-init          # Sans full_init au démarrage
#   python serve.py                           # Mode réel (fréquences métier)
# =============================================================================

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

# ── Résolution du chemin racine ───────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_FLOWS_PATH = os.path.join(_ROOT, "flows")
if _FLOWS_PATH not in sys.path:
    sys.path.insert(0, _FLOWS_PATH)

# ── Logging ───────────────────────────────────────────────────────────────────
_LOGS = os.path.join(_ROOT, "logs")
Path(_LOGS).mkdir(parents=True, exist_ok=True)

from novec_logger import setup_pipeline_logging, get_logger
setup_pipeline_logging()
logger = get_logger("serve")

# ── Import Prefect ────────────────────────────────────────────────────────────
try:
    from prefect import serve
    from prefect.schedules import Interval, Cron
    PREFECT_OK = True
except ImportError:
    PREFECT_OK = False
    logger.error("Prefect non installé → pip install prefect")

# ── Import des flows ──────────────────────────────────────────────────────────
try:
    from bronze_flow import (
        bronze_infra_flow,
        bronze_hourly_flow,
        bronze_daily_flow,
        bronze_monthly_flow,
        bronze_full_flow,
    )
    from silver_flow import (
        silver_daily_flow,
        silver_monthly_flow,
        silver_full_flow,
    )
    from ml_flow import ml_flow
    from data_simulation.config import get_db_engine
    FLOWS_OK = True
    logger.info("✅ Flows chargés : bronze_flow, silver_flow, ml_flow")
except ImportError as exc:
    FLOWS_OK = False
    logger.error("❌ Flows introuvables : %s", exc)


# =============================================================================
# FRÉQUENCES MÉTIER
# =============================================================================

# Mode RÉEL — fréquences entreprise Novec
INTERVALS_REAL = {
    "infra":    timedelta(seconds=30),
    "hourly":   timedelta(hours=1),
}
CRON_REAL = {
    "daily":   "0 */6 * * *",   # toutes les 6h
    "monthly": "0 2 1 * *",     # 02h00, 1er du mois
}

# Mode DÉMO — temps compressé pour simulation rapide
INTERVALS_DEMO = {
    "infra":   timedelta(seconds=30),
    "hourly":  timedelta(seconds=60),
    "daily":   timedelta(minutes=2),
    "monthly": timedelta(minutes=5),
}


# =============================================================================
# VÉRIFICATION PREFECT SERVER
# =============================================================================

def _check_prefect_server() -> bool:
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:4200/api/health", timeout=3)
        if r.status_code == 200:
            logger.info("✅ Prefect server accessible — http://127.0.0.1:4200")
            return True
        logger.error("❌ Prefect server répond %d", r.status_code)
        return False
    except Exception:
        logger.error(
            "❌ Prefect server inaccessible.\n"
            "   Lance d'abord : prefect server start"
        )
        return False


# =============================================================================
# VÉRIFICATION BRONZE — PREMIER DÉMARRAGE
# =============================================================================

def _is_bronze_empty(engine) -> bool:
    """
    Retourne True si Bronze est vide ou inaccessible → full_init nécessaire.
    Vérifie 3 tables critiques pour éviter les faux négatifs d'init partielle.
    """
    if engine is None:
        return True
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            counts = {}
            for table in ["staging_infrastructure", "staging_itsm_tickets", "staging_itam"]:
                try:
                    counts[table] = conn.execute(
                        text(f"SELECT COUNT(*) FROM Bronze.{table}")
                    ).scalar()
                except Exception:
                    counts[table] = 0

            logger.info("[INIT] Bronze counts : %s", counts)
            # Vide si toutes les tables critiques sont vides
            return all(c == 0 for c in counts.values())
    except Exception as exc:
        logger.warning("[INIT] Vérification Bronze impossible (%s) → supposé vide", exc)
        return True


# =============================================================================
# POINT D'ENTRÉE PRINCIPAL
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dashboard 360° Novec — Orchestrateur Prefect Natif",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prérequis (dans l'ordre) :
  1. prefect server start                              (Terminal 1)
  2. prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
  3. python serve.py --demo                            (Terminal 2)

     → Ouvre http://localhost:4200 pour voir les runs en temps réel

Exemples :
  python serve.py --demo                  # Démo : 10s/30s/2min/5min
  python serve.py --demo --dry-run        # Démo sans écriture SQL
  python serve.py --demo --skip-ml        # Démo sans ML Gold
  python serve.py --demo --no-init        # Démo sans full_init
  python serve.py                         # Prod : fréquences réelles
        """,
    )
    parser.add_argument("--demo",          action="store_true",
                        help="Mode démo : fréquences accélérées")
    parser.add_argument("--dry-run",       action="store_true",
                        help="Sans écriture SQL")
    parser.add_argument("--no-init",       action="store_true",
                        help="Ne pas lancer full_init au démarrage")
    parser.add_argument("--skip-ml",       action="store_true",
                        help="Sans pipeline ML Gold")
    parser.add_argument("--backfill-days", type=int, default=30, metavar="N",
                        help="Jours d'historique pour full_init (défaut: 30)")

    args = parser.parse_args()

    # ── Vérifications prérequis ───────────────────────────────────────────────
    if not PREFECT_OK:
        print("❌ Installez Prefect : pip install prefect")
        sys.exit(1)

    if not FLOWS_OK:
        print("❌ Flows introuvables — vérifiez bronze_flow.py, silver_flow.py, ml_flow.py")
        sys.exit(1)

    if not _check_prefect_server():
        print("\n  Lance d'abord : prefect server start\n")
        sys.exit(1)

    mode_label = "DÉMO ACCÉLÉRÉ" if args.demo else "MODE RÉEL"
    logger.info("═" * 60)
    logger.info("  serve.py — Dashboard 360° Novec — %s", mode_label)
    logger.info("  dry_run=%s | skip_ml=%s | backfill_days=%d",
                args.dry_run, args.skip_ml, args.backfill_days)
    logger.info("═" * 60)

    # ── Full Init si Bronze vide ──────────────────────────────────────────────
    if not args.no_init:
        engine = None if args.dry_run else get_db_engine()
        if _is_bronze_empty(engine):
            logger.info("[INIT] Bronze vide → lancement bronze_full_flow + silver + ml")
            bronze_full_flow(backfill_days=args.backfill_days, dry_run=args.dry_run)
            silver_full_flow(dry_run=args.dry_run)
            if not args.skip_ml:
                ml_flow(dry_run=args.dry_run)
            logger.info("[INIT] ✅ Full init terminé")
        else:
            logger.info("[INIT] Bronze déjà peuplé → skip full_init")
    else:
        logger.info("[INIT] --no-init : full_init ignoré")

    # ── Sélection des intervalles ─────────────────────────────────────────────
    intervals = INTERVALS_DEMO if args.demo else INTERVALS_REAL

    # ── Construction des deployments Bronze ───────────────────────────────────

    # DEPLOYMENT 1 — Infrastructure (30s réel / 10s démo)
    infra_deployment = bronze_infra_flow.to_deployment(
        name="novec-bronze-infra",
        interval=intervals["infra"],
        tags=["novec", "bronze", "infrastructure", "tier1"],
        description=(
            "TIER 1 — Génération Bronze infrastructure "
            "(simulation capteurs Zabbix 30s)."
        ),
        parameters={"backfill_days": 0, "dry_run": args.dry_run},
    )

    # DEPLOYMENT 2 — Parc Auto (1h réel / 30s démo)
    hourly_deployment = bronze_hourly_flow.to_deployment(
        name="novec-bronze-hourly",
        interval=intervals["hourly"],
        tags=["novec", "bronze", "parc_auto", "tier2"],
        description=(
            "TIER 2 — Bronze Parc Auto (télématique flotte). "
            "Cadence : 1h réel / 30s démo."
        ),
        parameters={"dry_run": args.dry_run},
    )

    # DEPLOYMENT 3 — Daily Bronze (6h réel / 2min démo)
    if args.demo:
        daily_bronze_deployment = bronze_daily_flow.to_deployment(
            name="novec-bronze-daily",
            interval=intervals["daily"],
            tags=["novec", "bronze", "daily", "tier3"],
            description=(
                "TIER 3 DÉMO — Bronze ITSM + Cyber + Apps. "
                "Cadence démo : 2min."
            ),
            parameters={"dry_run": args.dry_run},
        )
    else:
        daily_bronze_deployment = bronze_daily_flow.to_deployment(
            name="novec-bronze-daily",
            cron=CRON_REAL["daily"],
            timezone="Africa/Casablanca",
            tags=["novec", "bronze", "daily", "tier3"],
            description=(
                "TIER 3 PROD — Bronze ITSM + Cyber + Apps. "
                "Cron : toutes les 6h."
            ),
            parameters={"dry_run": args.dry_run},
        )

    # DEPLOYMENT 4 — Monthly Bronze (1er/mois réel / 5min démo)
    if args.demo:
        monthly_bronze_deployment = bronze_monthly_flow.to_deployment(
            name="novec-bronze-monthly",
            interval=intervals["monthly"],
            tags=["novec", "bronze", "monthly", "tier4"],
            description=(
                "TIER 4 DÉMO — Bronze ITAM + Maintenance + Gouvernance. "
                "Cadence démo : 5min."
            ),
            parameters={"dry_run": args.dry_run},
        )
    else:
        monthly_bronze_deployment = bronze_monthly_flow.to_deployment(
            name="novec-bronze-monthly",
            cron=CRON_REAL["monthly"],
            timezone="Africa/Casablanca",
            tags=["novec", "bronze", "monthly", "tier4"],
            description=(
                "TIER 4 PROD — Bronze ITAM + Maintenance + Gouvernance. "
                "Cron : 02h00 le 1er du mois."
            ),
            parameters={"dry_run": args.dry_run},
        )

    # ── Deployments Silver — déclenchés par trigger depuis l'UI Prefect ───────

    silver_daily_deployment = silver_daily_flow.to_deployment(
        name="novec-silver-daily",
        tags=["novec", "silver", "daily"],
        description=(
            "Silver quotidien — Validation + Transformation "
            "(Infrastructure, ITSM, Cyber, Apps, Parc Auto). "
            "Déclenché par automation Prefect : Bronze → Silver."
        ),
        parameters={"dry_run": args.dry_run},
    )

    silver_monthly_deployment = silver_monthly_flow.to_deployment(
        name="novec-silver-monthly",
        tags=["novec", "silver", "monthly"],
        description=(
            "Silver mensuel — Validation + Transformation "
            "(ITAM, Maintenance, Gouvernance). "
            "Déclenché par automation Prefect : Bronze → Silver."
        ),
        parameters={"dry_run": args.dry_run},
    )

    # ── Deployment ML — déclenché par automation Prefect Silver → ML ─────────

    ml_deployment = ml_flow.to_deployment(
        name="novec-ml",
        tags=["novec", "gold", "ml"],
        description=(
            "ML Gold — IF + ZScore + Prophet + ARIMA + Risk Score. "
            "Déclenché par automation Prefect : Silver → ML."
        ),
        parameters={
            "dry_run":       args.dry_run,
            "skip_forecast": False,
            "skip_scoring":  args.skip_ml,
        },
    )

    # ── Résumé avant lancement ────────────────────────────────────────────────
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print(f"║   Dashboard 360° Novec — Prefect Serve  [{mode_label:^20}] ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  DEPLOYMENTS BRONZE (schedulés)                                  ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    if args.demo:
        print("║  TIER 1 🔵 Bronze Infrastructure → toutes les 30s               ║")
        print("║  TIER 2 🟠 Bronze Parc Auto       → toutes les 60s               ║")
        print("║  TIER 3 🟣 Bronze ITSM+Cyber+Apps → toutes les 2min              ║")
        print("║  TIER 4 🟤 Bronze ITAM+Maint+Gouv → toutes les 5min              ║")
    else:
        print("║  TIER 1 🔵 Bronze Infrastructure → toutes les 30s                ║")
        print("║  TIER 2 🟠 Bronze Parc Auto       → toutes les 1h                ║")
        print("║  TIER 3 🟣 Bronze ITSM+Cyber+Apps → toutes les 6h                ║")
        print("║  TIER 4 🟤 Bronze ITAM+Maint+Gouv → 1er du mois à 02h00          ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  DEPLOYMENTS SILVER + ML (déclenchés par automation Prefect UI)  ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  🟢 Silver Daily   → après Bronze daily/hourly/infra SUCCESS      ║")
    print("║  🟢 Silver Monthly → après Bronze monthly SUCCESS                 ║")
    print("║  🔶 ML Gold        → après Silver daily/monthly SUCCESS            ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  CHAÎNE AUTOMATIQUE                                               ║")
    print("║  Bronze → automation → Silver → automation → ML                  ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  📊 Prefect UI : http://localhost:4200                            ║")
    print("║  ⛔  Arrêt     : Ctrl+C                                           ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    logger.info("🟢 Lancement de serve() — 7 deployments actifs")

    # ── SERVE — lance tous les deployments ────────────────────────────────────
    serve(
        infra_deployment,
        hourly_deployment,
        daily_bronze_deployment,
        monthly_bronze_deployment,
        silver_daily_deployment,
        silver_monthly_deployment,
        ml_deployment,
        limit=20,
    )


if __name__ == "__main__":
    main()