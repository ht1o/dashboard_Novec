# =============================================================================
# novec_logger.py
# Dashboard 360° Novec — Logger unifié et lisible
#
# Objectif :
#   - Supprimer le bruit httpx, prophet, prefect interne
#   - Écrire un fichier de log propre : logs/novec_pipeline_YYYYMMDD.log
#   - Format lisible : horodatage | niveau | couche | message
#
# Usage (dans serve.py, bronze_flow.py, silver_flow.py, ml_flow.py) :
#   from novec_logger import get_logger, setup_pipeline_logging
#
#   # Au démarrage (serve.py uniquement) :
#   setup_pipeline_logging()
#
#   # Dans chaque flow :
#   logger = get_logger("bronze")   # ou "silver", "ml", "serve"
#   logger.info("...")
# =============================================================================

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

# ── Répertoire des logs ───────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
_LOGS = _ROOT / "logs"
_LOGS.mkdir(parents=True, exist_ok=True)

# ── Fichier de log du jour ────────────────────────────────────────────────────
LOG_FILE = _LOGS / f"novec_pipeline_{datetime.now().strftime('%Y%m%d')}.log"

# ── Loggers bruités à filtrer ─────────────────────────────────────────────────
_NOISY_LOGGERS = [
    "httpx",
    "httpcore",
    "prefect.client",
    "prefect.runner",
    "prefect.infrastructure",
    "prefect.server",
    "uvicorn",
    "asyncio",
    "prophet",
    "prophet.plot",
    "cmdstanpy",
    "docket",
    "graphviz"
]

# ── Loggers Prefect à isoler complètement (propagate=False) ──────────────────
# Ces loggers génèrent des records sans le champ 'layer' → KeyError fatal
_PREFECT_LOGGERS = [
    "prefect",
    "prefect.flow_runs",
    "prefect.task_runs",
    "prefect.engine",
    "prefect.runner",
    "prefect.client",
    "prefect.server",
    "prefect.infrastructure",
    "prefect.logging",
    "prefect.runner._hook_runner",
    "prefect.runner._flow_run_executor",
    "prefect.runner._scheduled_run_poller",
]

# ── Format des lignes de log ──────────────────────────────────────────────────
#   19:03:16 | INFO    | BRONZE   | ✅ 75 lignes insérées — staging_infrastructure
_FMT_FILE    = "%(asctime)s | %(levelname)-7s | %(layer)-8s | %(message)s"
_FMT_CONSOLE = "%(asctime)s | %(levelname)-7s | %(layer)-8s | %(message)s"
_DATEFMT     = "%H:%M:%S"


# =============================================================================
# FIX PRINCIPAL — Formatter robuste qui ne plante pas si 'layer' est absent
# =============================================================================

class _SafeFormatter(logging.Formatter):
    """
    Formatter sécurisé : injecte une valeur par défaut pour 'layer'
    si le LogRecord ne contient pas ce champ.

    Sans ce fix, les logs internes de Prefect (qui n'ont pas 'layer')
    provoquent : KeyError: 'layer' → RecursionError infinie.
    """
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "layer"):
            record.layer = "EXTERN  "
        return super().format(record)


class _LayerFilter(logging.Filter):
    """Injecte le champ 'layer' dans chaque LogRecord."""
    def __init__(self, layer: str):
        super().__init__()
        self.layer = layer

    def filter(self, record: logging.LogRecord) -> bool:
        record.layer = self.layer
        return True


class _NoiseFilter(logging.Filter):
    """Bloque les loggers bruités (httpx, prophet, prefect interne...)."""
    def filter(self, record: logging.LogRecord) -> bool:
        for noisy in _NOISY_LOGGERS:
            if record.name.startswith(noisy):
                return False
        return True


# ── Handlers partagés (créés une seule fois) ──────────────────────────────────
_file_handler: logging.FileHandler | None = None
_console_handler: logging.StreamHandler | None = None
_initialized = False


