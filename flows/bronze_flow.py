# =============================================================================
# bronze_flow.py
# Dashboard 360° Novec — Flow Prefect : Génération Bronze
#
# Responsabilité UNIQUE : générer les données simulées et les insérer
# dans les tables Bronze.staging_* de SQL Server (ou CSV en fallback).
#
# Respecte l'ordre causal OrchestratorSimulator :
#   infra → itsm → cyber → apps → itam → parc_auto → maintenance → gouvernance
#
# 4 cadences métier exposées comme flows Prefect distincts :
#   bronze_infra_flow    — backfill infrastructure (30s réel / démo)
#   bronze_daily_flow    — ITSM + Cyber + Apps     (6h réel / 2min démo)
#   bronze_hourly_flow   — Parc Auto               (1h réel / 30s démo)
#   bronze_monthly_flow  — ITAM + Maintenance + Gouvernance (mensuel / 5min démo)
#
# Déclenchement automatique :
#   Chaque flow publie son statut dans Prefect.
#   silver_flow.py est déclenché via Automation Prefect quand
#   l'un des flows Bronze se termine en SUCCESS.
#
# Usage CLI :
#   python bronze_flow.py --infra
#   python bronze_flow.py --daily
#   python bronze_flow.py --hourly
#   python bronze_flow.py --monthly
#   python bronze_flow.py --all              # full init (ordre causal complet)
#   python bronze_flow.py --all --dry-run
#   python bronze_flow.py --infra --backfill-days 30
# =============================================================================

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Résolution des chemins ────────────────────────────────────────────────────
_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_SIM = os.path.join(_ROOT, "data_simulation")
_LOGS     = os.path.join(_ROOT, "logs")

for _p in [_ROOT, _DATA_SIM]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Logging ───────────────────────────────────────────────────────────────────
from novec_logger import get_logger
logger = get_logger("bronze")

# ── Config DB ─────────────────────────────────────────────────────────────────
try:
    from config import get_db_engine
except ImportError:
    def get_db_engine():
        return None


def _read_itsm_csat_from_silver() -> dict:
    """
    Lit le CSAT mensuel depuis Silver.silver_itsm au lieu de régénérer
    30 jours d'infra + itsm en mémoire.
    Retourne un dict vide si Silver n'est pas encore peuplé (premier démarrage).
    """
    try:
        engine = get_db_engine()
        if engine is None:
            return {}
        from sqlalchemy import text
        with engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT FORMAT(Date_Ticket, 'yyyy-MM') AS mois, AVG(CSAT) AS csat_moyen "
                "FROM Silver.silver_itsm "
                "GROUP BY FORMAT(Date_Ticket, 'yyyy-MM')"
            )).fetchall()
        result = {r.mois: float(r.csat_moyen) for r in rows}
        logger.info("[BRONZE][monthly] CSAT mensuel lu depuis Silver : %d mois", len(result))
        return result
    except Exception as exc:
        logger.warning("[BRONZE][monthly] CSAT depuis Silver KO (%s) — gouvernance sans corrélation ITSM", exc)
        return {}


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


# =============================================================================
# FABRIQUE D'ORCHESTRATEUR
# =============================================================================

