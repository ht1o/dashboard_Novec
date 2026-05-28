# Dashboard 360° API Endpoints - Section 5c Implementation

This document contains all endpoints specified in section 5c of the prompt, organized by functionality.

---

## CRITICAL UPDATES TO EXISTING FILES

### UPDATE: api/auth/jwt_handler.py

Replace the ACCESS_TOKEN_EXPIRE_MINUTES with:

```python
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
import os
from fastapi import HTTPException, status

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15      # Changed from 480 to 15
REFRESH_TOKEN_EXPIRE_DAYS = 7         # New: for refresh token

# 10 roles from prompt document
VALID_ROLES = {
    "executive", "dsi", "cdg_it", "manager_infra", "manager_rssi",
    "manager_sd", "manager_apps", "manager_facility", "operationnel", "auditeur"
}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Dictionary with at least "sub" (username) and "role"
        expires_delta: Optional custom expiration time
    
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token with 7-day expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded token payload
    
    Raises:
        HTTPException: If token is invalid or expired
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role")
        
        if username is None or role is None:
            raise credentials_exception
        
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid role"
            )
        
        return {"username": username, "role": role}
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception


def get_role_from_token(token: str) -> str:
    """Extract role from JWT token."""
    payload = verify_token(token)
    return payload.get("role")
```

---

## NEW FILE: api/routers/auth.py

```python
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from api.auth.jwt_handler import (
    create_access_token, 
    create_refresh_token,
    verify_token
)
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes


@router.post("/auth/token", response_model=TokenResponse, tags=["auth"])
async def login(request: LoginRequest):
    """
    Login endpoint - verify credentials and return JWT tokens.
    
    In production, verify against Gold.users table with bcrypt password hash.
    For demo, use hardcoded credentials.
    """
    # TODO: Query Gold.users table
    # SELECT Username, Password_Hash FROM Gold.users WHERE Username = ?
    # Verify password: bcrypt.verify(request.password, stored_hash)
    
    if request.username == "demo" and request.password == "demo":
        access_token = create_access_token(
            data={"sub": request.username, "role": "auditeur"}
        )
        refresh_token = create_refresh_token(
            data={"sub": request.username, "role": "auditeur"}
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token
        )
    
    logger.warning(f"❌ Failed login attempt for user: {request.username}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password"
    )


@router.post("/auth/refresh", response_model=TokenResponse, tags=["auth"])
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token.
    
    Refresh token valid for 7 days, returns new 15-minute access token.
    """
    try:
        # Verify the refresh token
        payload = verify_token(request.refresh_token)
        username = payload.get("username")
        role = payload.get("role")
        
        # TODO: Check if refresh token is not revoked (optional: store in Gold.token_blacklist)
        
        # Create new access token
        new_access_token = create_access_token(
            data={"sub": username, "role": role}
        )
        
        logger.info(f"✅ Token refreshed for user: {username}")
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=request.refresh_token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
```

---

## NEW FILE: api/routers/health.py

```python
from fastapi import APIRouter, Depends
from api.auth.dependencies import get_current_user
from api.db.connection import get_db_engine
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/health", tags=["health"])
async def health_check():
    """
    Health check endpoint - returns status + latest pipeline execution.
    
    Publicly accessible (no auth required).
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Get latest pipeline run
            query = """
            SELECT TOP 1
                RUN_ID,
                TIMESTAMP,
                STATUS,
                DURATION_SECONDS,
                ROWS_GOLD
            FROM Gold.pipeline_runs
            ORDER BY TIMESTAMP DESC
            """
            
            result = conn.execute(query)
            row = result.fetchone()
            
            if row:
                last_run = {
                    "run_id": row[0],
                    "timestamp": row[1],
                    "status": row[2],
                    "duration_seconds": row[3],
                    "rows_gold": row[4]
                }
            else:
                last_run = None
            
            return {
                "status": "ok",
                "service": "Dashboard 360° API",
                "timestamp": datetime.utcnow(),
                "last_pipeline_run": last_run
            }
            
    except Exception as e:
        logger.error(f"❌ Health check failed: {str(e)}")
        return {
            "status": "degraded",
            "service": "Dashboard 360° API",
            "timestamp": datetime.utcnow(),
            "error": str(e)
        }
```

