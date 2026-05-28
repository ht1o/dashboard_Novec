"""
pipeline.py — Pipeline de données automatisé avec Prefect
Dashboard 360 Novec | Phase 2

Orchestration :
  validate_bronze → bronze_to_silver

Usage :
  python pipeline.py                  # Exécution immédiate
  prefect server start                # Lancer l'UI (localhost:4200)
  python pipeline.py --schedule       # Activer le scheduling

Structure du projet :
  dashboard360_novec/
  ├── data_simulation/
  │   └── config.py                   ← connexion SQL Server
  └── database/
      └── validation&transformation/
          ├── validate_bronze.py
          ├── bronze_to_silver.py
          └── pipeline_automation.py             ← CE FICHIER
"""
import sys
import os
from datetime import datetime

from prefect import flow, task, get_run_logger

# ── Résolution des chemins (indépendant du répertoire de lancement) ──
# pipeline.py  → database/validation&transformation/
# config.py    → data_simulation/
# On remonte 2 niveaux depuis ce fichier pour atteindre la racine
_HERE     = os.path.dirname(os.path.abspath(__file__))          # .../database/validation&transformation
_ROOT     = os.path.dirname(os.path.dirname(_HERE))             # .../dashboard360_novec
_DATA_SIM = os.path.join(_ROOT, "data_simulation")              # .../data_simulation

for _p in [_DATA_SIM, _HERE]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import get_db_engine

# ── Import des fonctions métier (même dossier que pipeline.py) ───────
from validate_bronze import (
    validate_infrastructure, validate_itsm, validate_cybersecurity,
    validate_applications, validate_itam, validate_parc_auto,
    validate_maintenance, validate_gouvernance,
)
from bronze_to_silver import (
    transform_infrastructure, transform_itsm, transform_cyber,
    transform_applications, transform_itam, transform_parc_auto,
    transform_maintenance, transform_gouvernance,
)


# ════════════════════════════════════════════════════════════
# TASKS — Connexion SQL Server
# ════════════════════════════════════════════════════════════

@task(name="get-db-connection", retries=3, retry_delay_seconds=10)
def task_get_engine():
    logger = get_run_logger()
    engine = get_db_engine()
    if engine is None:
        raise ConnectionError(
            "Impossible de se connecter à SQL Server. "
            "Vérifiez le fichier .env et que le serveur est démarré."
        )
    logger.info("✅ Connexion SQL Server établie")
    return engine


# ════════════════════════════════════════════════════════════
# TASKS — Validation Bronze (1 task par domaine)
# ════════════════════════════════════════════════════════════

@task(name="validate-infrastructure", retries=2, retry_delay_seconds=30)
def task_validate_infrastructure(engine):
    logger = get_run_logger()
    v = validate_infrastructure(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"Infrastructure : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ Infrastructure — validation OK")

@task(name="validate-itsm", retries=2, retry_delay_seconds=30)
def task_validate_itsm(engine):
    logger = get_run_logger()
    v = validate_itsm(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"ITSM : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ ITSM — validation OK")

@task(name="validate-cybersecurity", retries=2, retry_delay_seconds=30)
def task_validate_cybersecurity(engine):
    logger = get_run_logger()
    v = validate_cybersecurity(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"Cybersécurité : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ Cybersécurité — validation OK")

@task(name="validate-applications", retries=2, retry_delay_seconds=30)
def task_validate_applications(engine):
    logger = get_run_logger()
    v = validate_applications(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"Applications : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ Applications — validation OK")

@task(name="validate-itam", retries=2, retry_delay_seconds=30)
def task_validate_itam(engine):
    logger = get_run_logger()
    v = validate_itam(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"ITAM : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ ITAM — validation OK")

@task(name="validate-parc-auto", retries=2, retry_delay_seconds=30)
def task_validate_parc_auto(engine):
    logger = get_run_logger()
    v = validate_parc_auto(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"Parc Auto : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ Parc Auto — validation OK")

@task(name="validate-maintenance", retries=2, retry_delay_seconds=30)
def task_validate_maintenance(engine):
    logger = get_run_logger()
    v = validate_maintenance(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"Maintenance : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ Maintenance — validation OK")

@task(name="validate-gouvernance", retries=2, retry_delay_seconds=30)
def task_validate_gouvernance(engine):
    logger = get_run_logger()
    v = validate_gouvernance(engine)
    failures = v.summary()
    if failures:
        for _, msg in failures:
            logger.warning(msg)
        raise ValueError(f"Gouvernance : {len(failures)} règle(s) échouée(s)")
    logger.info("✅ Gouvernance — validation OK")


