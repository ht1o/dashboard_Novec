# =============================================================================
# silver_flow.py
# Dashboard 360° Novec — Flow Prefect : Validation Bronze + Transformation Silver
#
# Responsabilité UNIQUE : valider les données Bronze puis les transformer
# en tables Silver agrégées et nettoyées.
#
# Déclenché automatiquement par Prefect Automation quand un bronze_flow
# se termine en SUCCESS (voir serve.py pour la configuration des triggers).
#
# 2 cadences de transformation alignées sur les cadences Bronze :
#   silver_daily_flow   — infra + itsm + cyber + apps + parc_auto
#   silver_monthly_flow — itam + maintenance + gouvernance
#
# Usage CLI :
#   python silver_flow.py --daily
#   python silver_flow.py --monthly
#   python silver_flow.py --all           # full init
#   python silver_flow.py --daily --dry-run
# =============================================================================

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── Résolution des chemins ────────────────────────────────────────────────────
_ROOT     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_SIM = os.path.join(_ROOT, "data_simulation")
_DB_VAL   = os.path.join(_ROOT, "database", "validation&transformation")
_LOGS     = os.path.join(_ROOT, "logs")

for _p in [_ROOT, _DATA_SIM, _DB_VAL]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Logging ───────────────────────────────────────────────────────────────────
from novec_logger import get_logger
logger = get_logger("silver")

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
    from prefect.concurrency.sync import concurrency  # ← AJOUT
    PREFECT_AVAILABLE = True
except ImportError:
    PREFECT_AVAILABLE = False
    NO_CACHE = None
    # Fallback no-op si Prefect absent
    from contextlib import contextmanager
    @contextmanager
    def concurrency(name, occupy=1):         # ← AJOUT fallback
        yield
    def flow(**kw):
        def d(fn): return fn
        return d
    def task(**kw):
        def d(fn): return fn
        return d

# =============================================================================
# GARDE ANTI-DOUBLONS — Empêche les exécutions Silver simultanées
# =============================================================================

def _should_skip_silver(flow_name: str) -> bool:
    """
    Vérifie si un autre run du même flow Silver est déjà en cours.
    
    Quand Prefect déclenche Silver via automation, chaque Bronze SUCCESS
    génère un trigger → N Bronze = N Silver en parallèle.
    Ce garde détecte les doublons et annule les surplus.
    
    Returns True si le flow courant doit s'arrêter (doublon).
    """
    if not PREFECT_AVAILABLE:
        return False
    try:
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.filters import (
            FlowRunFilter,
            FlowRunFilterState,
            FlowRunFilterStateName,
            FlowRunFilterFlowName,
            FlowFilter,
            FlowFilterName,
        )
        import asyncio

        async def _check():
            async with get_client() as client:
                # Cherche les runs RUNNING du même flow
                running = await client.read_flow_runs(
                    flow_run_filter=FlowRunFilter(
                        state=FlowRunFilterState(
                            name=FlowRunFilterStateName(any_=["Running"])
                        ),
                    ),
                    flow_filter=FlowFilter(
                        name=FlowFilterName(any_=[flow_name])
                    ),
                )
                return len(running)

        nb_running = asyncio.run(_check())
        if nb_running > 1:
            logger.warning(
                "[SILVER] %d runs '%s' déjà en cours → ce run est un doublon, skip.",
                nb_running, flow_name
            )
            return True
        return False
    except Exception as exc:
        logger.debug("[SILVER] Garde anti-doublons KO (%s) → on continue", exc)
        return False

# =============================================================================
# IMPORT PARESSEUX DES MODULES VALIDATION ET TRANSFORMATION
# =============================================================================

def _import_validators():
    try:
        import validate_bronze as vb
        return vb
    except ImportError:
        import importlib.util
        path = os.path.join(_DB_VAL, "validate_bronze.py")
        spec = importlib.util.spec_from_file_location("validate_bronze", path)
        vb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(vb)
        return vb


def _import_transformers():
    try:
        import bronze_to_silver as bts
        return bts
    except ImportError:
        import importlib.util
        path = os.path.join(_DB_VAL, "bronze_to_silver.py")
        spec = importlib.util.spec_from_file_location("bronze_to_silver", path)
        bts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bts)
        return bts


# =============================================================================
# MAPPING DOMAINES → FONCTIONS
# =============================================================================

_VALIDATORS_MAP = {
    "infrastructure": "validate_infrastructure",
    "itsm":           "validate_itsm",
    "cybersecurity":  "validate_cybersecurity",
    "applications":   "validate_applications",
    "parc_auto":      "validate_parc_auto",
    "itam":           "validate_itam",
    "maintenance":    "validate_maintenance",
    "gouvernance":    "validate_gouvernance",
}

