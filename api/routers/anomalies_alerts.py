from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import get_current_user
from api.models.schemas import AnomalyAlert, Recommendation, AlertPriority
from api.db.connection import get_db_engine
from api.utils.rag import normalize_rag
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/anomalies", response_model=List[AnomalyAlert], tags=["anomalies"])
async def get_anomalies(
    domain: Optional[str] = Query(None, description="Filtre par domaine"),
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD)"),
    rag_status: Optional[str] = Query(None, description="RED, AMBER ou GREEN"),
    user: dict = Depends(get_current_user)
):
    """
    Anomalies détectées (IsolationForest + Z-Score).
    FIX: Requêtes paramétrées — plus de SQL injection via f-strings.
    FIX: UNION ALL reconstruit proprement avec colonnes homogènes.
    """
    try:
        engine = get_db_engine()

        # FIX: construire les filtres séparément avec des paramètres nommés
        filters_if = "WHERE 1=1"
        filters_zs = "WHERE z.Est_Active = 1"
        params: dict = {}

        if domain:
            filters_if += " AND a.Domaine = :domain"
            filters_zs += " AND z.Domaine = :domain"
            params["domain"] = domain
        if rag_status:
            # anomalies_detected n'a pas de colonne Statut_RAG — filtre uniquement sur zscore
            filters_zs += " AND z.Statut_RAG = :rag_status"
            params["rag_status"] = rag_status
        if date:
            filters_if += " AND CAST(a.DateKey AS DATE) = :date"
            filters_zs += " AND CAST(z.DateKey AS DATE) = :date"
            params["date"] = date

        query = text(f"""
            SELECT TOP 200
                ROW_NUMBER() OVER (ORDER BY a.DateKey DESC) AS anomaly_id,
                ISNULL(a.ServerName, a.Application_Name)   AS entity,
                a.Domaine,
                NULL                                        AS kpi,
                NULL                                        AS valeur_observee,
                NULL                                        AS z_score,
                a.Score_Confiance,
                NULL                                        AS statut_rag,
                a.DateKey
            FROM Gold.anomalies_detected a
            {filters_if}

            UNION ALL

            SELECT TOP 200
                ROW_NUMBER() OVER (ORDER BY z.DateKey DESC) + 10000,
                z.GroupKey,
                z.Domaine,
                z.KPI,
                z.Valeur_Observee,
                z.Z_Score,
                CAST(ABS(z.Z_Score) / 3.0 AS FLOAT),
                z.Statut_RAG,
                z.DateKey
            FROM Gold.zscore_alerts z
            {filters_zs}

            ORDER BY DateKey DESC
        """)

        with engine.connect() as conn:
            results = conn.execute(query, params).fetchall()

        anomalies = [
    AnomalyAlert(
        anomaly_id=int(row[0]) if row[0] else i,
        entity=str(row[1]),
        domain=str(row[2]),
        kpi=row[3],                    # None passé tel quel
        observed_value=row[4],         # idem
        z_score=row[5],
        confidence_score=min(1.0, float(row[6])) if row[6] else 0.5,
        rag_status=normalize_rag(row[7]),
        detected_at=row[8],
        is_active=True
    )
    for i, row in enumerate(results)
    ]
        
        logger.info(f"✅ {len(anomalies)} anomalies récupérées pour: {user.get('username')}")
        return anomalies

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur anomalies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer les anomalies"
        )


@router.get("/api/alerts/active", response_model=List[AnomalyAlert], tags=["alerts"])
async def get_active_alerts(user: dict = Depends(get_current_user)):
    """
    Alertes actives Prophet + Z-Score combinées.
    """
    try:
        engine = get_db_engine()

        with engine.connect() as conn:
            query = text("""
                SELECT TOP 100
                    ROW_NUMBER() OVER (ORDER BY first_alert_date DESC) AS alert_id,
                    entity, domain, kpi, yhat, rag_status, first_alert_date
                FROM Gold.prophet_alerts
                WHERE Est_Active = 1

                UNION ALL

                SELECT TOP 100
                    ROW_NUMBER() OVER (ORDER BY DateKey DESC) + 10000,
                    GroupKey, Domaine, KPI, Valeur_Observee, Statut_RAG, DateKey
                FROM Gold.zscore_alerts
                WHERE Est_Active = 1

                ORDER BY alert_id
            """)
            results = conn.execute(query).fetchall()

        alerts = [
            AnomalyAlert(
                anomaly_id=int(row[0]),
                entity=str(row[1]),
                domain=str(row[2]),
                kpi=str(row[3]),
                observed_value=float(row[4]),
                confidence_score=0.85,
                rag_status=normalize_rag(row[5]),
                detected_at=row[6],
                is_active=True
            )
            for row in results
        ]

        logger.info(f"✅ {len(alerts)} alertes actives pour: {user.get('username')}")
        return alerts

    except Exception as e:
        logger.error(f"❌ Erreur alertes actives: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer les alertes actives"
        )


