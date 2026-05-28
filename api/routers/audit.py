from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import check_role_in
from api.db.connection import get_db_engine
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/audit", tags=["audit"])
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=500),
    start_date: Optional[str] = Query(None, description="Date début (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date fin (YYYY-MM-DD)"),
    user: dict = Depends(check_role_in(["dsi", "auditeur"]))  # FIX: auditeur ajouté
):
    """
    Journal d'audit paginé (RGPD / ISO 27001).
    FIX: requête entièrement paramétrée — plus d'injection via dates ou offset.
    FIX: auditeur a accès en lecture seule (cohérent avec ROLE_PAGES["auditeur"] = ["*"]).
    """
    try:
        engine = get_db_engine()

        # FIX: offset calculé côté Python puis passé en paramètre
        offset = (page - 1) * page_size

        base_query = """
            SELECT
                Id, Created_At, Username, Action,
                Resource, Details, Success, IP_Address, Error_Message
            FROM Gold.audit_log
            WHERE 1=1
        """
        params: dict = {"offset": offset, "page_size": page_size}

        if start_date:
            base_query += " AND Created_At >= :start_date"
            params["start_date"] = start_date
        if end_date:
            base_query += " AND Created_At <= :end_date"
            params["end_date"] = end_date

        # FIX: OFFSET/FETCH via paramètres nommés
        base_query += " ORDER BY Created_At DESC OFFSET :offset ROWS FETCH NEXT :page_size ROWS ONLY"

        with engine.connect() as conn:
            results = conn.execute(text(base_query), params).fetchall()

        logs = [
            {
                "audit_id": row[0],        # Id
                "timestamp": str(row[1]),  # Created_At
                "username": row[2],        # Username
                "action": row[3],          # Action
                "resource": row[4],        # Resource
                "details": row[5],         # Details
                "success": row[6],         # Success
                "ip_address": row[7],      # IP_Address
                "error_message": row[8]    # Error_Message
            }
            for row in results
        ]

        logger.info(f"✅ {len(logs)} entrées audit pour: {user.get('username')}")
        return {
            "page": page,
            "page_size": page_size,
            "total_records": len(logs),
            "data": logs
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur journal audit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer le journal d'audit"
        )