from fastapi import APIRouter, Depends, HTTPException, status
from api.auth.dependencies import check_role_in
from api.db.connection import get_db_engine
from sqlalchemy import text
from datetime import datetime, timezone
import logging
import subprocess
import os

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/pipeline/trigger", tags=["pipeline"])
async def trigger_pipeline(user: dict = Depends(check_role_in(["dsi"]))):
    """
    Déclenche le pipeline ML immédiatement.
    Accessible uniquement au rôle: dsi
    """
    try:
        logger.info(f"🚀 Pipeline déclenché par: {user.get('username')}")

        pipeline_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "master_pipeline.py")
        )

        if not os.path.exists(pipeline_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"master_pipeline.py introuvable: {pipeline_path}"
            )

        subprocess.Popen(
            ["python", pipeline_path],
            cwd=os.path.dirname(pipeline_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        return {
            "status": "success",
            "message": "Pipeline déclenché avec succès",
            "triggered_by": user.get("username"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Échec du déclenchement pipeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de déclencher le pipeline: {e}"
        )


@router.get("/api/pipeline/status", tags=["pipeline"])
async def get_pipeline_status(user: dict = Depends(check_role_in(["dsi"]))):
    """
    Retourne les 10 dernières exécutions du pipeline.
    Accessible uniquement au rôle: dsi
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            query = text("""
                SELECT TOP 10
                    Run_Id, Started_At, Status, Duration_Seconds,
                    IF_Anomalies_Detectees, Prophet_Predictions, Error_Message
                FROM Gold.pipeline_runs
                ORDER BY Started_At DESC
            """)
            results = conn.execute(query).fetchall()

        runs = [
            {
                "run_id": r[0],
                "timestamp": str(r[1]),
                "status": r[2],
                "duration_seconds": r[3],
                "anomalies_detected": r[4],
                "forecasts_generated": r[5],
                "error_message": r[6]
            }
            for r in results
        ]

        return {"runs": runs, "total": len(runs)}

    except Exception as e:
        logger.error(f"❌ Erreur statut pipeline: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer le statut du pipeline"
        )