# ════════════════════════════════════════════════════════════
# TASKS — Transformation Bronze → Silver (1 task par domaine)
# ════════════════════════════════════════════════════════════

@task(name="transform-infrastructure", retries=1)
def task_transform_infrastructure(engine):
    logger = get_run_logger()
    transform_infrastructure(engine)
    logger.info("✅ Silver.silver_infrastructure chargée")

@task(name="transform-itsm", retries=1)
def task_transform_itsm(engine):
    logger = get_run_logger()
    transform_itsm(engine)
    logger.info("✅ Silver.silver_itsm chargée")

@task(name="transform-cyber", retries=1)
def task_transform_cyber(engine):
    logger = get_run_logger()
    transform_cyber(engine)
    logger.info("✅ Silver.silver_cybersecurity chargée")

@task(name="transform-applications", retries=1)
def task_transform_applications(engine):
    logger = get_run_logger()
    transform_applications(engine)
    logger.info("✅ Silver.silver_applications chargée")

@task(name="transform-itam", retries=1)
def task_transform_itam(engine):
    logger = get_run_logger()
    transform_itam(engine)
    logger.info("✅ Silver.silver_itam chargée")

@task(name="transform-parc-auto", retries=1)
def task_transform_parc_auto(engine):
    logger = get_run_logger()
    transform_parc_auto(engine)
    logger.info("✅ Silver.silver_parc_auto chargée")

@task(name="transform-maintenance", retries=1)
def task_transform_maintenance(engine):
    logger = get_run_logger()
    transform_maintenance(engine)
    logger.info("✅ Silver.silver_maintenance chargée")

@task(name="transform-gouvernance", retries=1)
def task_transform_gouvernance(engine):
    logger = get_run_logger()
    transform_gouvernance(engine)
    logger.info("✅ Silver.silver_gouvernance chargée")


# ════════════════════════════════════════════════════════════
# FLOW PRINCIPAL
# ════════════════════════════════════════════════════════════

@flow(
    name="dashboard360-bronze-to-silver",
    description="Pipeline Medallion : Validation Bronze → Transformation Silver",
    log_prints=True,
)
def bronze_to_silver_pipeline():
    logger = get_run_logger()
    logger.info("=" * 55)
    logger.info("  Dashboard360 Novec — Pipeline Bronze → Silver")
    logger.info(f"  Démarrage : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 55)

    # ── Étape 1 : Connexion ───────────────────────────────────
    engine = task_get_engine()

    # ── Étape 2 : Validations Bronze en parallèle ────────────
    val_infra = task_validate_infrastructure.submit(engine)
    val_itsm  = task_validate_itsm.submit(engine)
    val_cyber = task_validate_cybersecurity.submit(engine)
    val_apps  = task_validate_applications.submit(engine)
    val_itam  = task_validate_itam.submit(engine)
    val_fleet = task_validate_parc_auto.submit(engine)
    val_maint = task_validate_maintenance.submit(engine)
    val_gouv  = task_validate_gouvernance.submit(engine)

    for future in [val_infra, val_itsm, val_cyber, val_apps,
                   val_itam, val_fleet, val_maint, val_gouv]:
        future.result()

    logger.info("✅ Toutes les validations Bronze passées — démarrage transformation")

    # ── Étape 3 : Transformations (ordre causal strict) ───────
    task_transform_infrastructure(engine)   # 1er — source des anomalies
    task_transform_itsm(engine)             # consomme anomalies infra
    task_transform_cyber(engine)
    task_transform_applications(engine)     # consomme anomalies infra
    task_transform_itam(engine)
    task_transform_parc_auto(engine)
    task_transform_maintenance(engine)
    task_transform_gouvernance(engine)      # dernier — consomme CSAT ITSM

    logger.info("=" * 55)
    logger.info("✅ Pipeline Bronze → Silver terminé avec succès.")
    logger.info("=" * 55)


# ════════════════════════════════════════════════════════════
# SCHEDULING (optionnel)
# ════════════════════════════════════════════════════════════

def deploy_with_schedule():
    """
    Crée un deployment avec schedule quotidien à 6h (Casablanca).
    Nécessite : prefect server start (dans un terminal séparé)
    """
    bronze_to_silver_pipeline.serve(
        name="daily-6am",
        cron="0 6 * * *",
        tags=["dashboard360", "bronze-silver", "novec"]
    )
    print("✅ Deployment créé — visible sur http://localhost:4200")


# ── Point d'entrée ────────────────────────────────────────────
if __name__ == '__main__':
    if "--schedule" in sys.argv:
        deploy_with_schedule()
    else:
        bronze_to_silver_pipeline()