from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum


def utcnow() -> datetime:
    # FIX: datetime.utcnow() est deprecated depuis Python 3.12
    return datetime.now(timezone.utc)


class RAGStatus(str, Enum):
    RED = "RED"
    AMBER = "AMBER"
    GREEN = "GREEN"


class AlertPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class InfrastructureMetric(BaseModel):
    server_name: str
    timestamp: datetime
    cpu_usage: float = Field(ge=0, le=100)
    ram_usage: float = Field(ge=0, le=100)
    disk_usage: float = Field(ge=0, le=100)
    latency_ms: float = Field(ge=0)
    uptime_pct: float = Field(ge=0, le=100)
    rag_status: RAGStatus


class AnomalyAlert(BaseModel):
    anomaly_id: int
    entity: str
    domain: str
    kpi: Optional[str] = None          # NULL pour les lignes anomalies_detected
    observed_value: Optional[float] = None  # idem
    z_score: Optional[float] = None
    confidence_score: float = Field(default=0.5, ge=0, le=1)
    rag_status: Optional[RAGStatus] = None  # NULL pour anomalies_detected
    detected_at: datetime
    is_active: bool = True


class ForecastPoint(BaseModel):
    timestamp: datetime
    value: float
    lower_confidence_interval: Optional[float] = None
    upper_confidence_interval: Optional[float] = None
    model_type: str = Field(description="'Prophet' ou 'ARIMA'")


class Forecast(BaseModel):
    entity: str
    kpi: str
    domain: str
    forecast_points: List[ForecastPoint]
    confidence_level: float = Field(ge=0, le=1)
    last_updated: datetime


class ITSMMetric(BaseModel):
    timestamp: datetime
    total_tickets: int = Field(ge=0)
    p1_tickets: int = Field(ge=0)
    p2_tickets: int = Field(ge=0)
    p3_tickets: int = Field(ge=0)
    backlog: int = Field(ge=0)
    avg_mttr_hours: float = Field(ge=0)
    sla_compliance_pct: float = Field(ge=0, le=100)
    csat_score: float = Field(ge=0, le=10)
    rag_status: RAGStatus


class CybersecMetric(BaseModel):
    timestamp: datetime
    vulnerabilities_open: int = Field(ge=0)
    mfa_coverage_pct: float = Field(ge=0, le=100)
    phishing_attempts: int = Field(ge=0)
    phishing_click_rate_pct: float = Field(ge=0, le=100)
    patches_pending: int = Field(ge=0)
    rgpd_compliance_pct: float = Field(ge=0, le=100)
    incidents_critical: int = Field(ge=0)
    rag_status: RAGStatus


class ApplicationMetric(BaseModel):
    application_name: str
    timestamp: datetime
    response_time_ms: float = Field(ge=0)
    availability_pct: float = Field(ge=0, le=100)
    error_rate_pct: float = Field(ge=0, le=100)
    throughput_req_per_sec: float = Field(ge=0)
    rag_status: RAGStatus


class ITAMMetric(BaseModel):
    timestamp: datetime
    total_assets: int = Field(ge=0)
    obsolete_assets_pct: float = Field(ge=0, le=100)
    cmdb_coverage_pct: float = Field(ge=0, le=100)
    license_compliance_pct: float = Field(ge=0, le=100)
    avg_tco_per_asset: float = Field(ge=0)
    rag_status: RAGStatus


class FacilityMetric(BaseModel):
    timestamp: datetime
    vehicles_available: int = Field(ge=0)
    vehicles_in_maintenance: int = Field(ge=0)
    incident_rate_pct: float = Field(ge=0, le=100)
    fuel_consumption_l_per_km: float = Field(ge=0)
    rag_status: RAGStatus


class MaintenanceMetric(BaseModel):
    timestamp: datetime
    preventive_maintenance_pct: float = Field(ge=0, le=100)
    total_work_orders: int = Field(ge=0)
    stock_ruptures: int = Field(ge=0)
    avg_completion_time_days: float = Field(ge=0)
    rag_status: RAGStatus


class GovernanceMetric(BaseModel):
    timestamp: datetime
    department: str
    budget_utilization_pct: float = Field(ge=0, le=100)
    roi_pct: float
    operational_cost: float = Field(ge=0)
    headcount: int = Field(ge=0)
    rag_status: RAGStatus


class ITRiskScore(BaseModel):
    timestamp: datetime
    domain: str
    anomaly_score: float = Field(ge=0, le=100)
    kpi_score: float = Field(ge=0, le=100)
    forecast_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    rag_status: RAGStatus


class ITRiskSummary(BaseModel):
    timestamp: datetime
    global_risk_score: float = Field(ge=0, le=100)
    by_domain: Dict[str, ITRiskScore]
    overall_rag_status: RAGStatus


class Recommendation(BaseModel):
    recommendation_id: int
    title: str
    description: str
    action: str
    domain: str
    entity: str
    kpi: str
    priority: AlertPriority
    rag_status: RAGStatus
    trigger_source: str
    assigned_to_role: str
    created_at: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None


class PipelineRun(BaseModel):
    run_id: int
    timestamp: datetime
    status: str
    duration_seconds: Optional[float] = None
    rows_bronze: int = Field(ge=0)
    rows_silver: int = Field(ge=0)
    rows_gold: int = Field(ge=0)
    anomalies_detected: int = Field(ge=0)
    forecasts_generated: int = Field(ge=0)
    error_message: Optional[str] = None


class ExecutiveDashboard(BaseModel):
    timestamp: datetime
    it_risk_score: ITRiskScore
    top_recommendations: List[Recommendation]
    infra_summary: InfrastructureMetric
    itsm_summary: ITSMMetric
    cybersec_summary: CybersecMetric
    critical_alerts: List[AnomalyAlert]
    department_scores: Dict[str, GovernanceMetric]


class APIResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=utcnow)  # FIX: utilise utcnow() avec timezone