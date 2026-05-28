from fastapi import APIRouter
from api.db.connection import get_db_engine
from sqlalchemy import text  # FIX: SQLAlchemy 2.x exige text()
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/health", tags=["health"])
async def health_check():
    """
    Health check public (sans authentification).
    Retourne le statut de l'API + la dernière exécution du pipeline.
    """
    try:
        engine = get_db_engine()

        with engine.connect() as conn:
            # FIX: utiliser text() obligatoire avec SQLAlchemy 2.x
            query = text("""
                SELECT TOP 1
                    Run_Id, Started_At, Status, Duration_Seconds
                FROM Gold.pipeline_runs
                ORDER BY Started_At DESC
            """)
            result = conn.execute(query)
            row = result.fetchone()

            last_run = {
                "run_id": row[0],
                "timestamp": str(row[1]),
                "status": row[2],
                "duration_seconds": row[3]
            } if row else None

        return {
            "status": "ok",
            "service": "Dashboard 360° API",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "last_pipeline_run": last_run
        }

    except Exception as e:
        logger.error(f"❌ Health check dégradé: {e}")
        return {
            "status": "degraded",
            "service": "Dashboard 360° API",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e)
        }