@router.get("/api/recommendations", response_model=List[Recommendation], tags=["recommendations"])
async def get_recommendations(
    role_filter: Optional[str] = Query(None, alias="role", description="Filtre par rôle assigné"),
    rec_status: Optional[str] = Query(None, alias="status", description="active, acknowledged, resolved"),
    user: dict = Depends(get_current_user)
):
    """
    Recommandations ML filtrées par rôle de l'utilisateur.
    FIX: paramètre 'status' renommé rec_status pour éviter le conflit avec le module status.
    """
    try:
        engine = get_db_engine()
        user_role = user.get("role")

        # FIX: paramètres liés, pas concaténés
        base_query = """
            SELECT TOP 100
                Id,
                Titre, Description, Action_Suggeree, Domaine, Entite,
                KPI_Declencheur, Priorite, Statut_RAG_Source,
                Destinataire_Role,
                CASE WHEN Date_Acquittement IS NOT NULL THEN 1 ELSE 0 END AS Acquitte,
                Acquitte_Par, Date_Acquittement, Statut
            FROM Gold.recommendations
            WHERE (Destinataire_Role = :user_role OR Destinataire_Role = '*')
        """
        params: dict = {"user_role": user_role}

        if rec_status:
            base_query += " AND STATUT = :rec_status"
            params["rec_status"] = rec_status

        base_query += " ORDER BY DateKey DESC"

        with engine.connect() as conn:
            results = conn.execute(text(base_query), params).fetchall()

        recommendations = [
            Recommendation(
                recommendation_id=int(row[0]),
                title=str(row[1]),
                description=str(row[2]),
                action=str(row[3]),
                domain=str(row[4]),
                entity=str(row[5]),
                kpi=str(row[6]),
                priority=row[7],
                rag_status=normalize_rag(row[8]),
                trigger_source="ML",
                assigned_to_role=str(row[9]),
                created_at=row[0],  # DateKey utilisé comme date création
                acknowledged=bool(row[10]),
                acknowledged_by=row[11],
                acknowledged_at=row[12]
            )
            for row in results
        ]

        logger.info(f"✅ {len(recommendations)} recommandations pour rôle: {user_role}")
        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur recommandations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer les recommandations"
        )


@router.patch("/api/recommendations/{recommendation_id}", tags=["recommendations"])
async def update_recommendation(
    recommendation_id: int,
    new_status: str = Query(..., description="acknowledged, resolved, dismissed"),
    user: dict = Depends(get_current_user)
):
    """
    Met à jour le statut d'une recommandation.
    FIX: WHERE utilise RECOMMENDATION_ID (pas DateKey).
    FIX: conn.commit() ajouté pour persister la transaction.
    """
    if new_status not in ("acknowledged", "resolved", "dismissed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Statut invalide. Valeurs acceptées: acknowledged, resolved, dismissed"
        )

    try:
        engine = get_db_engine()

        with engine.connect() as conn:
            update_query = text("""
                UPDATE Gold.recommendations
                SET
                    Statut = :new_status,
                    Acquitte_Par = :username,
                    Date_Acquittement = CASE WHEN :new_status = 'acknowledged' THEN GETUTCDATE() ELSE Date_Acquittement END
                WHERE Id = :rec_id
            """)
            conn.execute(update_query, {
                "new_status": new_status,
                "username": user.get("username"),
                "rec_id": recommendation_id
            })

            audit_query = text("""
                INSERT INTO Gold.alert_acknowledgements
                    (Recommendation_Id, Username, Action, Created_At)
                VALUES (:rec_id, :username, :action, GETUTCDATE())
            """)
            conn.execute(audit_query, {
                "rec_id": recommendation_id,
                "username": user.get("username"),
                "action": new_status
            })

            conn.commit()  # FIX: commit explicite

        logger.info(
            f"✅ Recommandation {recommendation_id} → {new_status} "
            f"par {user.get('username')}"
        )
        return {
            "status": "success",
            "recommendation_id": recommendation_id,
            "new_status": new_status,
            "updated_by": user.get("username"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour recommandation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de mettre à jour la recommandation"
        )