def setup_pipeline_logging() -> None:
    """
    Configure le logging global une seule fois au démarrage (serve.py).
    - Redirige la root logger vers le fichier propre
    - Supprime les loggers bruités
    - Isole les loggers Prefect internes (propagate=False)
      pour éviter le KeyError 'layer' + RecursionError
    - Conserve les messages métier (bronze_flow, silver_flow, ml_flow, serve)
    """
    global _file_handler, _console_handler, _initialized
    if _initialized:
        return

    # ── Handler fichier ───────────────────────────────────────────────────────
    _file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _file_handler.setLevel(logging.DEBUG)
    # FIX : _SafeFormatter au lieu de logging.Formatter
    _file_handler.setFormatter(_SafeFormatter(_FMT_FILE, datefmt=_DATEFMT))
    _file_handler.addFilter(_NoiseFilter())

    # ── Handler console (terminal) — INFO uniquement ──────────────────────────
    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setLevel(logging.INFO)
    # FIX : _SafeFormatter au lieu de logging.Formatter
    _console_handler.setFormatter(_SafeFormatter(_FMT_CONSOLE, datefmt=_DATEFMT))
    _console_handler.addFilter(_NoiseFilter())

    # ── Root logger ───────────────────────────────────────────────────────────
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # Supprimer les handlers existants pour éviter les doublons
    root.handlers.clear()
    root.addHandler(_file_handler)
    root.addHandler(_console_handler)

    # ── Silencer les loggers bruités explicitement ────────────────────────────
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.CRITICAL)
        logging.getLogger(name).propagate = False

    # ── FIX PRINCIPAL : Isoler complètement les loggers Prefect internes ──────
    # Sans propagate=False, les logs Prefect remontent vers le root logger
    # qui utilise _SafeFormatter avec %(layer)s.
    # Même avec _SafeFormatter, le RecursionError peut survenir si Prefect
    # intercepte ses propres logs via print_as_log → boucle infinie.
    # propagate=False coupe définitivement cette boucle.
    for name in _PREFECT_LOGGERS:
        lg = logging.getLogger(name)
        lg.propagate = False   # ← ne remonte plus vers notre root logger
        # On ne touche pas au level : Prefect gère ses propres handlers

    _initialized = True

    _get_base_logger("serve").info(
        f"📁 Logs pipeline → {LOG_FILE}"
    )


def _get_base_logger(layer: str) -> logging.Logger:
    """Crée ou récupère un logger avec le champ 'layer' injecté."""
    name = f"novec.{layer}"
    logger = logging.getLogger(name)
    # Éviter d'ajouter les filtres en double
    if not any(isinstance(f, _LayerFilter) for f in logger.filters):
        logger.addFilter(_LayerFilter(layer.upper()))
    return logger


def get_logger(layer: str) -> logging.Logger:
    """
    Retourne un logger propre pour la couche indiquée.

    Paramètres :
        layer : "bronze" | "silver" | "ml" | "serve"

    Exemple :
        logger = get_logger("bronze")
        logger.info("✅ 75 lignes insérées — staging_infrastructure")
    """
    if not _initialized:
        # Auto-init si appelé sans setup_pipeline_logging (ex: flow CLI)
        setup_pipeline_logging()
    return _get_base_logger(layer)


# =============================================================================
# HELPERS DE FORMAT — pour des logs métier cohérents dans tous les flows
# =============================================================================

def log_flow_start(logger: logging.Logger, flow_name: str, run_name: str) -> None:
    """Ligne de début de flow standardisée."""
    logger.info(f"▶  DÉBUT  {flow_name} — run: {run_name}")


def log_flow_end(logger: logging.Logger, flow_name: str, duration_s: float,
                 status: str = "SUCCESS") -> None:
    """Ligne de fin de flow standardisée."""
    icon = "✅" if status == "SUCCESS" else "❌"
    logger.info(f"{icon} FIN    {flow_name} — {status} ({duration_s:.1f}s)")


def log_task_insert(logger: logging.Logger, table: str, rows: int) -> None:
    """Log d'insertion SQL standardisé."""
    logger.info(f"  → INSERT {table:<45} {rows:>6} lignes")


def log_task_error(logger: logging.Logger, table: str, error: str) -> None:
    """Log d'erreur SQL standardisé."""
    logger.error(f"  ✗ ERREUR {table:<45} {error[:80]}")


def log_ml_summary(logger: logging.Logger, if_anomalies: int, zscore_alerts: int,
                   prophet_preds: int, arima_preds: int,
                   risk_score: float, rag: str) -> None:
    """Résumé final du pipeline ML."""
    rag_icon = {"VERT": "🟢", "AMBRE": "🟡", "ROUGE": "🔴"}.get(rag.upper(), "⚪")
    logger.info("─" * 60)
    logger.info(f"  IF anomalies détectées  : {if_anomalies:>8}")
    logger.info(f"  ZScore alertes          : {zscore_alerts:>8}")
    logger.info(f"  Prophet prédictions     : {prophet_preds:>8}")
    logger.info(f"  ARIMA prédictions       : {arima_preds:>8}")
    logger.info(f"  IT Risk Score           : {risk_score:>7.1f}/100  {rag_icon} {rag}")
    logger.info("─" * 60)