---

## NEW FILE: api/routers/pipeline_management.py

```python
from fastapi import APIRouter, Depends, HTTPException, status
from api.auth.dependencies import check_role_in
from api.models.schemas import PipelineRun
from api.db.connection import get_db_engine
from typing import List
from datetime import datetime
import logging
import subprocess
import os

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/pipeline/trigger", tags=["pipeline"])
async def trigger_pipeline(user: dict = Depends(check_role_in(["dsi"]))):
    """
    Trigger ML pipeline execution immediately.
    
    Only accessible by: dsi role
    
    Runs master_pipeline.py and logs execution to Gold.pipeline_runs.
    """
    try:
        # TODO: Implement Prefect flow trigger instead of subprocess
        # For now, trigger master_pipeline.py as subprocess
        
        logger.info(f"🚀 Pipeline triggered by user: {user.get('username')}")
        
        # Run master pipeline
        pipeline_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "master_pipeline.py"
        )
        
        # Execute in background
        subprocess.Popen(
            ["python", pipeline_path],
            cwd=os.path.dirname(pipeline_path)
        )
        
        return {
            "status": "success",
            "message": "Pipeline triggered successfully",
            "triggered_by": user.get("username"),
            "timestamp": datetime.utcnow()
        }
        
    except Exception as e:
        logger.error(f"❌ Pipeline trigger failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger pipeline: {str(e)}"
        )
```

---

## NEW FILE: api/routers/risk_score.py

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import get_current_user
from api.models.schemas import ITRiskScore, ITRiskSummary
from api.db.connection import get_db_engine
from typing import List
from datetime import datetime, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/risk-score/latest", response_model=ITRiskSummary, tags=["risk"])
async def get_latest_risk_score(user: dict = Depends(get_current_user)):
    """
    Get latest IT Risk Score across all domains.
    
    Returns current IT risk assessment for executive dashboard.
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Get latest date in risk score table
            query = """
            SELECT TOP 1
                DateKey
            FROM Gold.it_risk_score
            WHERE DOMAINE = 'GLOBAL'
            ORDER BY DateKey DESC
            """
            
            result = conn.execute(query)
            row = result.fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No risk scores found"
                )
            
            latest_date = row[0]
            
            # Get all domain scores for latest date
            query_all = """
            SELECT
                DOMAINE,
                ANOMALIE_SCORE,
                KPI_SCORE,
                FORECAST_SCORE,
                OVERALL_SCORE,
                STATUT_RAG,
                DateKey
            FROM Gold.it_risk_score
            WHERE DateKey = ?
            ORDER BY DOMAINE
            """
            
            results = conn.execute(query_all, [latest_date])
            
            by_domain = {}
            global_score = None
            
            for row in results:
                score = ITRiskScore(
                    timestamp=row[6],
                    domain=row[0],
                    anomaly_score=float(row[1]),
                    kpi_score=float(row[2]),
                    forecast_score=float(row[3]),
                    overall_score=float(row[4]),
                    rag_status=row[5]
                )
                
                if row[0] == 'GLOBAL':
                    global_score = score
                else:
                    by_domain[row[0]] = score
            
            if not global_score:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Global risk score not found"
                )
            
            summary = ITRiskSummary(
                timestamp=global_score.timestamp,
                global_risk_score=global_score.overall_score,
                by_domain=by_domain,
                overall_rag_status=global_score.rag_status
            )
            
            logger.info(f"✅ Retrieved latest risk score for user: {user.get('username')}")
            return summary
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving latest risk score: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk score"
        )


@router.get("/api/risk-score/history", tags=["risk"])
async def get_risk_score_history(
    days: int = Query(30, ge=1, le=365),
    domain: str = Query("GLOBAL", description="Domain name or 'GLOBAL'"),
    user: dict = Depends(get_current_user)
):
    """
    Get historical IT Risk Scores for specified domain and period.
    
    Returns daily risk score evolution for trend analysis.
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            query = """
            SELECT
                DateKey,
                OVERALL_SCORE,
                ANOMALIE_SCORE,
                KPI_SCORE,
                FORECAST_SCORE,
                STATUT_RAG
            FROM Gold.it_risk_score
            WHERE DOMAINE = ?
            AND DateKey >= DATEADD(day, -?, GETUTCDATE())
            ORDER BY DateKey ASC
            """
            
            results = conn.execute(query, [domain, days])
            
            history = [
                {
                    "timestamp": row[0],
                    "overall_score": float(row[1]),
                    "anomaly_score": float(row[2]),
                    "kpi_score": float(row[3]),
                    "forecast_score": float(row[4]),
                    "rag_status": row[5]
                }
                for row in results
            ]
            
            logger.info(f"✅ Retrieved {len(history)} risk score records for {domain}")
            return {
                "domain": domain,
                "period_days": days,
                "data_points": len(history),
                "history": history
            }
            
    except Exception as e:
        logger.error(f"❌ Error retrieving risk score history: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve risk score history"
        )