def _make_orchestrator(backfill_days: int = 1):
    """
    Instancie OrchestratorSimulator sur [now - backfill_days, now].
    Import lazy pour éviter les imports circulaires.
    """
    import importlib.util

    if "run_simulation" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "run_simulation",
            os.path.join(_DATA_SIM, "run_simulation.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        sys.modules["run_simulation"] = mod

    mod = sys.modules["run_simulation"]
    end_date   = datetime.now()
    start_date = end_date - timedelta(days=backfill_days)
    return mod.OrchestratorSimulator(start_date, end_date)


# =============================================================================
# TÂCHES ATOMIQUES — une par générateur
# =============================================================================

@task(
    name="gen_infrastructure",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_infra(dry_run: bool, backfill_days: int = 1) -> dict:
    """
    Génère Bronze.staging_infrastructure.

    Si backfill_days=0 : génère 1 seul batch (dernière heure) — mode streaming.
    Si backfill_days>0 : génère N jours complets — mode backfill/init.

    Retourne :
        {
          "rows": int,
          "infra_daily_anomalies": dict[str, int]  # pont causal → ITSM / Apps
        }
    """
    import pandas as pd
    
    if backfill_days == 0:
        logger.info("[BRONZE][infra] Mode streaming — 1 batch (dernière heure)")
    else:
        logger.info("[BRONZE][infra] Backfill %d jour(s)", backfill_days)

    if dry_run:
        logger.info("[BRONZE][infra] dry-run — pas d'écriture")
        return {"rows": -1, "infra_daily_anomalies": {}}

    from generators.gen_infra import generate_infrastructure

    if backfill_days == 0:
        # Mode streaming : 1 seule heure (now-1h → now)
        end_date   = datetime.now()
        start_date = end_date - timedelta(hours=1)
        daterange  = pd.date_range(start=start_date, end=end_date, freq='h')
    else:
        # Mode backfill : N jours complets
        end_date   = datetime.now()
        start_date = end_date - timedelta(days=backfill_days)
        daterange  = pd.date_range(start=start_date, end=end_date, freq='h')

    df_infra = generate_infrastructure(daterange, start_date)

    # Extraction des anomalies pour les corrélations causales
    orch = _make_orchestrator(max(backfill_days, 1))
    infra_daily_anomalies = orch._extract_daily_anomalies(df_infra)

    # Sauvegarde
    orch.save_data(df_infra, "infrastructure")

    nb = len(df_infra)
    logger.info("[BRONZE][infra] ✅ %d lignes → Bronze.staging_infrastructure", nb)
    return {"rows": nb, "infra_daily_anomalies": infra_daily_anomalies}



@task(
    name="gen_itsm",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_itsm(dry_run: bool, infra_daily_anomalies: dict) -> dict:
    """
    Génère Bronze.staging_itsm_tickets.
    Consomme infra_daily_anomalies pour les corrélations causales.

    Retourne :
        {
          "rows": int,
          "itsm_monthly_csat": dict[str, float]   # pont causal → Gouvernance
        }
    """
    logger.info("[BRONZE][itsm] Génération journalière")

    if dry_run:
        logger.info("[BRONZE][itsm] dry-run — pas d'écriture")
        return {"rows": -1, "itsm_monthly_csat": {}}

    orch = _make_orchestrator(backfill_days=1)
    from generators.gen_itsm import generate_itsm

    df_itsm = generate_itsm(orch.daterange_days, infra_daily_anomalies)
    itsm_monthly_csat = orch._extract_monthly_csat(df_itsm)
    orch.save_data(df_itsm, "itsm_tickets")

    nb = len(df_itsm)
    logger.info("[BRONZE][itsm] ✅ %d lignes → Bronze.staging_itsm_tickets", nb)
    return {"rows": nb, "itsm_monthly_csat": itsm_monthly_csat}


@task(
    name="gen_cybersecurity",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_cyber(dry_run: bool) -> int:
    """Génère Bronze.staging_cybersecurity (indépendant)."""
    logger.info("[BRONZE][cyber] Génération journalière")

    if dry_run:
        logger.info("[BRONZE][cyber] dry-run — pas d'écriture")
        return -1

    orch = _make_orchestrator(backfill_days=1)
    from generators.gen_securite import generate_cyber

    df = generate_cyber(orch.daterange_days, orch.start_date)
    orch.save_data(df, "cybersecurity")

    nb = len(df)
    logger.info("[BRONZE][cyber] ✅ %d lignes → Bronze.staging_cybersecurity", nb)
    return nb


@task(
    name="gen_applications",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_apps(dry_run: bool, infra_daily_anomalies: dict) -> int:
    """
    Génère Bronze.staging_applications.
    Consomme infra_daily_anomalies pour la cascade Infra → Apps.
    """
    logger.info("[BRONZE][apps] Génération journalière")

    if dry_run:
        logger.info("[BRONZE][apps] dry-run — pas d'écriture")
        return -1

    orch = _make_orchestrator(backfill_days=1)
    from generators.gen_applications import generate_applications

    df = generate_applications(orch.daterange_days, orch.start_date, infra_daily_anomalies)
    orch.save_data(df, "applications")

    nb = len(df)
    logger.info("[BRONZE][apps] ✅ %d lignes → Bronze.staging_applications", nb)
    return nb


@task(
    name="gen_parc_auto",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_parc_auto(dry_run: bool) -> int:
    """Génère Bronze.staging_parc_auto (indépendant, cadence horaire)."""
    logger.info("[BRONZE][parc_auto] Génération horaire")

    if dry_run:
        logger.info("[BRONZE][parc_auto] dry-run — pas d'écriture")
        return -1

    orch = _make_orchestrator(backfill_days=1)
    from generators.gen_facility import generate_fleet

    df = generate_fleet(orch.daterange_days)
    orch.save_data(df, "parc_auto")

    nb = len(df)
    logger.info("[BRONZE][parc_auto] ✅ %d lignes → Bronze.staging_parc_auto", nb)
    return nb


@task(
    name="gen_itam",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_itam(dry_run: bool) -> int:
    """Génère Bronze.staging_itam (indépendant, cadence mensuelle)."""
    logger.info("[BRONZE][itam] Génération mensuelle")

    if dry_run:
        logger.info("[BRONZE][itam] dry-run — pas d'écriture")
        return -1

    orch = _make_orchestrator(backfill_days=30)
    from generators.gen_itam import generate_itam

    df = generate_itam(orch.daterange_months)
    orch.save_data(df, "itam")

    nb = len(df)
    logger.info("[BRONZE][itam] ✅ %d lignes → Bronze.staging_itam", nb)
    return nb


@task(
    name="gen_maintenance",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_maintenance(dry_run: bool) -> int:
    """Génère Bronze.staging_maintenance (indépendant, cadence mensuelle)."""
    logger.info("[BRONZE][maintenance] Génération mensuelle")

    if dry_run:
        logger.info("[BRONZE][maintenance] dry-run — pas d'écriture")
        return -1

    orch = _make_orchestrator(backfill_days=30)
    from generators.gen_maintenance import generate_maintenance

    df = generate_maintenance(orch.daterange_months)
    orch.save_data(df, "maintenance")

    nb = len(df)
    logger.info("[BRONZE][maintenance] ✅ %d lignes → Bronze.staging_maintenance", nb)
    return nb


@task(
    name="gen_gouvernance",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_gen_gouvernance(dry_run: bool, itsm_monthly_csat: dict) -> int:
    """
    Génère Bronze.staging_gouvernance (cadence mensuelle).
    Consomme itsm_monthly_csat pour la corrélation ITSM → Gouvernance.
    """
    logger.info("[BRONZE][gouvernance] Génération mensuelle")

    if dry_run:
        logger.info("[BRONZE][gouvernance] dry-run — pas d'écriture")
        return -1

    orch = _make_orchestrator(backfill_days=30)
    from generators.gen_finance import generate_gouvernance

    df = generate_gouvernance(orch.daterange_months, itsm_monthly_csat)
    orch.save_data(df, "gouvernance")

    nb = len(df)
    logger.info("[BRONZE][gouvernance] ✅ %d lignes → Bronze.staging_gouvernance", nb)
    return nb


# =============================================================================
# FLOWS PREFECT — 4 cadences métier
# =============================================================================

@flow(
    name="novec_bronze_infra",
    description="Bronze — Infrastructure (simulation capteurs Zabbix 30s). Cadence : 30s réel / 10s démo.",
    log_prints=True,
)
def bronze_infra_flow(backfill_days: int = 1, dry_run: bool = False) -> dict:
    """
    Flow TIER 1 — Infrastructure uniquement.
    Retourne le résultat de task_gen_infra (inclut infra_daily_anomalies)
    pour que silver_flow puisse être chaîné via trigger Prefect.
    """
    logger.info("══ BRONZE FLOW — Infrastructure | backfill=%d | dry_run=%s", backfill_days, dry_run)
    result = task_gen_infra(dry_run=dry_run, backfill_days=backfill_days)
    logger.info("══ BRONZE FLOW — Infrastructure ✅ %s lignes", result["rows"])
    return result


@flow(
    name="novec_bronze_hourly",
    description="Bronze — Parc Auto (télématique flotte). Cadence : 1h réel / 30s démo.",
    log_prints=True,
)
def bronze_hourly_flow(dry_run: bool = False) -> int:
    """Flow TIER 2 — Parc Auto uniquement."""
    logger.info("══ BRONZE FLOW — Parc Auto | dry_run=%s", dry_run)
    nb = task_gen_parc_auto(dry_run=dry_run)
    logger.info("══ BRONZE FLOW — Parc Auto ✅ %s lignes", nb)
    return nb


@flow(
    name="novec_bronze_daily",
    description="Bronze — ITSM + Cybersécurité + Applications. Cadence : 6h réel / 2min démo.",
    log_prints=True,
)
def bronze_daily_flow(dry_run: bool = False) -> dict:
    """
    Flow TIER 3 — Domaines journaliers.

    Ordre causal respecté :
      1. infra  → fournit infra_daily_anomalies (re-généré en mémoire, NON sauvegardé)
      2. itsm   → consomme infra_daily_anomalies
      3. cyber  → indépendant
      4. apps   → consomme infra_daily_anomalies

    L'infra est re-générée en mémoire uniquement pour les corrélations causales.
    La sauvegarde Bronze infra est gérée par bronze_infra_flow (cadence 30s).
    """
    logger.info("══ BRONZE FLOW — Daily (ITSM + Cyber + Apps) | dry_run=%s", dry_run)

    # Infra en mémoire pour les corrélations — pas de sauvegarde ici
    if not dry_run:
        orch = _make_orchestrator(backfill_days=2)   # ← 2 jours garantit au moins 1 jour complet
        from generators.gen_infra import generate_infrastructure
        df_infra = generate_infrastructure(orch.daterange_hours, orch.start_date)
        infra_daily_anomalies = orch._extract_daily_anomalies(df_infra)
        nb_jours = len(infra_daily_anomalies)
        if nb_jours == 0:
            logger.warning("[BRONZE][daily] Aucune anomalie infra extraite — corrélations ITSM/Apps désactivées pour ce run")
        else:
            logger.info("[BRONZE][daily] Anomalies infra extraites : %d jour(s)", nb_jours)
    else:
        infra_daily_anomalies = {}

    result_itsm  = task_gen_itsm(dry_run=dry_run, infra_daily_anomalies=infra_daily_anomalies)
    nb_cyber     = task_gen_cyber(dry_run=dry_run)
    nb_apps      = task_gen_apps(dry_run=dry_run, infra_daily_anomalies=infra_daily_anomalies)

    total = (
        result_itsm["rows"]
        + (nb_cyber if nb_cyber > 0 else 0)
        + (nb_apps if nb_apps > 0 else 0)
    )
    logger.info("══ BRONZE FLOW — Daily ✅ %d lignes totales", total)
    return {"rows": total, "itsm_monthly_csat": result_itsm["itsm_monthly_csat"]}


@flow(
    name="novec_bronze_monthly",
    description="Bronze — ITAM + Maintenance + Gouvernance. Cadence : 1er du mois / 5min démo.",
    log_prints=True,
)
def bronze_monthly_flow(dry_run: bool = False) -> int:
    """
    Flow TIER 4 — Domaines mensuels.

    Ordre causal respecté :
      1. itsm (Silver) → fournit itsm_monthly_csat (lu depuis Silver.silver_itsm)
      2. itam          → indépendant
      3. maintenance   → indépendant
      4. gouvernance   → consomme itsm_monthly_csat
    """
    logger.info("══ BRONZE FLOW — Monthly (ITAM + Maintenance + Gouvernance) | dry_run=%s", dry_run)

    # Lecture du CSAT mensuel depuis Silver — pas de régénération en mémoire
    if not dry_run:
        itsm_monthly_csat = _read_itsm_csat_from_silver()
    else:
        itsm_monthly_csat = {}

    nb_itam        = task_gen_itam(dry_run=dry_run)
    nb_maintenance = task_gen_maintenance(dry_run=dry_run)
    nb_gouvernance = task_gen_gouvernance(dry_run=dry_run, itsm_monthly_csat=itsm_monthly_csat)

    total = sum(n for n in [nb_itam, nb_maintenance, nb_gouvernance] if n > 0)
    logger.info("══ BRONZE FLOW — Monthly ✅ %d lignes totales", total)
    return total


@flow(
    name="novec_bronze_full",
    description="Bronze — Génération complète tous domaines (full init). Respecte l'ordre causal.",
    log_prints=True,
)
def bronze_full_flow(backfill_days: int = 30, dry_run: bool = False) -> dict:
    """
    Flow FULL INIT — Tous les domaines dans l'ordre causal complet.
    Utilisé au premier démarrage ou pour un rejeu complet.

    Ordre causal strict (identique à OrchestratorSimulator.run()) :
      1. infra       → source des anomalies
      2. itsm        → consomme infra_daily_anomalies
      3. cyber       → indépendant
      4. apps        → consomme infra_daily_anomalies
      5. itam        → indépendant
      6. parc_auto   → indépendant
      7. maintenance → indépendant
      8. gouvernance → consomme itsm_monthly_csat
    """
    logger.info("══ BRONZE FLOW — Full Init | backfill=%d | dry_run=%s", backfill_days, dry_run)

    total_rows = 0
    errors     = []

    # 1. Infrastructure
    try:
        result_infra = task_gen_infra(dry_run=dry_run, backfill_days=backfill_days)
        infra_daily_anomalies = result_infra["infra_daily_anomalies"]
        total_rows += max(result_infra["rows"], 0)
    except Exception as exc:
        logger.error("[BRONZE][full] infra échouée : %s", exc)
        errors.append(str(exc))
        infra_daily_anomalies = {}

    # 2. ITSM
    try:
        result_itsm = task_gen_itsm(dry_run=dry_run, infra_daily_anomalies=infra_daily_anomalies)
        itsm_monthly_csat = result_itsm["itsm_monthly_csat"]
        total_rows += max(result_itsm["rows"], 0)
    except Exception as exc:
        logger.error("[BRONZE][full] itsm échouée : %s", exc)
        errors.append(str(exc))
        itsm_monthly_csat = {}

    # 3. Cyber
    try:
        nb = task_gen_cyber(dry_run=dry_run)
        total_rows += max(nb, 0)
    except Exception as exc:
        logger.error("[BRONZE][full] cyber échouée : %s", exc)
        errors.append(str(exc))

    # 4. Applications
    try:
        nb = task_gen_apps(dry_run=dry_run, infra_daily_anomalies=infra_daily_anomalies)
        total_rows += max(nb, 0)
    except Exception as exc:
        logger.error("[BRONZE][full] apps échouée : %s", exc)
        errors.append(str(exc))

    # 5. ITAM
    try:
        nb = task_gen_itam(dry_run=dry_run)
        total_rows += max(nb, 0)
    except Exception as exc:
        logger.error("[BRONZE][full] itam échouée : %s", exc)
        errors.append(str(exc))

    # 6. Parc Auto
    try:
        nb = task_gen_parc_auto(dry_run=dry_run)
        total_rows += max(nb, 0)
    except Exception as exc:
        logger.error("[BRONZE][full] parc_auto échouée : %s", exc)
        errors.append(str(exc))

    # 7. Maintenance
    try:
        nb = task_gen_maintenance(dry_run=dry_run)
        total_rows += max(nb, 0)
    except Exception as exc:
        logger.error("[BRONZE][full] maintenance échouée : %s", exc)
        errors.append(str(exc))

    # 8. Gouvernance
    try:
        nb = task_gen_gouvernance(dry_run=dry_run, itsm_monthly_csat=itsm_monthly_csat)
        total_rows += max(nb, 0)
    except Exception as exc:
        logger.error("[BRONZE][full] gouvernance échouée : %s", exc)
        errors.append(str(exc))

    status = "success" if not errors else "partial"
    logger.info("══ BRONZE FLOW — Full Init %s | %d lignes | %d erreurs",
                status.upper(), total_rows, len(errors))
    return {"rows": total_rows, "status": status, "errors": errors}


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dashboard 360° Novec — Bronze Flow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Flows disponibles :
  --infra               Infrastructure (backfill)
  --hourly              Parc Auto (cadence horaire)
  --daily               ITSM + Cyber + Apps (cadence quotidienne)
  --monthly             ITAM + Maintenance + Gouvernance (cadence mensuelle)
  --all                 Full init (tous les domaines, ordre causal complet)

Options :
  --dry-run             Sans écriture SQL
  --backfill-days N     Jours à rétro-générer pour --infra et --all (défaut : 1)

Exemples :
  python bronze_flow.py --all --backfill-days 30
  python bronze_flow.py --daily --dry-run
  python bronze_flow.py --infra --backfill-days 7
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--infra",   action="store_true")
    group.add_argument("--hourly",  action="store_true")
    group.add_argument("--daily",   action="store_true")
    group.add_argument("--monthly", action="store_true")
    group.add_argument("--all",     action="store_true")

    parser.add_argument("--dry-run",       action="store_true")
    parser.add_argument("--backfill-days", type=int, default=1, metavar="N")

    args = parser.parse_args()

    if args.infra:
        bronze_infra_flow(backfill_days=args.backfill_days, dry_run=args.dry_run)
    elif args.hourly:
        bronze_hourly_flow(dry_run=args.dry_run)
    elif args.daily:
        bronze_daily_flow(dry_run=args.dry_run)
    elif args.monthly:
        bronze_monthly_flow(dry_run=args.dry_run)
    elif args.all:
        bronze_full_flow(backfill_days=args.backfill_days, dry_run=args.dry_run)


if __name__ == "__main__":
    main()