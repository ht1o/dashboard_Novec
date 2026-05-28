from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import get_current_user
from api.models.schemas import ITRiskScore, ITRiskSummary
from api.db.connection import get_db_engine
from api.utils.rag import normalize_rag
from sqlalchemy import text
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/risk-score/latest", response_model=ITRiskSummary, tags=["risk"])
async def get_latest_risk_score(user: dict = Depends(get_current_user)):
    """
    Retourne le dernier IT Risk Score global et par domaine.
    """
    try:
        engine = get_db_engine()

        with engine.connect() as conn:
            # Dernière date disponible
            date_query = text("""
                SELECT TOP 1 DateKey
                FROM Gold.it_risk_score
                ORDER BY DateKey DESC
            """)
            row = conn.execute(date_query).fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Aucun risk score disponible"
                )

            latest_date = row[0]

            # Score global et par domaine pour cette date
            all_query = text("""
                SELECT
                    DateKey,
                    Score_Global,
                    Score_Infrastructure,
                    Score_ITSM,
                    Score_Cybersec,
                    Score_Applications,
                    Score_ITAM,
                    Score_Gouvernance,
                    Statut_RAG_Global,
                    Nb_Anomalies_IF,
                    Nb_Alertes_Rouge,
                    Nb_Alertes_Ambre
                FROM Gold.it_risk_score
                WHERE DateKey = :date
            """)
            result = conn.execute(all_query, {"date": latest_date}).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Score global introuvable"
            )

        domain_map = {
            "infrastructure": float(result[2]) if result[2] is not None else 0.0,
            "itsm":           float(result[3]) if result[3] is not None else 0.0,
            "cybersec":       float(result[4]) if result[4] is not None else 0.0,
            "applications":   float(result[5]) if result[5] is not None else 0.0,
            "itam":           float(result[6]) if result[6] is not None else 0.0,
            "gouvernance":    float(result[7]) if result[7] is not None else 0.0,
        }

        by_domain = {
            domain: ITRiskScore(
                timestamp=result[0],
                domain=domain,
                anomaly_score=score,
                kpi_score=score,
                forecast_score=score,
                overall_score=score,
                rag_status=normalize_rag(result[8])
            )
            for domain, score in domain_map.items()
        }

        global_score = ITRiskScore(
            timestamp=result[0],
            domain="GLOBAL",
            anomaly_score=float(result[1]),
            kpi_score=float(result[1]),
            forecast_score=float(result[1]),
            overall_score=float(result[1]),
            rag_status=normalize_rag(result[8])
        )

        logger.info(f"✅ Risk score récupéré pour: {user.get('username')}")
        return ITRiskSummary(
            timestamp=global_score.timestamp,
            global_risk_score=global_score.overall_score,
            by_domain=by_domain,
            overall_rag_status=global_score.rag_status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur risk score latest: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer le risk score"
        )


@router.get("/api/risk-score/history", tags=["risk"])
async def get_risk_score_history(
    days: int = Query(30, ge=1, le=365, description="Nombre de jours d'historique"),
    user: dict = Depends(get_current_user)
):
    """Retourne l'évolution du risk score global sur une période donnée."""
    try:
        engine = get_db_engine()

        with engine.connect() as conn:
            query = text("""
                SELECT
                    DateKey,
                    Score_Global,
                    Score_Infrastructure,
                    Score_ITSM,
                    Score_Cybersec,
                    Score_Applications,
                    Score_ITAM,
                    Score_Gouvernance,
                    Statut_RAG_Global,
                    Nb_Anomalies_IF,
                    Nb_Alertes_Rouge,
                    Nb_Alertes_Ambre
                FROM Gold.it_risk_score
                WHERE DateKey >= DATEADD(day, :neg_days, GETUTCDATE())
                ORDER BY DateKey ASC
            """)
            results = conn.execute(query, {"neg_days": -days}).fetchall()

        history = [
            {
                "timestamp": str(row[0]),
                "overall_score": float(row[1]) if row[1] is not None else None,
                "score_infrastructure": float(row[2]) if row[2] is not None else None,
                "score_itsm": float(row[3]) if row[3] is not None else None,
                "score_cybersec": float(row[4]) if row[4] is not None else None,
                "score_applications": float(row[5]) if row[5] is not None else None,
                "score_itam": float(row[6]) if row[6] is not None else None,
                "score_gouvernance": float(row[7]) if row[7] is not None else None,
                "rag_status": normalize_rag(row[8]),
                "nb_anomalies_if": row[9],
                "nb_alertes_rouge": row[10],
                "nb_alertes_ambre": row[11]
            }
            for row in results
        ]

        logger.info(f"✅ {len(history)} points historique risk score")
        return {"period_days": days, "data_points": len(history), "history": history}

    except Exception as e:
        logger.error(f"❌ Erreur historique risk score: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer l'historique du risk score"
        )