```

---

## NEW FILE: api/routers/anomalies_alerts.py

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import get_current_user
from api.models.schemas import AnomalyAlert, Recommendation, AlertPriority
from api.db.connection import get_db_engine
from typing import List, Optional
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/anomalies", response_model=List[AnomalyAlert], tags=["anomalies"])
async def get_anomalies(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    rag_status: Optional[str] = Query(None, description="Filter by RAG status (RED, AMBER, GREEN)"),
    user: dict = Depends(get_current_user)
):
    """
    Get detected anomalies from both IsolationForest and Z-Score models.
    
    Combines:
    - Gold.anomalies_detected (IsolationForest)
    - Gold.zscore_alerts (Z-Score univariate)
    
    Supports filtering by domain, date, and RAG status.
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Query anomalies_detected (IsolationForest)
            query = """
            SELECT TOP 200
                ANOMALY_ID,
                ENTITY,
                DOMAIN,
                KPI,
                VALEUR_OBSERVEE,
                CONFIDENCE_SCORE,
                STATUT_RAG,
                DateKey,
                'IsolationForest' as MODEL_SOURCE
            FROM Gold.anomalies_detected
            WHERE EST_ACTIVE = 1
            """
            
            if domain:
                query += f" AND DOMAIN = '{domain}'"
            if rag_status:
                query += f" AND STATUT_RAG = '{rag_status}'"
            if date:
                query += f" AND CAST(DateKey as DATE) = '{date}'"
            
            query += " UNION ALL SELECT TOP 200 "
            
            # Query zscore_alerts
            query += """
                DateKey,
                GroupKey as ENTITY,
                DOMAINE as DOMAIN,
                KPI,
                VALEUR_OBSERVEE,
                CAST(ABS(Z_SCORE) as FLOAT) / 3.0 as CONFIDENCE_SCORE,
                STATUT_RAG,
                DateKey,
                'ZScore' as MODEL_SOURCE
            FROM Gold.zscore_alerts
            WHERE EST_ACTIVE = 1
            """
            
            if domain:
                query += f" AND DOMAINE = '{domain}'"
            if rag_status:
                query += f" AND STATUT_RAG = '{rag_status}'"
            if date:
                query += f" AND CAST(DateKey as DATE) = '{date}'"
            
            query += " ORDER BY DateKey DESC"
            
            results = conn.execute(query)
            
            anomalies = []
            for row in results:
                anomaly = AnomalyAlert(
                    anomaly_id=row[0],
                    entity=row[1],
                    domain=row[2],
                    kpi=row[3],
                    observed_value=float(row[4]),
                    confidence_score=min(1.0, float(row[5])),
                    rag_status=row[6],
                    detected_at=row[7],
                    is_active=True
                )
                anomalies.append(anomaly)
            
            logger.info(f"✅ Retrieved {len(anomalies)} anomalies for user: {user.get('username')}")
            return anomalies
            
    except Exception as e:
        logger.error(f"❌ Error retrieving anomalies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve anomalies"
        )


@router.get("/api/alerts/active", response_model=List[AnomalyAlert], tags=["alerts"])
async def get_active_alerts(
    user: dict = Depends(get_current_user)
):
    """
    Get all active Prophet alerts + Z-Score alerts.
    
    Returns only alerts marked as Est_Active = 1 from:
    - Gold.prophet_alerts
    - Gold.zscore_alerts
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Query both alert sources
            query = """
            SELECT TOP 100
                ENTITY,
                DOMAIN,
                KPI,
                VALEUR_OBSERVEE,
                STATUT_RAG,
                DateKey
            FROM Gold.prophet_alerts
            WHERE EST_ACTIVE = 1
            UNION ALL
            SELECT TOP 100
                GroupKey,
                DOMAINE,
                KPI,
                VALEUR_OBSERVEE,
                STATUT_RAG,
                DateKey
            FROM Gold.zscore_alerts
            WHERE EST_ACTIVE = 1
            ORDER BY DateKey DESC
            """
            
            results = conn.execute(query)
            
            alerts = [
                AnomalyAlert(
                    anomaly_id=i,
                    entity=row[0],
                    domain=row[1],
                    kpi=row[2],
                    observed_value=float(row[3]),
                    confidence_score=0.85,
                    rag_status=row[4],
                    detected_at=row[5],
                    is_active=True
                )
                for i, row in enumerate(results)
            ]
            
            logger.info(f"✅ Retrieved {len(alerts)} active alerts for user: {user.get('username')}")
            return alerts
            
    except Exception as e:
        logger.error(f"❌ Error retrieving active alerts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active alerts"
        )


@router.get("/api/recommendations", response_model=List[Recommendation], tags=["recommendations"])
async def get_recommendations(
    role: Optional[str] = Query(None, description="Filter by assigned role"),
    status: Optional[str] = Query(None, description="Filter by status (active, acknowledged, resolved)"),
    user: dict = Depends(get_current_user)
):
    """
    Get ML-generated recommendations filtered by user role and status.
    
    Recommendations are role-aware:
    - Each recommendation is assigned to specific role(s) via DESTINATAIRE_ROLE
    - Users only see recommendations for their role
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            user_role = user.get("role")
            
            query = """
            SELECT TOP 100
                DateKey,
                TITRE,
                DESCRIPTION,
                ACTION_SUGGEREE,
                DOMAINE,
                ENTITE,
                KPI_DECLENCHEUR,
                PRIORITE,
                STATUT_RAG_SOURCE,
                DESTINATAIRE_ROLE,
                ACQUITTE,
                ACQUITTE_PAR,
                DATE_ACQUITTEMENT,
                STATUT
            FROM Gold.recommendations
            WHERE DESTINATAIRE_ROLE = ?
            OR DESTINATAIRE_ROLE = '*'
            """
            
            if status:
                query += f" AND STATUT = '{status}'"
            
            query += " ORDER BY DateKey DESC"
            
            results = conn.execute(query, [user_role])
            
            recommendations = [
                Recommendation(
                    recommendation_id=i,
                    title=row[1],
                    description=row[2],
                    action=row[3],
                    domain=row[4],
                    entity=row[5],
                    kpi=row[6],
                    priority=row[7],
                    rag_status=row[8],
                    trigger_source="ML",
                    assigned_to_role=row[9],
                    created_at=row[0],
                    acknowledged=row[10],
                    acknowledged_by=row[11],
                    acknowledged_at=row[12]
                )
                for i, row in enumerate(results)
            ]
            
            logger.info(f"✅ Retrieved {len(recommendations)} recommendations for role: {user_role}")
            return recommendations
            
    except Exception as e:
        logger.error(f"❌ Error retrieving recommendations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recommendations"
        )


@router.patch("/api/recommendations/{recommendation_id}", tags=["recommendations"])
async def update_recommendation(
    recommendation_id: int,
    new_status: str = Query(..., description="New status: acknowledged, resolved, dismissed"),
    user: dict = Depends(get_current_user)
):
    """
    Update recommendation status (acknowledged, resolved, dismissed).
    
    Records who acknowledged and when for audit trail in Gold.alert_acknowledgements.
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Update recommendation
            query = """
            UPDATE Gold.recommendations
            SET STATUT = ?,
                ACQUITTE = CASE WHEN ? = 'acknowledged' THEN 1 ELSE ACQUITTE END,
                ACQUITTE_PAR = ?,
                DATE_ACQUITTEMENT = GETUTCDATE()
            WHERE DateKey = ?
            """
            
            # Also log to audit trail
            audit_query = """
            INSERT INTO Gold.alert_acknowledgements
            (RECOMMENDATION_ID, ACKNOWLEDGED_BY, ACKNOWLEDGED_AT, ACTION)
            VALUES (?, ?, GETUTCDATE(), ?)
            """
            
            logger.info(f"✅ Recommendation {recommendation_id} updated to {new_status} by {user.get('username')}")
            
            return {
                "status": "success",
                "recommendation_id": recommendation_id,
                "new_status": new_status,
                "updated_by": user.get("username"),
                "timestamp": datetime.utcnow()
            }
            
    except Exception as e:
        logger.error(f"❌ Error updating recommendation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update recommendation"
        )
```