_TRANSFORMERS_MAP = {
    "infrastructure": "transform_infrastructure",
    "itsm":           "transform_itsm",
    "cybersecurity":  "transform_cyber",
    "applications":   "transform_applications",
    "parc_auto":      "transform_parc_auto",
    "itam":           "transform_itam",
    "maintenance":    "transform_maintenance",
    "gouvernance":    "transform_gouvernance",
}

# Ordre causal strict pour la transformation Silver
SILVER_ORDER_DAILY = (
    "infrastructure",
    "itsm",
    "cybersecurity",
    "applications",
    "parc_auto",
)
SILVER_ORDER_MONTHLY = (
    "itam",
    "maintenance",
    "gouvernance",
)


# =============================================================================
# TÂCHE VALIDATION BRONZE
# =============================================================================

@task(
    name="validate_bronze",
    retries=2,
    retry_delay_seconds=15,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_validate(domains: tuple[str, ...], engine) -> dict:
    """
    Valide les tables Bronze pour les domaines spécifiés.

    Pour chaque domaine, appelle validate_<domaine>(engine) depuis validate_bronze.py.
    La règle expect_no_future_dates utilise pd.Timestamp.now() (corrigé vs .normalize()).

    Retourne :
        {
          "validated": int,          # nb domaines OK
          "failed": list[str],       # domaines en échec
          "warnings": list[str],     # règles non bloquantes
        }

    Lève ValueError si au moins un domaine échoue — bloque la transformation.
    """
    logger.info("[VAL] Validation Bronze : %s", list(domains))
    vb = _import_validators()

    validated = 0
    failed    = []
    warnings  = []

    for domain in domains:
        fn_name = _VALIDATORS_MAP.get(domain)
        if not fn_name or not hasattr(vb, fn_name):
            logger.warning("[VAL] validate_%s introuvable — ignoré", domain)
            continue
        try:
            result   = getattr(vb, fn_name)(engine)
            failures = result.summary() if hasattr(result, "summary") else []

            if failures:
                for _, msg in failures:
                    logger.warning("[VAL][%s] %s", domain, msg)
                    warnings.append(f"{domain}: {msg}")
                failed.append(f"{domain} ({len(failures)} règle(s))")
            else:
                logger.info("[VAL][%s] ✅", domain)
                validated += 1

        except Exception as exc:
            msg = f"validate_{domain} exception : {exc}"
            logger.error("[VAL] %s", msg)
            failed.append(domain)

    logger.info("[VAL] %d/%d domaines validés", validated, len(domains))

    if failed:
        raise ValueError(f"Validation échouée : {', '.join(failed)}")

    return {"validated": validated, "failed": failed, "warnings": warnings}


# =============================================================================
# TÂCHE TRANSFORMATION BRONZE → SILVER
# =============================================================================

@task(
    name="transform_to_silver",
    retries=1,
    retry_delay_seconds=10,
    **({"cache_policy": NO_CACHE} if PREFECT_AVAILABLE else {}),
)
def task_transform(domains: tuple[str, ...], engine, cadence: str = "daily") -> dict:
    """
    Transforme les tables Bronze en tables Silver pour les domaines spécifiés.

    Appelle transform_<domaine>(engine) depuis bronze_to_silver.py dans l'ordre
    causal défini par SILVER_ORDER_DAILY ou SILVER_ORDER_MONTHLY.

    Règle bloquante : si 'infrastructure' échoue, on arrête immédiatement
    car les autres domaines Silver peuvent en dépendre.

    Retourne :
        {
          "transformed": int,    # nb domaines transformés avec succès
          "failed": list[str],   # domaines en échec (non bloquants sauf infra)
        }
    """
    logger.info("[TRANSFORM][%s] Domaines : %s", cadence, list(domains))
    bts = _import_transformers()

    transformed = 0
    failed      = []

    for domain in domains:
        fn_name = _TRANSFORMERS_MAP.get(domain)
        if not fn_name or not hasattr(bts, fn_name):
            logger.warning("[TRANSFORM] %s introuvable — ignoré", fn_name)
            continue
        try:
            getattr(bts, fn_name)(engine)
            logger.info("[TRANSFORM][%s] ✅ Silver.silver_%s", cadence, domain)
            transformed += 1
        except Exception as exc:
            msg = f"transform_{domain} échoué : {exc}"
            logger.error("[TRANSFORM] %s", msg, exc_info=True)
            failed.append(domain)

            # Infrastructure bloquante — les vues Silver en dépendent
            if domain == "infrastructure":
                raise RuntimeError(
                    "Transformation Infrastructure échouée — pipeline Silver interrompu"
                ) from exc

    logger.info(
        "[TRANSFORM][%s] %d/%d domaines transformés",
        cadence, transformed, len(domains)
    )

    if failed:
        logger.warning("[TRANSFORM][%s] Domaines en échec : %s", cadence, failed)

    return {"transformed": transformed, "failed": failed}


# =============================================================================
# FLOWS PREFECT — 2 cadences + full
# =============================================================================

@flow(
    name="novec_silver_daily",
    description=(
        "Silver — Validation + Transformation quotidienne : "
        "Infrastructure, ITSM, Cybersécurité, Applications, Parc Auto. "
        "Déclenché par trigger Prefect après bronze_daily_flow SUCCESS."
    ),
    log_prints=True,
)
def silver_daily_flow(dry_run: bool = False) -> dict:
    """
    Flow Silver quotidien.

    Étapes :
      1. Valide les 5 domaines journaliers en Bronze
      2. Transforme Bronze → Silver dans l'ordre causal

    Bloqué si la validation échoue (pour ne pas écrire du Silver corrompu).
    dry_run : valide mais ne transforme pas (engine=None simulé).

    Le verrou silver_pool (concurrency-limit=1) garantit qu'un seul Silver
    s'exécute à la fois, éliminant les deadlocks SQL Server.
    Pour créer le slot une seule fois : prefect concurrency-limit create silver_pool 1
    """
    # ── VERROU ANTI-DEADLOCK ──────────────────────────────────────────────────
    # Un seul silver (daily ou monthly) à la fois.
    # Pas de timeout : les runs attendent proprement en file au lieu de crasher.
    with concurrency("silver_pool", occupy=1):
        # ── GARDE ANTI-DOUBLONS ──────────────────────────────────────────
        if _should_skip_silver("novec_silver_monthly"):
            return {"status": "skipped", "reason": "duplicate_run"}
        logger.info("══ SILVER FLOW — Daily | dry_run=%s", dry_run)

        engine = None if dry_run else get_db_engine()
        if engine is None and not dry_run:
            logger.warning("[SILVER][daily] SQL Server indisponible — flow annulé")
            return {"status": "skipped", "reason": "no_engine"}

        # Validation
        try:
            val_result = task_validate(domains=SILVER_ORDER_DAILY, engine=engine)
            logger.info("[SILVER][daily] Validation ✅ %d domaines", val_result["validated"])
        except ValueError as exc:
            logger.error("[SILVER][daily] Validation bloquante : %s", exc)
            return {"status": "failed", "phase": "validation", "error": str(exc)}

        if dry_run:
            logger.info("[SILVER][daily] dry-run — transformation ignorée")
            return {"status": "dry_run", "validated": val_result["validated"]}

        # Transformation
        try:
            tr_result = task_transform(
                domains=SILVER_ORDER_DAILY,
                engine=engine,
                cadence="daily",
            )
            logger.info("══ SILVER FLOW — Daily ✅ %d transformés", tr_result["transformed"])
            return {
                "status": "success" if not tr_result["failed"] else "partial",
                "validated": val_result["validated"],
                "transformed": tr_result["transformed"],
                "failed": tr_result["failed"],
            }
        except RuntimeError as exc:
            logger.error("[SILVER][daily] Transformation bloquante : %s", exc)
            return {"status": "failed", "phase": "transform", "error": str(exc)}


@flow(
    name="novec_silver_monthly",
    description=(
        "Silver — Validation + Transformation mensuelle : "
        "ITAM, Maintenance, Gouvernance. "
        "Déclenché par trigger Prefect après bronze_monthly_flow SUCCESS."
    ),
    log_prints=True,
)
def silver_monthly_flow(dry_run: bool = False) -> dict:
    """
    Flow Silver mensuel.

    Étapes :
      1. Valide les 3 domaines mensuels en Bronze
      2. Transforme Bronze → Silver

    Partage le même verrou silver_pool que silver_daily_flow.
    """
    # ── VERROU ANTI-DEADLOCK ──────────────────────────────────────────────────
    with concurrency("silver_pool", occupy=1):
        # ── GARDE ANTI-DOUBLONS ──────────────────────────────────────────
        if _should_skip_silver("novec_silver_monthly"):
            return {"status": "skipped", "reason": "duplicate_run"}
        logger.info("══ SILVER FLOW — Monthly | dry_run=%s", dry_run)

        engine = None if dry_run else get_db_engine()
        if engine is None and not dry_run:
            logger.warning("[SILVER][monthly] SQL Server indisponible — flow annulé")
            return {"status": "skipped", "reason": "no_engine"}

        # Validation
        try:
            val_result = task_validate(domains=SILVER_ORDER_MONTHLY, engine=engine)
            logger.info("[SILVER][monthly] Validation ✅ %d domaines", val_result["validated"])
        except ValueError as exc:
            logger.error("[SILVER][monthly] Validation bloquante : %s", exc)
            return {"status": "failed", "phase": "validation", "error": str(exc)}

        if dry_run:
            logger.info("[SILVER][monthly] dry-run — transformation ignorée")
            return {"status": "dry_run", "validated": val_result["validated"]}

        # Transformation
        try:
            tr_result = task_transform(
                domains=SILVER_ORDER_MONTHLY,
                engine=engine,
                cadence="monthly",
            )
            logger.info("══ SILVER FLOW — Monthly ✅ %d transformés", tr_result["transformed"])
            return {
                "status": "success" if not tr_result["failed"] else "partial",
                "validated": val_result["validated"],
                "transformed": tr_result["transformed"],
                "failed": tr_result["failed"],
            }
        except RuntimeError as exc:
            logger.error("[SILVER][monthly] Transformation bloquante : %s", exc)
            return {"status": "failed", "phase": "transform", "error": str(exc)}


@flow(
    name="novec_silver_full",
    description="Silver — Validation + Transformation complète tous domaines (full init).",
    log_prints=True,
)
def silver_full_flow(dry_run: bool = False) -> dict:
    """
    Flow Silver complet — tous les domaines dans l'ordre causal.
    Utilisé au premier démarrage ou pour un rejeu complet.

    Partage le même verrou silver_pool.
    """
    # ── VERROU ANTI-DEADLOCK ──────────────────────────────────────────────────
    with concurrency("silver_pool", occupy=1):
        # ── GARDE ANTI-DOUBLONS ──────────────────────────────────────────
        if _should_skip_silver("novec_silver_monthly"):
            return {"status": "skipped", "reason": "duplicate_run"}
        logger.info("══ SILVER FLOW — Full Init | dry_run=%s", dry_run)

        all_domains = SILVER_ORDER_DAILY + SILVER_ORDER_MONTHLY
        engine = None if dry_run else get_db_engine()

        if engine is None and not dry_run:
            logger.warning("[SILVER][full] SQL Server indisponible — flow annulé")
            return {"status": "skipped", "reason": "no_engine"}

        # Validation complète
        try:
            val_result = task_validate(domains=all_domains, engine=engine)
            logger.info("[SILVER][full] Validation ✅ %d domaines", val_result["validated"])
        except ValueError as exc:
            logger.error("[SILVER][full] Validation bloquante : %s", exc)
            return {"status": "failed", "phase": "validation", "error": str(exc)}

        if dry_run:
            logger.info("[SILVER][full] dry-run — transformation ignorée")
            return {"status": "dry_run", "validated": val_result["validated"]}

        # Transformation complète
        try:
            tr_result = task_transform(
                domains=all_domains,
                engine=engine,
                cadence="full",
            )
            status = "success" if not tr_result["failed"] else "partial"
            logger.info("══ SILVER FLOW — Full Init %s | %d transformés",
                        status.upper(), tr_result["transformed"])
            return {
                "status": status,
                "validated": val_result["validated"],
                "transformed": tr_result["transformed"],
                "failed": tr_result["failed"],
            }
        except RuntimeError as exc:
            logger.error("[SILVER][full] Transformation bloquante : %s", exc)
            return {"status": "failed", "phase": "transform", "error": str(exc)}


# =============================================================================
# POINT D'ENTRÉE CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dashboard 360° Novec — Silver Flow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Prérequis (une seule fois) :
  prefect concurrency-limit create silver_pool 1

Flows disponibles :
  --daily               Validation + Transformation quotidienne
  --monthly             Validation + Transformation mensuelle
  --all                 Full init (tous les domaines)

Options :
  --dry-run             Valide sans transformer

Exemples :
  python silver_flow.py --all
  python silver_flow.py --daily --dry-run
  python silver_flow.py --monthly
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--daily",   action="store_true")
    group.add_argument("--monthly", action="store_true")
    group.add_argument("--all",     action="store_true")

    parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.daily:
        silver_daily_flow(dry_run=args.dry_run)
    elif args.monthly:
        silver_monthly_flow(dry_run=args.dry_run)
    elif args.all:
        silver_full_flow(dry_run=args.dry_run)


if __name__ == "__main__":
    main()