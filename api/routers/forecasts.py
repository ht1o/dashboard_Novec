from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import get_current_user
from api.models.schemas import Forecast, ForecastPoint
from api.db.connection import get_db_engine
from sqlalchemy import text
from typing import Optional, List
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

DOMAIN_TABLE_MAP = {
    "infrastructure": "Gold.forecast_infra",
    "itsm":           "Gold.forecast_itsm",
    "cybersec":       "Gold.forecast_cybersec",
    "applications":   "Gold.forecast_apps",
    "itam":           "Gold.forecast_itam",
    "parc_auto":      "Gold.forecast_parc_auto",
    "maintenance":    "Gold.forecast_maintenance",
    "gouvernance":    "Gold.forecast_gouvernance",
}

VALID_DOMAINS = list(DOMAIN_TABLE_MAP.keys())

# Ajouter dans api/routers/forecasts.py, AVANT la route /{domain}

# Map domaine → colonne entité pour les segments
DOMAIN_ENTITY_COL = {
    "infrastructure": ("Gold.forecast_infra",      "server_name"),
    "applications":   ("Gold.forecast_apps",        "application_name"),
    "gouvernance":    ("Gold.forecast_gouvernance", "departement"),
    # Les autres domaines n'ont pas d'entité distincte
    "itsm":           (None, None),
    "cybersec":       (None, None),
    "itam":           (None, None),
    "parc_auto":      (None, None),
    "maintenance":    (None, None),
}

SEGMENT_TYPE_MAP = {
    "infrastructure": "server",
    "applications":   "application",
    "gouvernance":    "departement",
}


@router.get("/api/forecasts/domaines", tags=["forecasts"])
async def get_forecast_domaines(user: dict = Depends(get_current_user)):
    """
    Liste des domaines disponibles.
    Alimente le premier dropdown de FilterBar.jsx.
    """
    return {
        "domaines": list(DOMAIN_TABLE_MAP.keys())
    }


@router.get("/api/forecasts/segments", tags=["forecasts"])
async def get_forecast_segments(
    domaine: str = Query(..., description="Domaine (ex: infrastructure)"),
    user: dict = Depends(get_current_user)
):
    """
    Entités filtrables pour un domaine.
    Alimente le dropdown serveur/app/département de FilterBar.jsx.
    Retourne ['Global'] pour les domaines sans entité distincte.
    """
    domain_key = domaine.lower()
    entry = DOMAIN_ENTITY_COL.get(domain_key)

    if not entry or entry[0] is None:
        return {
            "domaine": domaine,
            "segments": ["Global"],
            "segment_type": "global"
        }

    table_name, col_name = entry
    try:
        engine = get_db_engine()
        # table_name et col_name viennent d'un dict interne — pas d'injection
        query = text(f"""
            SELECT DISTINCT {col_name}
            FROM {table_name}
            WHERE {col_name} IS NOT NULL
            ORDER BY {col_name}
        """)
        with engine.connect() as conn:
            results = conn.execute(query).fetchall()

        return {
            "domaine": domaine,
            "segments": [r[0] for r in results if r[0]],
            "segment_type": SEGMENT_TYPE_MAP.get(domain_key, "global")
        }
    except Exception as e:
        logger.error(f"❌ Erreur segments {domaine}: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer les segments")


@router.get("/api/forecasts/kpis", tags=["forecasts"])
async def get_forecast_kpis(
    domaine: str = Query(..., description="Domaine (ex: infrastructure)"),
    user: dict = Depends(get_current_user)
):
    """
    KPIs disponibles pour un domaine.
    Alimente le dropdown KPI de FilterBar.jsx (page forecast détail).
    """
    domain_key = domaine.lower()
    table_name = DOMAIN_TABLE_MAP.get(domain_key)

    if not table_name:
        raise HTTPException(
            status_code=400,
            detail=f"Domaine invalide: '{domaine}'. Valeurs: {VALID_DOMAINS}"
        )

    try:
        engine = get_db_engine()
        query = text(f"SELECT DISTINCT KPI FROM {table_name} WHERE KPI IS NOT NULL ORDER BY KPI")
        with engine.connect() as conn:
            results = conn.execute(query).fetchall()

        return {"domaine": domaine, "kpis": [r[0] for r in results if r[0]]}
    except Exception as e:
        logger.error(f"❌ Erreur KPIs {domaine}: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer les KPIs")

# FIX CRITIQUE: {domain} est un PATH PARAMETER — ne pas le déclarer avec Query(...)
# L'erreur originale "Cannot use Query for path param 'domain'" venait exactement de ça.
@router.get("/api/forecast/{domain}", response_model=Forecast, tags=["forecasts"])
async def get_forecast(
    domain: str,  # FIX: path param simple, PAS Query(...)
    kpi: str = Query(..., description="Nom du KPI (ex: CPU, DISK, Volume_Total)"),
    entity: Optional[str] = Query(None, description="Entité: ServerName, Application_Name, Departement"),
    horizon: int = Query(30, ge=1, le=90, description="Jours à prédire"),
    user: dict = Depends(get_current_user)
):
    """
    Prévisions pour un domaine, KPI et entité donnés.
    FIX principal: domain n'est plus déclaré Query(...) sur un path param.
    FIX: Requêtes paramétrées — plus d'injection via entity.
    """
    domain = domain.lower()

    if domain not in DOMAIN_TABLE_MAP:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Domaine invalide: '{domain}'. Valeurs acceptées: {VALID_DOMAINS}"
        )

    table_name = DOMAIN_TABLE_MAP[domain]

    # FIX: entity filtrée via paramètre nommé, pas f-string
    entity_filter = ""
    params: dict = {"kpi": kpi}

    if entity:
        params["entity"] = entity
        if domain == "infrastructure":
            entity_filter = "AND server_name = :entity"
        elif domain == "applications":
            entity_filter = "AND application_name = :entity"
        elif domain == "gouvernance":
            entity_filter = "AND departement = :entity"
        # parc_auto et maintenance n'ont pas de colonne entité dans le schéma

    # NOTE: table_name vient d'un dict interne, pas de l'utilisateur → pas d'injection
    query = text(f"""
        SELECT TOP {horizon}
            DS,
            Yhat,
            Yhat_Lower,
            Yhat_Upper,
            Source_Modele
        FROM {table_name}
        WHERE KPI = :kpi
        {entity_filter}
        AND DS > GETUTCDATE()
        AND Is_Forecast = 1
        ORDER BY DS
    """)
    

    try:
        engine = get_db_engine()

        with engine.connect() as conn:
            results = conn.execute(query, params).fetchall()

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aucune prévision pour domaine={domain}, kpi={kpi}"
            )

        forecast_points = [
            ForecastPoint(
                timestamp=row[0],       # DS
                value=float(row[1]),    # Yhat
                lower_confidence_interval=float(row[2]) if row[2] is not None else None,  # Yhat_Lower
                upper_confidence_interval=float(row[3]) if row[3] is not None else None,  # Yhat_Upper
                model_type=str(row[4]) if row[4] else "Unknown"  # Source_Modele
            )
            for row in results
        ]

        logger.info(
            f"✅ {len(forecast_points)} points prévision — "
            f"domaine={domain}, kpi={kpi}, user={user.get('username')}"
        )

        return Forecast(
            entity=entity or "Global",
            kpi=kpi,
            domain=domain,
            forecast_points=forecast_points,
            confidence_level=0.95,
            last_updated=datetime.now(timezone.utc)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur prévision {domain}/{kpi}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible de récupérer les prévisions"
        )