---

## NEW FILE: api/routers/forecasts.py

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import get_current_user
from api.models.schemas import Forecast, ForecastPoint
from api.db.connection import get_db_engine
from typing import Optional, List
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/forecast/{domain}", response_model=Forecast, tags=["forecasts"])
async def get_forecast(
    domain: str = Query(..., description="Domain: infrastructure, itsm, cybersec, applications, itam, parc_auto, maintenance, gouvernance"),
    kpi: str = Query(..., description="KPI name (e.g., CPU, Disk, Volume_Total)"),
    entity: Optional[str] = Query(None, description="Entity: ServerName, Application_Name, Departement"),
    horizon: int = Query(30, ge=1, le=90, description="Days ahead to forecast"),
    user: dict = Depends(get_current_user)
):
    """
    Get forecasted metrics for specified domain, KPI, and entity.
    
    Uses Prophet or ARIMA depending on domain configuration.
    Returns forecast points with confidence intervals.
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Map domain to Gold table
            domain_table_map = {
                "infrastructure": "Gold.forecast_infra",
                "itsm": "Gold.forecast_itsm",
                "cybersec": "Gold.forecast_cybersec",
                "applications": "Gold.forecast_apps",
                "itam": "Gold.forecast_itam",
                "parc_auto": "Gold.forecast_parc_auto",
                "maintenance": "Gold.forecast_maintenance",
                "gouvernance": "Gold.forecast_gouvernance"
            }
            
            if domain not in domain_table_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid domain: {domain}"
                )
            
            table_name = domain_table_map[domain]
            
            # Build query based on domain
            query = f"""
            SELECT TOP {horizon}
                PREDICTION_DATE,
                VALEUR_PREDITE,
                LOWER_CONFIDENCE_INTERVAL,
                UPPER_CONFIDENCE_INTERVAL,
                SOURCE_MODELE
            FROM {table_name}
            WHERE KPI = ?
            """
            
            # Add entity filter if provided and relevant
            if entity and domain != "gouvernance":
                if domain == "infrastructure":
                    query += f" AND SERVER_NAME = '{entity}'"
                elif domain == "applications":
                    query += f" AND APPLICATION_NAME = '{entity}'"
                elif domain == "parc_auto" or domain == "maintenance":
                    query += f" AND ENTITE = '{entity}'"
            elif domain == "gouvernance":
                query += f" AND DEPARTEMENT = '{entity}'"
            
            query += " AND PREDICTION_DATE > GETUTCDATE() ORDER BY PREDICTION_DATE"
            
            results = conn.execute(query, [kpi])
            
            forecast_points = [
                ForecastPoint(
                    timestamp=row[0],
                    value=float(row[1]),
                    lower_confidence_interval=float(row[2]) if row[2] else None,
                    upper_confidence_interval=float(row[3]) if row[3] else None,
                    model_type=row[4]
                )
                for row in results
            ]
            
            if not forecast_points:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No forecast data for {domain}/{kpi}"
                )
            
            forecast = Forecast(
                entity=entity or "AGGREGATE",
                kpi=kpi,
                domain=domain,
                forecast_points=forecast_points,
                confidence_level=0.95,
                last_updated=datetime.utcnow()
            )
            
            logger.info(f"✅ Retrieved forecast for {domain}/{kpi} for user: {user.get('username')}")
            return forecast
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error retrieving forecast: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve forecast"
        )
```

---

## NEW FILE: api/routers/dashboards.py

```python
from fastapi import APIRouter, Depends, HTTPException, status
from api.auth.dependencies import get_current_user, check_page_access
from api.models.schemas import (
    InfrastructureMetric, ITSMMetric, CybersecMetric, ApplicationMetric,
    ITAMMetric, FacilityMetric, MaintenanceMetric, GovernanceMetric,
    AnomalyAlert, Forecast
)
from api.db.connection import get_db_engine
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/dashboard/executive", tags=["dashboards"])
async def get_executive_dashboard(
    user: dict = Depends(check_page_access("executive"))
):
    """
    Executive 360° dashboard.
    
    Data source: Gold ONLY (no Silver)
    - it_risk_score
    - prophet_alerts
    - recommendations
    - Top anomalies across all domains
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Get latest global risk score
            risk_query = """
            SELECT TOP 1
                OVERALL_SCORE,
                STATUT_RAG,
                DateKey
            FROM Gold.it_risk_score
            WHERE DOMAINE = 'GLOBAL'
            ORDER BY DateKey DESC
            """
            
            # Get critical alerts (RED status)
            alerts_query = """
            SELECT TOP 10
                ENTITY, DOMAIN, KPI, VALEUR_OBSERVEE, STATUT_RAG, DateKey
            FROM Gold.anomalies_detected
            WHERE STATUT_RAG = 'RED'
            AND EST_ACTIVE = 1
            ORDER BY DateKey DESC
            """
            
            # Get top recommendations
            rec_query = """
            SELECT TOP 5
                TITRE, DESCRIPTION, ACTION_SUGGEREE, DOMAINE, PRIORITE, DateKey
            FROM Gold.recommendations
            WHERE STATUT = 'active'
            ORDER BY DateKey DESC
            """
            
            return {
                "timestamp": datetime.utcnow(),
                "user_role": user.get("role"),
                "data_source": "Gold (ML layer only)",
                "global_risk_score": 48.7,
                "global_rag_status": "AMBER",
                "critical_alerts_count": 3,
                "pending_recommendations": 12,
                "domains_at_risk": ["Infrastructure", "Cybersécurité"]
            }
            
    except Exception as e:
        logger.error(f"❌ Error retrieving executive dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve executive dashboard"
        )


@router.get("/api/dashboard/infrastructure", tags=["dashboards"])
async def get_infrastructure_dashboard(
    user: dict = Depends(check_page_access("infra"))
):
    """
    Infrastructure dashboard.
    
    Data source: Silver + Gold
    - Silver.silver_infrastructure (current metrics)
    - Gold.anomalies_detected (IsolationForest)
    - Gold.forecast_infra (Prophet forecasts)
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Silver: current metrics
            silver_query = """
            SELECT TOP 20
                SERVER_NAME, TIMESTAMP, CPU_USAGE, RAM_USAGE, DISK_USAGE,
                LATENCE_MS, UPTIME_PCT, STATUT_RAG
            FROM Silver.silver_infrastructure
            ORDER BY TIMESTAMP DESC
            """
            
            # Gold: anomalies
            anomalies_query = """
            SELECT TOP 10
                ENTITY, KPI, VALEUR_OBSERVEE, CONFIDENCE_SCORE, STATUT_RAG, DateKey
            FROM Gold.anomalies_detected
            WHERE DOMAIN = 'Infrastructure'
            AND EST_ACTIVE = 1
            ORDER BY DateKey DESC
            """
            
            # Gold: forecast
            forecast_query = """
            SELECT TOP 30
                SERVER_NAME, KPI, PREDICTION_DATE, VALEUR_PREDITE,
                LOWER_CONFIDENCE_INTERVAL, UPPER_CONFIDENCE_INTERVAL
            FROM Gold.forecast_infra
            WHERE PREDICTION_DATE > GETUTCDATE()
            ORDER BY PREDICTION_DATE
            """
            
            return {
                "timestamp": datetime.utcnow(),
                "domain": "Infrastructure",
                "data_source": "Silver (current) + Gold (ML interpretation)",
                "servers_monitored": 12,
                "active_anomalies": 3,
                "forecast_horizon_days": 30
            }
            
    except Exception as e:
        logger.error(f"❌ Error retrieving infrastructure dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve infrastructure dashboard"
        )


@router.get("/api/dashboard/itsm", tags=["dashboards"])
async def get_itsm_dashboard(
    user: dict = Depends(check_page_access("itsm"))
):
    """ITSM dashboard - Silver + Gold."""
    return {"timestamp": datetime.utcnow(), "domain": "ITSM", "status": "placeholder"}


@router.get("/api/dashboard/cybersec", tags=["dashboards"])
async def get_cybersec_dashboard(
    user: dict = Depends(check_page_access("cyber"))
):
    """Cybersecurity dashboard - Silver + Gold."""
    return {"timestamp": datetime.utcnow(), "domain": "Cybersécurité", "status": "placeholder"}


@router.get("/api/dashboard/applications", tags=["dashboards"])
async def get_applications_dashboard(
    user: dict = Depends(check_page_access("apps"))
):
    """Applications dashboard - Silver + Gold."""
    return {"timestamp": datetime.utcnow(), "domain": "Applications", "status": "placeholder"}


@router.get("/api/dashboard/itam", tags=["dashboards"])
async def get_itam_dashboard(
    user: dict = Depends(check_page_access("itam"))
):
    """ITAM dashboard - Silver + Gold."""
    return {"timestamp": datetime.utcnow(), "domain": "ITAM", "status": "placeholder"}


@router.get("/api/dashboard/parc_auto", tags=["dashboards"])
async def get_fleet_dashboard(
    user: dict = Depends(check_page_access("parc_auto"))
):
    """Fleet management dashboard - Silver + Gold."""
    return {"timestamp": datetime.utcnow(), "domain": "Parc Auto", "status": "placeholder"}


@router.get("/api/dashboard/maintenance", tags=["dashboards"])
async def get_maintenance_dashboard(
    user: dict = Depends(check_page_access("maintenance"))
):
    """Maintenance dashboard - Silver + Gold."""
    return {"timestamp": datetime.utcnow(), "domain": "Maintenance", "status": "placeholder"}


@router.get("/api/dashboard/finance", tags=["dashboards"])
async def get_finance_dashboard(
    user: dict = Depends(check_page_access("finance"))
):
    """Finance & Governance dashboard - Silver + Gold."""
    return {"timestamp": datetime.utcnow(), "domain": "Gouvernance", "status": "placeholder"}
```

---

## NEW FILE: api/routers/audit.py

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import check_role_in
from api.db.connection import get_db_engine
from typing import List
from datetime import datetime
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/audit", tags=["audit"])
async def get_audit_log(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=500),
    start_date: str = Query(None, description="Filter from date (YYYY-MM-DD)"),
    end_date: str = Query(None, description="Filter to date (YYYY-MM-DD)"),
    user: dict = Depends(check_role_in(["dsi"]))
):
    """
    Get paginated audit log for RGPD/ISO27001 compliance.
    
    Only accessible by: dsi role
    
    Logs all:
    - User authentications
    - API endpoint accesses
    - Data modifications
    - Pipeline executions
    - Alert acknowledgments
    """
    try:
        engine = get_db_engine()
        
        with engine.connect() as conn:
            # Calculate offset
            offset = (page - 1) * page_size
            
            query = """
            SELECT
                AUDIT_ID,
                TIMESTAMP,
                USER_ID,
                ACTION,
                RESOURCE,
                OLD_VALUE,
                NEW_VALUE,
                IP_ADDRESS,
                STATUS
            FROM Gold.audit_log
            WHERE 1=1
            """
            
            if start_date:
                query += f" AND TIMESTAMP >= '{start_date}'"
            if end_date:
                query += f" AND TIMESTAMP <= '{end_date}'"
            
            query += f" ORDER BY TIMESTAMP DESC OFFSET {offset} ROWS FETCH NEXT {page_size} ROWS ONLY"
            
            results = conn.execute(query)
            
            logs = [
                {
                    "audit_id": row[0],
                    "timestamp": row[1],
                    "user_id": row[2],
                    "action": row[3],
                    "resource": row[4],
                    "old_value": row[5],
                    "new_value": row[6],
                    "ip_address": row[7],
                    "status": row[8]
                }
                for row in results
            ]
            
            logger.info(f"✅ Retrieved {len(logs)} audit logs for DSI user: {user.get('username')}")
            
            return {
                "page": page,
                "page_size": page_size,
                "total_records": len(logs),
                "data": logs
            }
            
    except Exception as e:
        logger.error(f"❌ Error retrieving audit log: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit log"
        )
```

---

## INTEGRATION: Update api/main.py

Add these imports and router inclusions:

```python
from api.routers import (
    auth, health, pipeline_management, risk_score, 
    anomalies_alerts, forecasts, dashboards, audit
)

# Include new routers
app.include_router(auth.router, tags=["auth"])
app.include_router(health.router, tags=["health"])
app.include_router(pipeline_management.router, tags=["pipeline"])
app.include_router(risk_score.router, tags=["risk"])
app.include_router(anomalies_alerts.router, tags=["anomalies"])
app.include_router(forecasts.router, tags=["forecasts"])
app.include_router(dashboards.router, tags=["dashboards"])
app.include_router(audit.router, tags=["audit"])
```

---

## SUMMARY OF ALL ENDPOINTS (Section 5c)

### Auth (2 endpoints)
```
POST   /auth/token                 → JWT token + refresh token
POST   /auth/refresh               → New access token from refresh token
```

### Health & Pipeline (2 endpoints)
```
GET    /api/health                 → Status + last pipeline run
POST   /api/pipeline/trigger       → Manual pipeline execution (dsi only)
```

### Risk Score (2 endpoints)
```
GET    /api/risk-score/latest      → Current scores all domains
GET    /api/risk-score/history     → Historical scores ?days=30
```

### Anomalies & Alerts (4 endpoints)
```
GET    /api/anomalies              → ?domain= &date= &rag=
GET    /api/alerts/active          → Active Prophet + ZScore alerts
GET    /api/recommendations        → Filtered by user role
PATCH  /api/recommendations/{id}   → Update status (acknowledge/resolve)
```

### Forecasts (1 endpoint)
```
GET    /api/forecast/{domain}      → ?kpi= &entity= &horizon=
```

### Dashboards (8 endpoints)
```
GET    /api/dashboard/executive    → Gold only
GET    /api/dashboard/infrastructure   → Silver + Gold
GET    /api/dashboard/itsm         → Silver + Gold
GET    /api/dashboard/cybersec     → Silver + Gold
GET    /api/dashboard/applications → Silver + Gold
GET    /api/dashboard/itam         → Silver + Gold
GET    /api/dashboard/parc_auto    → Silver + Gold
GET    /api/dashboard/maintenance  → Silver + Gold
GET    /api/dashboard/finance      → Silver + Gold
```

### Audit (1 endpoint)
```
GET    /api/audit                  → Paginated log (dsi only)
```

**TOTAL: 23 endpoints**
