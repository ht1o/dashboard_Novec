"""
dashboards.py — Router FastAPI pour tous les endpoints dashboard
Dashboard 360 Novec — Silver (KPIs réels) + Gold (forecasts + anomalies)

Sources de données :
  Silver.silver_*      → valeurs observées réelles (KPI cards, graphiques tendances)
  Gold.forecast_*      → prédictions Prophet (Prédiction IA, ForecastChart)
  Gold.zscore_alerts   → alertes statistiques temps réel
  Gold.anomalies_detected → anomalies IsolationForest
  Gold.it_risk_score   → score RAG global par domaine
  Gold.recommendations → recommandations ML
  Gold.prophet_alerts  → alertes Prophet actives

Conventions :
  - Statut_RAG stocké en français : ROUGE / AMBRE / VERT
  - Toutes les URLs utilisent des tirets (parc-auto, cybersecurity)
  - Chaque endpoint retourne : kpis{}, trends[], prediction_ia{}, risk_score, rag_status
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from api.auth.dependencies import get_current_user, check_role_in
from api.db.connection import get_db_engine
from api.utils.rag import normalize_rag
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timezone
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers d'accès par rôle
# ---------------------------------------------------------------------------

ROLE_PAGES = {
    "executive":        ["executive"],
    "dsi":              ["executive", "infrastructure", "itsm", "cyber", "apps",
                         "itam", "parc_auto", "maintenance", "finance", "alerts"],
    "manager_infra":    ["infrastructure", "itam"],
    "manager_rssi":     ["cyber", "infrastructure"],
    "manager_sd":       ["itsm"],
    "manager_apps":     ["apps"],
    "manager_facility": ["parc_auto", "maintenance"],
    "cdg_it":           ["finance"],
    "operationnel":     ["alerts"],
    "auditeur":         ["executive", "infrastructure", "itsm", "cyber", "apps",
                         "itam", "parc_auto", "maintenance", "finance", "alerts"],
}


def check_page_access(page: str):
    """Dépendance FastAPI : vérifie que le rôle a accès à la page demandée."""
    async def _check(user: dict = Depends(get_current_user)):
        role = user.get("role", "")
        allowed = ROLE_PAGES.get(role, [])
        if page not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Rôle '{role}' non autorisé sur la page '{page}'"
            )
        return user
    return _check


# ---------------------------------------------------------------------------
# Helper : filtres Silver génériques
# ---------------------------------------------------------------------------

def build_date_filter(date_from: Optional[str], date_to: Optional[str],
                      params: dict, col: str = "DateKey") -> str:
    """Construit les clauses AND DateKey >= / <= et alimente params."""
    clause = ""
    if date_from:
        clause += f" AND {col} >= :date_from"
        params["date_from"] = date_from
    if date_to:
        clause += f" AND {col} <= :date_to"
        params["date_to"] = date_to
    return clause


# ---------------------------------------------------------------------------
# 1. EXECUTIVE — Vue 360° (Gold uniquement)
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/executive", tags=["dashboards"])
async def get_executive_dashboard(
    period_from: Optional[str] = Query(None, description="Mois début YYYY-MM"),
    period_to: Optional[str] = Query(None, description="Mois fin YYYY-MM"),
    user: dict = Depends(check_page_access("executive"))
):
    """
    Page 1 — Vue Executive 360°
    Scorecard RAG : 1 ligne par domaine (statut + KPI clé + recommandation)
    KPIs transversaux : IT Cost/Revenue, IT Risk Score, Digital Adoption, Prédiction J+7
    Point d'attention direction : recommandation Gold la plus critique
    Prédictions J+7 : résumé textuel depuis prophet_alerts actives

    Sources :
      Gold.it_risk_score          → Score_Global, scores par domaine, RAG
      Silver.silver_*             → 1 KPI représentatif par domaine (dernière valeur)
      Gold.recommendations        → point d'attention + actions recommandées
      Gold.prophet_alerts         → prédictions J+7 en surimpression
    """
    try:
        engine = get_db_engine()
        with engine.connect() as conn:

            # ── Risk score global + par domaine ───────────────────────────────
            risk_q = text("""
                SELECT TOP 1
                    Score_Global, Score_Infrastructure, Score_ITSM,
                    Score_Cybersec, Score_Applications, Score_ITAM,
                    Score_Gouvernance, Statut_RAG_Global,
                    Nb_Anomalies_IF, Nb_Alertes_Rouge, Nb_Alertes_Ambre,
                    Top_Contributeurs, DateKey
                FROM Gold.it_risk_score
                ORDER BY DateKey DESC
            """)
            risk = conn.execute(risk_q).fetchone()

            # ── KPI représentatif par domaine (dernière valeur Silver) ────────
            # Infrastructure : Uptime
            infra_kpi_q = text("""
                SELECT TOP 1 AVG(Disponibilite_Pct) AS v
                FROM Silver.silver_infrastructure
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_infrastructure)
                GROUP BY DateKey
            """)
            infra_uptime = conn.execute(infra_kpi_q).scalar()

            # Cybersécurité : Conformité RGPD
            cyber_kpi_q = text("""
                SELECT TOP 1 RGPD_Conformite_Pct
                FROM Silver.silver_cybersecurity
                ORDER BY DateKey DESC
            """)
            cyber_conf = conn.execute(cyber_kpi_q).scalar()

            # ITSM : CSAT
            itsm_kpi_q = text("""
                SELECT TOP 1 CSAT_Moyen
                FROM Silver.silver_itsm
                ORDER BY DateKey DESC
            """)
            itsm_csat = conn.execute(itsm_kpi_q).scalar()

            # Finance : Écart budget (dernière ligne toutes directions)
            finance_kpi_q = text("""
                SELECT AVG(Ecart_Budget_Moyen_Pct)
                FROM Silver.silver_gouvernance
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_gouvernance)
            """)
            finance_ecart = conn.execute(finance_kpi_q).scalar()

            # Applications : bugs critiques total
            apps_kpi_q = text("""
                SELECT SUM(Nb_Bugs_Critiques)
                FROM Silver.silver_applications
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_applications)
            """)
            apps_bugs = conn.execute(apps_kpi_q).scalar()

            # ITAM : % postes vétustes
            itam_kpi_q = text("""
                SELECT TOP 1 Vetuste_Moyen_Pct
                FROM Silver.silver_itam
                ORDER BY DateKey DESC
            """)
            itam_vetuste = conn.execute(itam_kpi_q).scalar()

            # Parc auto : disponibilité flotte
            parc_kpi_q = text("""
                SELECT TOP 1 AVG(Disponibilite_Pct)
                FROM Silver.silver_parc_auto
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_parc_auto)
                GROUP BY DateKey
            """)
            parc_dispo = conn.execute(parc_kpi_q).scalar()

            # Maintenance : ratio préventif
            maint_kpi_q = text("""
                SELECT TOP 1 AVG(Ratio_Preventif_Pct)
                FROM Silver.silver_maintenance
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_maintenance)
                GROUP BY DateKey
            """)
            maint_ratio = conn.execute(maint_kpi_q).scalar()

            # Applications : qualité données (Data & BI)
            data_kpi_q = text("""
                SELECT AVG(Qualite_Donnees_Pct)
                FROM Silver.silver_applications
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_applications)
            """)
            data_qualite = conn.execute(data_kpi_q).scalar()

            # Digital adoption (gouvernance)
            digital_q = text("""
                SELECT AVG(Adoption_Digital_Pct)
                FROM Silver.silver_gouvernance
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_gouvernance)
            """)
            digital_adoption = conn.execute(digital_q).scalar()

            # ── Recommandation prioritaire (point d'attention direction) ──────
            attention_q = text("""
                SELECT TOP 1
                    Titre, Description, Action_Suggeree, Domaine,
                    Statut_RAG_Source, Priorite
                FROM Gold.recommendations
                WHERE Statut = 'active'
                  AND Statut_RAG_Source IN ('ROUGE', 'RED')
                  AND Destinataire_Role IN ('dsi', 'executive', '*')
                ORDER BY DateKey DESC
            """)
            attention = conn.execute(attention_q).fetchone()

            # ── Actions recommandées par domaine (scorecard droite) ───────────
            actions_q = text("""
                SELECT Domaine, Titre, Action_Suggeree, Statut_RAG_Source
                FROM Gold.recommendations
                WHERE Statut = 'active'
                  AND Statut_RAG_Source IN ('ROUGE', 'AMBRE', 'RED', 'AMBER')
                  AND Destinataire_Role IN ('dsi', 'executive', '*')
                ORDER BY
                    CASE Statut_RAG_Source WHEN 'ROUGE' THEN 1 WHEN 'RED' THEN 1
                                           WHEN 'AMBRE' THEN 2 ELSE 3 END,
                    DateKey DESC
            """)
            actions_rows = conn.execute(actions_q).fetchall()

            # ── Prédictions J+7 actives (surimpression executive) ─────────────
            preds_q = text("""
                SELECT TOP 5
                    domain, entity, kpi, yhat, rag_status, first_alert_date
                FROM Gold.prophet_alerts
                WHERE Est_Active = 1
                ORDER BY
                    CASE rag_status WHEN 'ROUGE' THEN 1 WHEN 'RED' THEN 1
                                    WHEN 'AMBRE' THEN 2 ELSE 3 END,
                    first_alert_date ASC
            """)
            preds = conn.execute(preds_q).fetchall()

        # Actions par domaine (1 action max par domaine pour le scorecard)
        actions_by_domain = {}
        for r in actions_rows:
            dom = str(r[0])
            if dom not in actions_by_domain:
                actions_by_domain[dom] = {
                    "titre": r[1], "action": r[2],
                    "rag": normalize_rag(r[3])
                }

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),

            # Scorecard RAG — état des 9 domaines
            "scorecard": {
                "infrastructure": {
                    "rag": normalize_rag(
                        "VERT" if (infra_uptime or 0) >= 99
                        else "AMBRE" if (infra_uptime or 0) >= 97
                        else "ROUGE"
                    ),
                    "kpi_label": "Uptime",
                    "kpi_value": round(float(infra_uptime), 1) if infra_uptime else None,
                    "kpi_unit": "%",
                    "action": actions_by_domain.get("Infrastructure"),
                    "risk_score": float(risk[1]) if risk and risk[1] else None,
                },
                "cybersecurite": {
                    "rag": normalize_rag(
                        "VERT" if (cyber_conf or 0) >= 95
                        else "AMBRE" if (cyber_conf or 0) >= 80
                        else "ROUGE"
                    ),
                    "kpi_label": "Conformité RGPD",
                    "kpi_value": round(float(cyber_conf), 1) if cyber_conf else None,
                    "kpi_unit": "%",
                    "action": actions_by_domain.get("Cybersécurité"),
                    "risk_score": float(risk[4]) if risk and risk[4] else None,
                },
                "service_desk": {
                    "rag": normalize_rag(
                        "VERT" if (itsm_csat or 0) >= 4
                        else "AMBRE" if (itsm_csat or 0) >= 3
                        else "ROUGE"
                    ),
                    "kpi_label": "CSAT",
                    "kpi_value": round(float(itsm_csat), 2) if itsm_csat else None,
                    "kpi_unit": "/5",
                    "action": actions_by_domain.get("ITSM"),
                    "risk_score": float(risk[2]) if risk and risk[2] else None,
                },
                "gouvernance": {
                    "rag": normalize_rag(
                        "VERT" if (finance_ecart or 0) <= 0
                        else "AMBRE" if (finance_ecart or 0) <= 10
                        else "ROUGE"
                    ),
                    "kpi_label": "Écart budget",
                    "kpi_value": round(float(finance_ecart), 1) if finance_ecart else None,
                    "kpi_unit": "%",
                    "action": actions_by_domain.get("Gouvernance"),
                    "risk_score": float(risk[6]) if risk and risk[6] else None,
                },
                "applications": {
                    "rag": normalize_rag(
                        "VERT" if (apps_bugs or 0) == 0
                        else "AMBRE" if (apps_bugs or 0) <= 5
                        else "ROUGE"
                    ),
                    "kpi_label": "Bugs prod",
                    "kpi_value": int(apps_bugs) if apps_bugs else 0,
                    "kpi_unit": "",
                    "action": actions_by_domain.get("Applications"),
                    "risk_score": float(risk[3]) if risk and risk[3] else None,
                },
                "parc_informatique": {
                    "rag": normalize_rag(
                        "VERT" if (itam_vetuste or 0) <= 20
                        else "AMBRE" if (itam_vetuste or 0) <= 35
                        else "ROUGE"
                    ),
                    "kpi_label": "Postes > 5 ans",
                    "kpi_value": round(float(itam_vetuste), 1) if itam_vetuste else None,
                    "kpi_unit": "%",
                    "action": actions_by_domain.get("ITAM"),
                    "risk_score": float(risk[5]) if risk and risk[5] else None,
                },
                "parc_automobile": {
                    "rag": normalize_rag(
                        "VERT" if (parc_dispo or 0) >= 90
                        else "AMBRE" if (parc_dispo or 0) >= 80
                        else "ROUGE"
                    ),
                    "kpi_label": "Disponibilité flotte",
                    "kpi_value": round(float(parc_dispo), 1) if parc_dispo else None,
                    "kpi_unit": "%",
                    "action": actions_by_domain.get("Parc Auto"),
                    "risk_score": None,  # pas de Score_ParcAuto dans it_risk_score
                },
                "maintenance": {
                    "rag": normalize_rag(
                        "VERT" if (maint_ratio or 0) >= 70
                        else "AMBRE" if (maint_ratio or 0) >= 50
                        else "ROUGE"
                    ),
                    "kpi_label": "Ratio préventif",
                    "kpi_value": round(float(maint_ratio), 1) if maint_ratio else None,
                    "kpi_unit": "%",
                    "action": actions_by_domain.get("Maintenance"),
                    "risk_score": None,
                },
                "data_bi": {
                    "rag": normalize_rag(
                        "VERT" if (data_qualite or 0) >= 95
                        else "AMBRE" if (data_qualite or 0) >= 85
                        else "ROUGE"
                    ),
                    "kpi_label": "Qualité données",
                    "kpi_value": round(float(data_qualite), 1) if data_qualite else None,
                    "kpi_unit": "%",
                    "action": actions_by_domain.get("Applications"),
                    "risk_score": None,
                },
            },

            # KPIs transversaux (bande du bas)
            "kpis_transversaux": {
                "it_risk_score":     round(float(risk[0]), 1) if risk and risk[0] else None,
                "rag_global":        normalize_rag(risk[7]) if risk else None,
                "digital_adoption_pct": round(float(digital_adoption), 1) if digital_adoption else None,
                "nb_anomalies_if":   int(risk[8]) if risk and risk[8] else 0,
                "nb_alertes_rouge":  int(risk[9]) if risk and risk[9] else 0,
                "nb_alertes_ambre":  int(risk[10]) if risk and risk[10] else 0,
                "top_contributeurs": str(risk[11]) if risk and risk[11] else None,
                "last_update":       str(risk[12]) if risk else None,
            },

            # Point d'attention direction
            "point_attention": {
                "titre":       attention[0] if attention else None,
                "description": attention[1] if attention else None,
                "action":      attention[2] if attention else None,
                "domaine":     attention[3] if attention else None,
                "rag":         normalize_rag(attention[4]) if attention else None,
                "priorite":    attention[5] if attention else None,
            } if attention else None,

            # Prédictions J+7 (surimpression)
            "predictions_j7": [
                {
                    "domaine": r[0], "entite": r[1], "kpi": r[2],
                    "valeur": float(r[3]) if r[3] else None,
                    "rag": normalize_rag(r[4]),
                    "date_alerte": str(r[5]) if r[5] else None,
                }
                for r in preds
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard executive: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard executive")


# ---------------------------------------------------------------------------
# 2. INFRASTRUCTURE (déjà documenté — version complète)
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/infrastructure", tags=["dashboards"])
async def get_infrastructure_dashboard(
    server: Optional[str] = Query(None, description="Filtre par ServerName"),
    date_from: Optional[str] = Query(None, description="Date début YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Date fin YYYY-MM-DD"),
    user: dict = Depends(check_page_access("infrastructure"))
):
    """
    Page 3 — Infrastructure IT (screenshot de référence Power BI)

    Section 1 KPI Cards (Silver) :
      Uptime Moyen ← AVG(Disponibilite_Pct)
      CPU Moyen    ← AVG(CPU_Moyen_Pct)
      RAM Utilisée ← AVG(RAM_Moyen_Pct)
      Stockage     ← AVG(Disk_Moyen_Pct)
      Alertes      ← COUNT zscore_alerts ROUGE

    Section 2 Graphiques :
      Uptime 30j (LineChart)        ← Silver GROUP BY DateKey
      Ressources Moy (BarChart H)   ← AVG CPU/RAM/Disk
      Anomalies/semaine (BarChart)  ← Gold anomalies_detected

    Section 3 Cloud & Prédiction :
      Instances actives  ← COUNT DISTINCT ServerName
      Backup Coverage    ← AVG(Backup_Coverage_Pct)
      Latence avg        ← AVG(Latence_Moyenne_ms)
      Disponibilité      ← dernière valeur Disponibilite_Pct
      Prédiction IA      ← Gold forecast_infra premier ROUGE futur
    """
    try:
        engine = get_db_engine()

        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        if server:
            silver_where += " AND ServerName = :server"
            silver_params["server"] = server
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — KPI Cards
            kpi_q = text(f"""
                SELECT
                    AVG(Disponibilite_Pct)      AS Uptime,
                    AVG(CPU_Moyen_Pct)          AS CPU,
                    AVG(RAM_Moyen_Pct)          AS RAM,
                    AVG(Disk_Moyen_Pct)         AS Disk,
                    AVG(Latence_Moyenne_ms)     AS Latence,
                    AVG(Backup_Coverage_Pct)    AS Backup,
                    AVG(MTBF_Moyen_Hours)       AS MTBF,
                    AVG(MTTR_Moyen_Hours)       AS MTTR,
                    SUM(Nb_Anomalies)           AS Total_Anomalies,
                    COUNT(DISTINCT ServerName)  AS Nb_Serveurs
                FROM Silver.silver_infrastructure
                {silver_where}
            """)
            kpi = conn.execute(kpi_q, silver_params).fetchone()

            # Alertes ROUGE actives (Gold)
            alert_where = "Domaine = 'Infrastructure' AND Est_Active = 1 AND Statut_RAG IN ('ROUGE','RED')"
            if server:
                alert_where += " AND GroupKey = :server"
            alertes_rouge = conn.execute(
                text(f"SELECT COUNT(*) FROM Gold.zscore_alerts WHERE {alert_where}"),
                {"server": server} if server else {}
            ).scalar() or 0

            # Section 2 — Tendances 30j
            trend_q = text(f"""
                SELECT
                    DateKey,
                    AVG(Disponibilite_Pct)  AS Uptime,
                    AVG(CPU_Moyen_Pct)      AS CPU,
                    AVG(RAM_Moyen_Pct)      AS RAM,
                    AVG(Disk_Moyen_Pct)     AS Disk,
                    SUM(Nb_Anomalies)       AS Anomalies
                FROM Silver.silver_infrastructure
                {silver_where}
                  AND DateKey >= DATEADD(day, -30, GETUTCDATE())
                GROUP BY DateKey
                ORDER BY DateKey ASC
            """)
            trends = conn.execute(trend_q, silver_params).fetchall()

            # Section 2 — Ressources moyennes sur période (BarChart horizontal)
            res_q = text(f"""
                SELECT AVG(CPU_Moyen_Pct), AVG(RAM_Moyen_Pct), AVG(Disk_Moyen_Pct)
                FROM Silver.silver_infrastructure {silver_where}
            """)
            res = conn.execute(res_q, silver_params).fetchone()

            # Section 2 — Anomalies par semaine (BarChart Gold)
            ano_where = "Domaine = 'Infrastructure' AND Anomalie_IF = 1 AND DateKey >= DATEADD(day,-60,GETUTCDATE())"
            if server:
                ano_where += " AND ServerName = :server"
            ano_q = text(f"""
                SELECT
                    DATEPART(week, DateKey)    AS Semaine,
                    MIN(CAST(DateKey AS DATE)) AS Debut_Semaine,
                    COUNT(*)                   AS Nb
                FROM Gold.anomalies_detected
                WHERE {ano_where}
                GROUP BY DATEPART(week, DateKey)
                ORDER BY Semaine
            """)
            anomalies_weekly = conn.execute(
                ano_q, {"server": server} if server else {}
            ).fetchall()

            # Section 3 — dernière disponibilité
            last_dispo_q = text("""
                SELECT TOP 1 AVG(Disponibilite_Pct)
                FROM Silver.silver_infrastructure
                WHERE DateKey = (SELECT MAX(DateKey) FROM Silver.silver_infrastructure)
                GROUP BY DateKey
            """)
            last_dispo = conn.execute(last_dispo_q).scalar()

            # Section 3 — Liste serveurs pour dropdown
            srv_list = [r[0] for r in conn.execute(text("""
                SELECT DISTINCT ServerName FROM Silver.silver_infrastructure
                WHERE DateKey >= DATEADD(day,-30,GETUTCDATE()) AND ServerName IS NOT NULL
                ORDER BY ServerName
            """)).fetchall()]

            # Section 3 — Prédiction IA (premier forecast ROUGE futur)
            fc_where = "Is_Forecast = 1 AND Statut_RAG IN ('ROUGE','RED')"
            if server:
                fc_where += " AND server_name = :server"
            fc_q = text(f"""
                SELECT TOP 1 server_name, KPI, DS, Yhat, Statut_RAG, Risk_Score
                FROM Gold.forecast_infra
                WHERE {fc_where}
                ORDER BY DS ASC
            """)
            fc = conn.execute(fc_q, {"server": server} if server else {}).fetchone()

            # Risk score domaine
            risk_q = text("""
                SELECT TOP 1 Score_Infrastructure, Statut_RAG_Global
                FROM Gold.it_risk_score ORDER BY DateKey DESC
            """)
            risk = conn.execute(risk_q).fetchone()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "Infrastructure",
            "filters_applied": {"server": server, "date_from": date_from, "date_to": date_to},

            "kpis": {
                "uptime_moyen_pct":     round(float(kpi[0]), 2) if kpi and kpi[0] else None,
                "cpu_moyen_pct":        round(float(kpi[1]), 2) if kpi and kpi[1] else None,
                "ram_moyen_pct":        round(float(kpi[2]), 2) if kpi and kpi[2] else None,
                "disk_moyen_pct":       round(float(kpi[3]), 2) if kpi and kpi[3] else None,
                "latence_moy_ms":       round(float(kpi[4]), 1) if kpi and kpi[4] else None,
                "backup_coverage_pct":  round(float(kpi[5]), 2) if kpi and kpi[5] else None,
                "mtbf_moyen_hours":     round(float(kpi[6]), 1) if kpi and kpi[6] else None,
                "mttr_moyen_hours":     round(float(kpi[7]), 1) if kpi and kpi[7] else None,
                "total_anomalies":      int(kpi[8]) if kpi and kpi[8] else 0,
                "nb_serveurs":          int(kpi[9]) if kpi and kpi[9] else 0,
                "alertes_rouge":        int(alertes_rouge),
            },

            "resources_avg": {
                "cpu":  round(float(res[0]), 2) if res and res[0] else None,
                "ram":  round(float(res[1]), 2) if res and res[1] else None,
                "disk": round(float(res[2]), 2) if res and res[2] else None,
                "seuil_critique": 90,
            },

            "trends_30j": [
                {
                    "date": str(r[0]),
                    "uptime": round(float(r[1]), 2) if r[1] else None,
                    "cpu":    round(float(r[2]), 2) if r[2] else None,
                    "ram":    round(float(r[3]), 2) if r[3] else None,
                    "disk":   round(float(r[4]), 2) if r[4] else None,
                    "anomalies": int(r[5]) if r[5] else 0,
                }
                for r in trends
            ],

            "anomalies_weekly": [
                {"semaine": int(r[0]), "debut_semaine": str(r[1]), "nb_anomalies": int(r[2])}
                for r in anomalies_weekly
            ],

            "cloud": {
                "instances_actives":   int(kpi[9]) if kpi and kpi[9] else 0,
                "backup_coverage_pct": round(float(kpi[5]), 2) if kpi and kpi[5] else None,
                "latence_avg_ms":      round(float(kpi[4]), 1) if kpi and kpi[4] else None,
                "disponibilite_pct":   round(float(last_dispo), 2) if last_dispo else None,
            },

            "prediction_ia": {
                "server":      fc[0] if fc else None,
                "kpi":         fc[1] if fc else None,
                "date_alerte": str(fc[2]) if fc else None,
                "yhat":        round(float(fc[3]), 2) if fc else None,
                "rag":         normalize_rag(fc[4]) if fc else None,
                "risk_score":  round(float(fc[5]), 2) if fc and fc[5] else None,
            } if fc else None,

            "risk_score": float(risk[0]) if risk and risk[0] else None,
            "rag_status":  normalize_rag(risk[1]) if risk else None,
            "available_servers": srv_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard infrastructure: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard infrastructure")


# ---------------------------------------------------------------------------
# 3. CYBERSÉCURITÉ
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/cybersecurity", tags=["dashboards"])
async def get_cybersec_dashboard(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: dict = Depends(check_page_access("cyber"))
):
    """
    Page 4 — Cybersécurité & Conformité

    Section 1 ÉTAT SÉCURITÉ (Silver) :
      Incidents Critiques ← SUM(Nb_Incidents_Critiques) dernière période
      MTTD Detection      ← AVG(MTTD_Moyen_Hours)
      Vulnérabilités      ← SUM(Total_Vuln_Non_Patchees)
      Patch Systèmes      ← AVG(Systemes_Patches_Moyen_Pct)
      Adoption MFA        ← AVG(MFA_Adoption_Pct)  [+delta vs même période N-1]
      Conformité RGPD/ISO ← AVG(RGPD_Conformite_Pct) cible 95%

    Section 2 TENDANCES 13 mois (Silver) :
      LineChart MFA vs Conformité RGPD (deux courbes)
      BarChart incidents critiques / mois
      LineChart taux phishing évolution

    Section 3 PRÉDICTION M+3 (Gold forecast_cybersec) :
      MFA M+3, RGPD M+3, Incidents M+3, Vulnérabilités M+3
    """
    try:
        engine = get_db_engine()
        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — KPI Cards (dernière valeur disponible)
            kpi_last_q = text("""
                SELECT TOP 1
                    Nb_Incidents_Critiques,
                    MTTD_Moyen_Hours,
                    Total_Vuln_Non_Patchees,
                    Systemes_Patches_Moyen_Pct,
                    MFA_Adoption_Pct,
                    Taux_Phishing_Moyen_Pct,
                    RGPD_Conformite_Pct,
                    DateKey
                FROM Silver.silver_cybersecurity
                ORDER BY DateKey DESC
            """)
            last = conn.execute(kpi_last_q).fetchone()

            # Total incidents sur la période (pour sous-titre "Total année")
            inc_total_q = text(f"""
                SELECT SUM(Nb_Incidents_Critiques)
                FROM Silver.silver_cybersecurity {silver_where}
            """)
            inc_total = conn.execute(inc_total_q, silver_params).scalar() or 0

            # Delta MFA vs même période précédente (approximation : 12 mois avant)
            mfa_prev_q = text("""
                SELECT TOP 1 MFA_Adoption_Pct
                FROM Silver.silver_cybersecurity
                WHERE DateKey <= DATEADD(year, -1, (SELECT MAX(DateKey) FROM Silver.silver_cybersecurity))
                ORDER BY DateKey DESC
            """)
            mfa_prev = conn.execute(mfa_prev_q).scalar()

            # Section 2 — Tendances 13 mois
            trend_q = text(f"""
                SELECT
                    DateKey,
                    Nb_Incidents_Critiques,
                    Total_Vuln_Non_Patchees,
                    Systemes_Patches_Moyen_Pct,
                    MFA_Adoption_Pct,
                    Taux_Phishing_Moyen_Pct,
                    RGPD_Conformite_Pct
                FROM Silver.silver_cybersecurity
                {silver_where}
                  AND DateKey >= DATEADD(month, -13, GETUTCDATE())
                ORDER BY DateKey ASC
            """)
            trends = conn.execute(trend_q, silver_params).fetchall()

            # Section 3 — Prédictions M+3 (3 prochains mois, 4 KPIs clés)
            fc_kpis = ("MFA_Adoption_Pct", "RGPD_Conformite_Pct",
                       "Nb_Incidents_Critiques", "Total_Vuln_Non_Patchees")
            fc_results = {}
            for kpi_name in fc_kpis:
                fc_q = text("""
                    SELECT TOP 3 DS, Yhat, Statut_RAG
                    FROM Gold.forecast_cybersec
                    WHERE KPI = :kpi AND Is_Forecast = 1 AND DS > GETUTCDATE()
                    ORDER BY DS ASC
                """)
                rows = conn.execute(fc_q, {"kpi": kpi_name}).fetchall()
                if rows:
                    # Valeur M+3 = moyenne des 3 prochains mois
                    fc_results[kpi_name] = {
                        "yhat_m3": round(float(sum(r[1] for r in rows) / len(rows)), 1),
                        "rag": normalize_rag(rows[-1][2]),
                        "date_m3": str(rows[-1][0]),
                    }

            # Alertes actives cybersécurité
            alertes_q = text("""
                SELECT COUNT(*) FROM Gold.zscore_alerts
                WHERE Domaine = 'Cybersécurité'
                  AND Est_Active = 1
                  AND Statut_RAG IN ('ROUGE', 'RED')
            """)
            alertes_rouge = conn.execute(alertes_q).scalar() or 0

            # Risk score domaine
            risk_q = text("""
                SELECT TOP 1 Score_Cybersec, Statut_RAG_Global
                FROM Gold.it_risk_score ORDER BY DateKey DESC
            """)
            risk = conn.execute(risk_q).fetchone()

        mfa_delta = None
        if last and mfa_prev and last[4]:
            mfa_delta = round(float(last[4]) - float(mfa_prev), 1)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "Cybersécurité",
            "filters_applied": {"date_from": date_from, "date_to": date_to},

            # Section 1 — ÉTAT SÉCURITÉ
            "kpis": {
                "incidents_critiques":      int(last[0]) if last and last[0] else 0,
                "incidents_total_periode":  int(inc_total),
                "mttd_moyen_hours":         round(float(last[1]), 2) if last and last[1] else None,
                "vuln_non_patchees":        int(last[2]) if last and last[2] else 0,
                "systemes_patches_pct":     round(float(last[3]), 1) if last and last[3] else None,
                "mfa_adoption_pct":         round(float(last[4]), 1) if last and last[4] else None,
                "mfa_delta_vs_an_precedent": mfa_delta,
                "taux_phishing_pct":        round(float(last[5]), 2) if last and last[5] else None,
                "rgpd_conformite_pct":      round(float(last[6]), 1) if last and last[6] else None,
                "rgpd_cible":               95,
                "alertes_rouge":            int(alertes_rouge),
                "derniere_date":            str(last[7]) if last else None,

                # RAG calculés (pour coloration des cards)
                "rag_incidents":   normalize_rag("VERT" if (last[0] if last else 1) == 0 else "ROUGE"),
                "rag_mttd":        normalize_rag("VERT" if (last[1] if last else 99) < 2 else "AMBRE"),
                "rag_vuln":        normalize_rag("VERT" if (last[2] if last else 1) == 0 else "ROUGE"),
                "rag_patch":       normalize_rag("VERT" if (last[3] if last else 0) >= 95 else "AMBRE"),
                "rag_mfa":         normalize_rag("VERT" if (last[4] if last else 0) >= 95 else "AMBRE"),
                "rag_rgpd":        normalize_rag("VERT" if (last[6] if last else 0) >= 95 else "AMBRE"),
            },

            # Section 2 — Tendances 13 mois
            "trends_13m": [
                {
                    "date":             str(r[0]),
                    "incidents":        int(r[1]) if r[1] else 0,
                    "vuln":             int(r[2]) if r[2] else 0,
                    "patch_pct":        round(float(r[3]), 1) if r[3] else None,
                    "mfa_pct":          round(float(r[4]), 1) if r[4] else None,
                    "phishing_pct":     round(float(r[5]), 2) if r[5] else None,
                    "rgpd_pct":         round(float(r[6]), 1) if r[6] else None,
                }
                for r in trends
            ],

            # Section 3 — Prédictions M+3
            "predictions_m3": {
                "mfa_m3":     fc_results.get("MFA_Adoption_Pct"),
                "rgpd_m3":    fc_results.get("RGPD_Conformite_Pct"),
                "incidents_m3": fc_results.get("Nb_Incidents_Critiques"),
                "vuln_m3":    fc_results.get("Total_Vuln_Non_Patchees"),
            },

            "risk_score": float(risk[0]) if risk and risk[0] else None,
            "rag_status":  normalize_rag(risk[1]) if risk else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard cybersec: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard cybersécurité")


# ---------------------------------------------------------------------------
# 4. ITSM / SERVICE DESK
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/itsm", tags=["dashboards"])
async def get_itsm_dashboard(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    priority: Optional[str] = Query(None, description="Filtre priorité: P1, P2, P3"),
    user: dict = Depends(check_page_access("itsm"))
):
    """
    Page 5 — Service Desk & Support

    Section 1 KPIs SERVICE DESK (Silver) :
      Volume Tickets/Jour ← AVG(Volume_Total) dernier jour enregistré
      SLA Moyen           ← AVG(SLA_Moyen_Pct) cible ≥ 95%
      FCR                 ← AVG(FCR_Moyen_Pct) cible ≥ 70%
      MTTR Moyen          ← AVG(MTTR_Moyen_Hours) P1 ≤ 4h
      CSAT Moyen          ← AVG(CSAT_Moyen) /5
      Backlog Total       ← SUM(Backlog_Total) dernière valeur

    Section 2 VOLUMÉTRIE & TENDANCES (Silver) :
      BarChart stacked P1/P2/P3 — 13 mois
      LineChart Backlog évolution 13 mois
      LineChart SLA réel + prédiction J+7 (Gold forecast_itsm)

    Section 3 CHARGE TECHNICIENS (non disponible en Silver — placeholder)
      Prédiction Volume J+7 ← Gold forecast_itsm KPI=Volume_Total horizon=7j
    """
    try:
        engine = get_db_engine()
        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — KPI Cards : valeur du dernier jour enregistré
            last_q = text("""
                SELECT TOP 1
                    Volume_Total, Total_P1, Total_P2, Total_P3,
                    Backlog_Total, SLA_Moyen_Pct, FCR_Moyen_Pct,
                    MTTR_Moyen_Hours, CSAT_Moyen, Pct_Tickets_P1, DateKey
                FROM Silver.silver_itsm
                ORDER BY DateKey DESC
            """)
            last = conn.execute(last_q).fetchone()

            # Moyennes sur la période filtrée (pour sous-titres et tendances)
            avg_q = text(f"""
                SELECT
                    AVG(CAST(Volume_Total AS float)),
                    AVG(SLA_Moyen_Pct),
                    AVG(FCR_Moyen_Pct),
                    AVG(MTTR_Moyen_Hours),
                    AVG(CSAT_Moyen),
                    SUM(Backlog_Total),
                    SUM(Total_P1), SUM(Total_P2), SUM(Total_P3)
                FROM Silver.silver_itsm
                {silver_where}
            """)
            avg = conn.execute(avg_q, silver_params).fetchone()

            # Section 2 — Volumétrie 13 mois (P1/P2/P3 stacked + Backlog)
            trend_q = text(f"""
                SELECT
                    DateKey,
                    Total_P1, Total_P2, Total_P3,
                    Volume_Total, Backlog_Total,
                    SLA_Moyen_Pct, MTTR_Moyen_Hours
                FROM Silver.silver_itsm
                {silver_where}
                  AND DateKey >= DATEADD(month, -13, GETUTCDATE())
                ORDER BY DateKey ASC
            """)
            trends = conn.execute(trend_q, silver_params).fetchall()

            # Section 2 — SLA + Prédiction J+7 (8 semaines réel + prédiction)
            sla_weekly_q = text(f"""
                SELECT
                    DATEPART(week, DateKey) AS Semaine,
                    MIN(CAST(DateKey AS DATE)) AS Debut,
                    AVG(SLA_Moyen_Pct) AS SLA_Reel
                FROM Silver.silver_itsm
                {silver_where}
                  AND DateKey >= DATEADD(week, -8, GETUTCDATE())
                GROUP BY DATEPART(week, DateKey)
                ORDER BY Semaine ASC
            """)
            sla_weekly = conn.execute(sla_weekly_q, silver_params).fetchall()

            # Prédiction SLA J+7 (Gold)
            sla_fc_q = text("""
                SELECT TOP 7 DS, Yhat, Statut_RAG
                FROM Gold.forecast_itsm
                WHERE KPI = 'SLA_Moyen_Pct' AND Is_Forecast = 1 AND DS > GETUTCDATE()
                ORDER BY DS ASC
            """)
            sla_fc = conn.execute(sla_fc_q).fetchall()

            # Prédiction Volume J+7
            vol_fc_q = text("""
                SELECT TOP 7 DS, Yhat, Yhat_Lower, Yhat_Upper
                FROM Gold.forecast_itsm
                WHERE KPI = 'Volume_Total' AND Is_Forecast = 1 AND DS > GETUTCDATE()
                ORDER BY DS ASC
            """)
            vol_fc = conn.execute(vol_fc_q).fetchall()

            # Prédiction IA narrative : premier KPI ROUGE futur
            pred_ia_q = text("""
                SELECT TOP 1 KPI, DS, Yhat, Statut_RAG
                FROM Gold.forecast_itsm
                WHERE Is_Forecast = 1
                  AND Statut_RAG IN ('ROUGE', 'RED')
                  AND DS > GETUTCDATE()
                ORDER BY DS ASC
            """)
            pred_ia = conn.execute(pred_ia_q).fetchone()

            # Risk score ITSM
            risk_q = text("""
                SELECT TOP 1 Score_ITSM, Statut_RAG_Global
                FROM Gold.it_risk_score ORDER BY DateKey DESC
            """)
            risk = conn.execute(risk_q).fetchone()

        # Calcul delta backlog vs 12 mois avant (simplifié : premier vs dernier)
        backlog_delta = None
        if len(trends) >= 2 and trends[0][4] and trends[-1][4]:
            backlog_delta = int(trends[-1][4]) - int(trends[0][4])

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "ITSM",
            "filters_applied": {"date_from": date_from, "date_to": date_to, "priority": priority},

            # Section 1 — KPI Cards (valeur dernière journée)
            "kpis": {
                "volume_tickets_jour":  int(last[0]) if last and last[0] else None,
                "total_p1":             int(last[1]) if last and last[1] else 0,
                "total_p2":             int(last[2]) if last and last[2] else 0,
                "total_p3":             int(last[3]) if last and last[3] else 0,
                "backlog_total":        int(last[4]) if last and last[4] else 0,
                "backlog_delta_13m":    backlog_delta,
                "sla_moyen_pct":        round(float(last[5]), 1) if last and last[5] else None,
                "sla_cible":            95,
                "fcr_moyen_pct":        round(float(last[6]), 1) if last and last[6] else None,
                "fcr_cible":            70,
                "mttr_moyen_hours":     round(float(last[7]), 1) if last and last[7] else None,
                "mttr_p1_cible":        4,
                "csat_moyen":           round(float(last[8]), 2) if last and last[8] else None,
                "pct_tickets_p1":       round(float(last[9]), 1) if last and last[9] else None,
                "derniere_date":        str(last[10]) if last else None,

                # Totaux période
                "periode_volume_total": int(avg[0]) if avg and avg[0] else None,
                "periode_sla_moy":      round(float(avg[1]), 1) if avg and avg[1] else None,
                "periode_fcr_moy":      round(float(avg[2]), 1) if avg and avg[2] else None,
                "periode_mttr_moy":     round(float(avg[3]), 1) if avg and avg[3] else None,
                "periode_csat_moy":     round(float(avg[4]), 2) if avg and avg[4] else None,
                "periode_backlog":      int(avg[5]) if avg and avg[5] else 0,
                "periode_p1_total":     int(avg[6]) if avg and avg[6] else 0,
                "periode_p2_total":     int(avg[7]) if avg and avg[7] else 0,
                "periode_p3_total":     int(avg[8]) if avg and avg[8] else 0,
            },

            # Section 2 — Volumétrie 13 mois (BarChart stacked + LineChart Backlog)
            "trends_13m": [
                {
                    "date":         str(r[0]),
                    "p1":           int(r[1]) if r[1] else 0,
                    "p2":           int(r[2]) if r[2] else 0,
                    "p3":           int(r[3]) if r[3] else 0,
                    "volume_total": int(r[4]) if r[4] else 0,
                    "backlog":      int(r[5]) if r[5] else 0,
                    "sla_pct":      round(float(r[6]), 1) if r[6] else None,
                    "mttr":         round(float(r[7]), 1) if r[7] else None,
                }
                for r in trends
            ],

            # Section 2 — SLA hebdo réel + prédiction J+7 (LineChart double)
            "sla_weekly": [
                {
                    "semaine":    int(r[0]),
                    "debut":      str(r[1]),
                    "sla_reel":   round(float(r[2]), 1) if r[2] else None,
                }
                for r in sla_weekly
            ],
            "sla_prediction_j7": [
                {
                    "date":  str(r[0]),
                    "yhat":  round(float(r[1]), 1) if r[1] else None,
                    "rag":   normalize_rag(r[2]),
                }
                for r in sla_fc
            ],

            # Section 3 — Prédiction volume J+7
            "prediction_volume_j7": {
                "points": [
                    {
                        "date":  str(r[0]),
                        "yhat":  round(float(r[1]), 0) if r[1] else None,
                        "lower": round(float(r[2]), 0) if r[2] else None,
                        "upper": round(float(r[3]), 0) if r[3] else None,
                    }
                    for r in vol_fc
                ],
                "tendance_pct": round(
                    ((float(vol_fc[-1][1]) - float(vol_fc[0][1])) / float(vol_fc[0][1])) * 100, 1
                ) if vol_fc and vol_fc[0][1] and vol_fc[-1][1] else None,
            } if vol_fc else None,

            # Prédiction IA narrative
            "prediction_ia": {
                "kpi":         pred_ia[0] if pred_ia else None,
                "date_alerte": str(pred_ia[1]) if pred_ia else None,
                "yhat":        round(float(pred_ia[2]), 1) if pred_ia and pred_ia[2] else None,
                "rag":         normalize_rag(pred_ia[3]) if pred_ia else None,
            } if pred_ia else None,

            "risk_score": float(risk[0]) if risk and risk[0] else None,
            "rag_status":  normalize_rag(risk[1]) if risk else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard ITSM: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard ITSM")


# ---------------------------------------------------------------------------
# 5. APPLICATIONS & BI
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/applications", tags=["dashboards"])
async def get_applications_dashboard(
    app: Optional[str] = Query(None, description="Filtre par Application_Name"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: dict = Depends(check_page_access("apps"))
):
    """
    Page Applications & BI

    Section 1 KPIs (Silver) :
      Disponibilité moy   ← AVG(Disponibilite_Pct) cible ≥ 99%
      Temps réponse       ← AVG(Temps_Reponse_Moyen_ms)
      Bugs critiques      ← SUM(Nb_Bugs_Critiques)
      Qualité données     ← AVG(Qualite_Donnees_Pct)
      Adoption Power BI   ← AVG(Adoption_PowerBI_Pct)
      Nb applications     ← COUNT DISTINCT Application_Name

    Section 2 Tendances (Silver) :
      LineChart disponibilité par app sur période
      BarChart bugs critiques par mois
      LineChart temps de réponse évolution

    Section 3 Prédiction IA (Gold forecast_apps) :
      Premier KPI ROUGE futur par application
    """
    try:
        engine = get_db_engine()
        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        if app:
            silver_where += " AND Application_Name = :app"
            silver_params["app"] = app
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — KPIs agrégés
            kpi_q = text(f"""
                SELECT
                    AVG(Disponibilite_Pct)          AS Dispo,
                    AVG(Temps_Reponse_Moyen_ms)     AS TR_Moy,
                    AVG(Temps_Reponse_Max_ms)        AS TR_Max,
                    SUM(Nb_Bugs_Critiques)           AS Bugs,
                    AVG(Qualite_Donnees_Pct)         AS Qualite,
                    AVG(Adoption_PowerBI_Pct)        AS Adoption,
                    COUNT(DISTINCT Application_Name) AS Nb_Apps
                FROM Silver.silver_applications
                {silver_where}
            """)
            kpi = conn.execute(kpi_q, silver_params).fetchone()

            # Alertes applications actives
            alertes_q = text("""
                SELECT COUNT(*) FROM Gold.zscore_alerts
                WHERE Domaine = 'Applications'
                  AND Est_Active = 1
                  AND Statut_RAG IN ('ROUGE', 'RED')
            """)
            alertes_rouge = conn.execute(alertes_q).scalar() or 0

            # Section 2 — Tendances 13 mois
            trend_q = text(f"""
                SELECT
                    DateKey, Application_Name,
                    Disponibilite_Pct, Temps_Reponse_Moyen_ms,
                    Nb_Bugs_Critiques, Qualite_Donnees_Pct
                FROM Silver.silver_applications
                {silver_where}
                  AND DateKey >= DATEADD(month, -13, GETUTCDATE())
                ORDER BY DateKey ASC, Application_Name
            """)
            trends = conn.execute(trend_q, silver_params).fetchall()

            # Disponibilité par application (dernière période pour ranking)
            dispo_by_app_q = text(f"""
                SELECT
                    Application_Name,
                    AVG(Disponibilite_Pct) AS Dispo,
                    AVG(Temps_Reponse_Moyen_ms) AS TR,
                    SUM(Nb_Bugs_Critiques) AS Bugs
                FROM Silver.silver_applications
                {silver_where}
                GROUP BY Application_Name
                ORDER BY Dispo ASC
            """)
            dispo_by_app = conn.execute(dispo_by_app_q, silver_params).fetchall()

            # Liste des applications disponibles (pour dropdown)
            apps_list = [r[0] for r in conn.execute(text("""
                SELECT DISTINCT Application_Name FROM Silver.silver_applications
                WHERE Application_Name IS NOT NULL ORDER BY Application_Name
            """)).fetchall()]

            # Section 3 — Prédiction IA (premier ROUGE futur)
            fc_where = "Is_Forecast = 1 AND Statut_RAG IN ('ROUGE','RED') AND DS > GETUTCDATE()"
            if app:
                fc_where += " AND application_name = :app"
            fc_q = text(f"""
                SELECT TOP 1 application_name, KPI, DS, Yhat, Statut_RAG, Risk_Score
                FROM Gold.forecast_apps
                WHERE {fc_where}
                ORDER BY DS ASC
            """)
            fc = conn.execute(fc_q, {"app": app} if app else {}).fetchone()

            # Risk score
            risk_q = text("""
                SELECT TOP 1 Score_Applications, Statut_RAG_Global
                FROM Gold.it_risk_score ORDER BY DateKey DESC
            """)
            risk = conn.execute(risk_q).fetchone()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "Applications",
            "filters_applied": {"app": app, "date_from": date_from, "date_to": date_to},

            "kpis": {
                "disponibilite_moy_pct":    round(float(kpi[0]), 2) if kpi and kpi[0] else None,
                "disponibilite_cible":      99,
                "temps_reponse_moy_ms":     round(float(kpi[1]), 1) if kpi and kpi[1] else None,
                "temps_reponse_max_ms":     round(float(kpi[2]), 1) if kpi and kpi[2] else None,
                "bugs_critiques":           int(kpi[3]) if kpi and kpi[3] else 0,
                "qualite_donnees_pct":      round(float(kpi[4]), 1) if kpi and kpi[4] else None,
                "adoption_powerbi_pct":     round(float(kpi[5]), 1) if kpi and kpi[5] else None,
                "nb_applications":          int(kpi[6]) if kpi and kpi[6] else 0,
                "alertes_rouge":            int(alertes_rouge),
            },

            "trends_13m": [
                {
                    "date":       str(r[0]),
                    "app":        str(r[1]) if r[1] else "Global",
                    "dispo":      round(float(r[2]), 2) if r[2] else None,
                    "tr_ms":      round(float(r[3]), 1) if r[3] else None,
                    "bugs":       int(r[4]) if r[4] else 0,
                    "qualite":    round(float(r[5]), 1) if r[5] else None,
                }
                for r in trends
            ],

            "dispo_by_app": [
                {
                    "app":  str(r[0]),
                    "dispo": round(float(r[1]), 2) if r[1] else None,
                    "tr_ms": round(float(r[2]), 1) if r[2] else None,
                    "bugs":  int(r[3]) if r[3] else 0,
                    "rag": normalize_rag(
                        "VERT" if (r[1] or 0) >= 99
                        else "AMBRE" if (r[1] or 0) >= 95
                        else "ROUGE"
                    ),
                }
                for r in dispo_by_app
            ],

            "prediction_ia": {
                "app":         fc[0] if fc else None,
                "kpi":         fc[1] if fc else None,
                "date_alerte": str(fc[2]) if fc else None,
                "yhat":        round(float(fc[3]), 2) if fc and fc[3] else None,
                "rag":         normalize_rag(fc[4]) if fc else None,
                "risk_score":  round(float(fc[5]), 2) if fc and fc[5] else None,
            } if fc else None,

            "risk_score":      float(risk[0]) if risk and risk[0] else None,
            "rag_status":       normalize_rag(risk[1]) if risk else None,
            "available_apps":  apps_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard applications: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard applications")


# ---------------------------------------------------------------------------
# 6. ITAM — Parc Informatique
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/itam", tags=["dashboards"])
async def get_itam_dashboard(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: dict = Depends(check_page_access("itam"))
):
    """
    Page ITAM — Parc Informatique (maquette imaginée selon logique métier)

    Section 1 KPIs (Silver — granularité mensuelle) :
      Total Postes         ← MAX(Total_Postes)
      Vétusté > 5 ans      ← AVG(Vetuste_Moyen_Pct) alerte si > 30%
      TCO moyen / poste    ← AVG(TCO_Moyen_Par_Poste_MAD) en MAD
      TCO total            ← SUM(TCO_Total_MAD)
      Conformité licences  ← AVG(Conformite_Licences_Pct) cible ≥ 95%
      Licences inutilisées ← SUM(Total_Licences_Inutilisees)
      Délai mise à dispo   ← AVG(Delai_Mise_Dispo_Moyen_Jours) cible ≤ 3j
      CMDB couverture      ← AVG(CMDB_Couverture_Pct) cible ≥ 95%

    Section 2 Tendances (Silver) :
      LineChart vétusté évolution
      LineChart TCO évolution
      BarChart licences inutilisées par mois

    Section 3 Prédiction IA (Gold forecast_itam) :
      Vétusté M+6, TCO M+6, Conformité licences M+6
    """
    try:
        engine = get_db_engine()
        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — KPIs agrégés (dernière valeur + moyenne période)
            last_q = text("""
                SELECT TOP 1
                    Total_Postes, Vetuste_Moyen_Pct, TCO_Moyen_Par_Poste_MAD,
                    TCO_Total_MAD, Conformite_Licences_Pct,
                    Total_Licences_Inutilisees, Delai_Mise_Dispo_Moyen_Jours,
                    CMDB_Couverture_Pct, DateKey
                FROM Silver.silver_itam
                ORDER BY DateKey DESC
            """)
            last = conn.execute(last_q).fetchone()

            # Tendance TCO vs mois précédent
            prev_tco_q = text("""
                SELECT TOP 1 TCO_Moyen_Par_Poste_MAD
                FROM Silver.silver_itam
                WHERE DateKey < (SELECT MAX(DateKey) FROM Silver.silver_itam)
                ORDER BY DateKey DESC
            """)
            prev_tco = conn.execute(prev_tco_q).scalar()

            # Section 2 — Tendances sur 13 mois
            trend_q = text(f"""
                SELECT
                    DateKey,
                    Total_Postes, Vetuste_Moyen_Pct,
                    TCO_Moyen_Par_Poste_MAD, TCO_Total_MAD,
                    Conformite_Licences_Pct, Total_Licences_Inutilisees,
                    Delai_Mise_Dispo_Moyen_Jours, CMDB_Couverture_Pct
                FROM Silver.silver_itam
                {silver_where}
                  AND DateKey >= DATEADD(month, -13, GETUTCDATE())
                ORDER BY DateKey ASC
            """)
            trends = conn.execute(trend_q, silver_params).fetchall()

            # Alertes ITAM actives
            alertes_q = text("""
                SELECT COUNT(*) FROM Gold.zscore_alerts
                WHERE Domaine = 'ITAM'
                  AND Est_Active = 1
                  AND Statut_RAG IN ('ROUGE', 'RED')
            """)
            alertes_rouge = conn.execute(alertes_q).scalar() or 0

            # Section 3 — Prédictions M+6 (3 KPIs clés)
            fc_kpis = ("Vetuste_Moyen_Pct", "TCO_Moyen_Par_Poste_MAD", "Conformite_Licences_Pct")
            fc_results = {}
            for kpi_name in fc_kpis:
                fc_q = text("""
                    SELECT TOP 6 DS, Yhat, Statut_RAG
                    FROM Gold.forecast_itam
                    WHERE KPI = :kpi AND Is_Forecast = 1 AND DS > GETUTCDATE()
                    ORDER BY DS ASC
                """)
                rows = conn.execute(fc_q, {"kpi": kpi_name}).fetchall()
                if rows:
                    fc_results[kpi_name] = {
                        "yhat_m6": round(float(rows[-1][1]), 1) if rows[-1][1] else None,
                        "rag":     normalize_rag(rows[-1][2]),
                        "date_m6": str(rows[-1][0]),
                        "points":  [{"date": str(r[0]), "yhat": round(float(r[1]), 1) if r[1] else None} for r in rows],
                    }

            # Risk score ITAM
            risk_q = text("""
                SELECT TOP 1 Score_ITAM, Statut_RAG_Global
                FROM Gold.it_risk_score ORDER BY DateKey DESC
            """)
            risk = conn.execute(risk_q).fetchone()

        tco_delta = None
        if last and prev_tco and last[2]:
            tco_delta = round(((float(last[2]) - float(prev_tco)) / float(prev_tco)) * 100, 1)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "ITAM",
            "filters_applied": {"date_from": date_from, "date_to": date_to},

            # Section 1 — KPI Cards
            "kpis": {
                "total_postes":             int(last[0]) if last and last[0] else None,
                "vetuste_pct":              round(float(last[1]), 1) if last and last[1] else None,
                "vetuste_seuil_alerte":     30,
                "tco_moyen_par_poste_mad":  round(float(last[2]), 0) if last and last[2] else None,
                "tco_delta_vs_mois_prec":   tco_delta,
                "tco_total_mad":            round(float(last[3]), 0) if last and last[3] else None,
                "conformite_licences_pct":  round(float(last[4]), 1) if last and last[4] else None,
                "conformite_cible":         95,
                "licences_inutilisees":     int(last[5]) if last and last[5] else 0,
                "delai_mise_dispo_jours":   round(float(last[6]), 1) if last and last[6] else None,
                "delai_cible":              3,
                "cmdb_couverture_pct":      round(float(last[7]), 1) if last and last[7] else None,
                "cmdb_cible":              95,
                "alertes_rouge":            int(alertes_rouge),
                "derniere_date":            str(last[8]) if last else None,

                # RAG cards
                "rag_vetuste":    normalize_rag("VERT" if (last[1] or 100) <= 20 else "AMBRE" if (last[1] or 100) <= 35 else "ROUGE"),
                "rag_licences":   normalize_rag("VERT" if (last[4] or 0) >= 95 else "AMBRE" if (last[4] or 0) >= 80 else "ROUGE"),
                "rag_delai":      normalize_rag("VERT" if (last[6] or 99) <= 3 else "AMBRE" if (last[6] or 99) <= 5 else "ROUGE"),
                "rag_cmdb":       normalize_rag("VERT" if (last[7] or 0) >= 95 else "AMBRE"),
            },

            # Section 2 — Tendances 13 mois
            "trends_13m": [
                {
                    "date":               str(r[0]),
                    "total_postes":       int(r[1]) if r[1] else None,
                    "vetuste_pct":        round(float(r[2]), 1) if r[2] else None,
                    "tco_par_poste":      round(float(r[3]), 0) if r[3] else None,
                    "tco_total":          round(float(r[4]), 0) if r[4] else None,
                    "conformite_licences": round(float(r[5]), 1) if r[5] else None,
                    "licences_inutilisees": int(r[6]) if r[6] else 0,
                    "delai_mise_dispo":   round(float(r[7]), 1) if r[7] else None,
                    "cmdb_couverture":    round(float(r[8]), 1) if r[8] else None,
                }
                for r in trends
            ],

            # Section 3 — Prédictions M+6
            "predictions_m6": {
                "vetuste_m6":    fc_results.get("Vetuste_Moyen_Pct"),
                "tco_m6":        fc_results.get("TCO_Moyen_Par_Poste_MAD"),
                "licences_m6":   fc_results.get("Conformite_Licences_Pct"),
            },

            "risk_score": float(risk[0]) if risk and risk[0] else None,
            "rag_status":  normalize_rag(risk[1]) if risk else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard ITAM: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard ITAM")


# ---------------------------------------------------------------------------
# 7. PARC AUTOMOBILE
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/parc-auto", tags=["dashboards"])
async def get_fleet_dashboard(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    vehicule_dept: Optional[str] = Query(None, description="Filtre Véhicule/Département"),
    user: dict = Depends(check_page_access("parc_auto"))
):
    """
    Page 8 — Parc Automobile (screenshot de référence Power BI)

    Section 1 ÉTAT DE LA FLOTTE (Silver) :
      Flotte Totale         ← MAX(Flotte_Totale) — périmètre constant
      Disponibilité Flotte  ← AVG(Disponibilite_Pct) dernière valeur [AMBRE si < 90%]
      Sinistres ce mois     ← SUM(Nb_Sinistres) mois courant
      Conso Moy L/100km     ← AVG(Conso_Moyenne_L100km) stable 13 mois
      TCO Moyen / Véhicule  ← AVG(TCO_Moyen_Par_Vehicule_MAD) [delta vs N-1]
      Taux Sinistralité     ← AVG(Taux_Sinistralite_Pct) [VERT si 0]

    Section 2 TENDANCES FLOTTE 13 mois (Silver) :
      LineChart Disponibilité % — 13 mois
      BarChart Sinistres par mois (avec annotation pic)
      LineChart Conso L/100km évolution

    Section 3 TCO & PRÉDICTION M+3 (Silver points clés + Gold forecast_parc_auto) :
      TCO points clés (barres mensuelles colorées RAG)
      Prédictions M+3 : Conso M+3, Sinistres M+3, TCO M+3
    """
    try:
        engine = get_db_engine()
        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — Dernière valeur disponible
            last_q = text("""
                SELECT TOP 1
                    Flotte_Totale, Vehicules_Disponibles, Disponibilite_Pct,
                    Nb_Sinistres, Taux_Sinistralite_Pct,
                    Conso_Totale_L, Conso_Moyenne_L100km,
                    TCO_Moyen_Par_Vehicule_MAD, DateKey
                FROM Silver.silver_parc_auto
                ORDER BY DateKey DESC
            """)
            last = conn.execute(last_q).fetchone()

            # Moy disponibilité sur la période (sous-titre "Moy : 90.1%")
            avg_dispo_q = text(f"""
                SELECT AVG(Disponibilite_Pct), AVG(TCO_Moyen_Par_Vehicule_MAD)
                FROM Silver.silver_parc_auto {silver_where}
            """)
            avg_row = conn.execute(avg_dispo_q, silver_params).fetchone()

            # TCO delta vs an précédent
            prev_tco_q = text("""
                SELECT TOP 1 TCO_Moyen_Par_Vehicule_MAD
                FROM Silver.silver_parc_auto
                WHERE DateKey <= DATEADD(year, -1, (SELECT MAX(DateKey) FROM Silver.silver_parc_auto))
                ORDER BY DateKey DESC
            """)
            prev_tco = conn.execute(prev_tco_q).scalar()

            # Sinistres du mois courant
            sinistres_mois_q = text("""
                SELECT SUM(Nb_Sinistres)
                FROM Silver.silver_parc_auto
                WHERE YEAR(DateKey) = YEAR(GETUTCDATE())
                  AND MONTH(DateKey) = MONTH(GETUTCDATE())
            """)
            sinistres_mois = conn.execute(sinistres_mois_q).scalar() or 0

            # Section 2 — Tendances 13 mois
            trend_q = text(f"""
                SELECT
                    DateKey,
                    Flotte_Totale, Vehicules_Disponibles, Disponibilite_Pct,
                    Nb_Sinistres, Taux_Sinistralite_Pct,
                    Conso_Totale_L, Conso_Moyenne_L100km,
                    TCO_Moyen_Par_Vehicule_MAD
                FROM Silver.silver_parc_auto
                {silver_where}
                  AND DateKey >= DATEADD(month, -13, GETUTCDATE())
                ORDER BY DateKey ASC
            """)
            trends = conn.execute(trend_q, silver_params).fetchall()

            # Pic de sinistres (pour annotation graphique)
            pic_q = text(f"""
                SELECT TOP 1 DateKey, Nb_Sinistres
                FROM Silver.silver_parc_auto
                {silver_where}
                ORDER BY Nb_Sinistres DESC
            """)
            pic = conn.execute(pic_q, silver_params).fetchone()

            # Section 3 — TCO points clés (4 points : Avr, Aoû, Déc, Avr+1)
            tco_points_q = text(f"""
                SELECT DateKey, TCO_Moyen_Par_Vehicule_MAD
                FROM Silver.silver_parc_auto
                {silver_where}
                ORDER BY DateKey ASC
            """)
            tco_all = conn.execute(tco_points_q, silver_params).fetchall()
            # Sélectionner 4 points représentatifs (début, milieu-1, milieu-2, fin)
            tco_points = []
            if tco_all:
                n = len(tco_all)
                indices = [0, n // 3, (2 * n) // 3, n - 1] if n >= 4 else list(range(n))
                for i in indices:
                    r = tco_all[i]
                    tco_points.append({
                        "date":  str(r[0]),
                        "tco":   round(float(r[1]), 0) if r[1] else None,
                        "rag":   normalize_rag(
                            "VERT" if (r[1] or 0) < (avg_row[1] or 50000)
                            else "ROUGE" if (r[1] or 0) > (avg_row[1] or 50000) * 1.1
                            else "AMBRE"
                        ),
                    })

            # Section 3 — Prédictions M+3 (Conso, Sinistres, TCO)
            fc_kpis = {
                "Conso_Moyenne_L100km":     "conso_m3",
                "Nb_Sinistres":             "sinistres_m3",
                "TCO_Moyen_Par_Vehicule_MAD": "tco_m3",
            }
            fc_results = {}
            for kpi_name, alias in fc_kpis.items():
                fc_q = text("""
                    SELECT TOP 3 DS, Yhat, Statut_RAG
                    FROM Gold.forecast_parc_auto
                    WHERE KPI = :kpi AND Is_Forecast = 1 AND DS > GETUTCDATE()
                    ORDER BY DS ASC
                """)
                rows = conn.execute(fc_q, {"kpi": kpi_name}).fetchall()
                if rows:
                    fc_results[alias] = {
                        "yhat_m3":  round(float(rows[-1][1]), 1) if rows[-1][1] else None,
                        "rag":      normalize_rag(rows[-1][2]),
                        "date_m3":  str(rows[-1][0]),
                    }

        tco_delta = None
        if last and prev_tco and last[7]:
            tco_delta = round(((float(last[7]) - float(prev_tco)) / float(prev_tco)) * 100, 1)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "Parc Auto",
            "filters_applied": {"date_from": date_from, "date_to": date_to, "vehicule_dept": vehicule_dept},

            # Section 1 — ÉTAT DE LA FLOTTE
            "kpis": {
                "flotte_totale":            int(last[0]) if last and last[0] else None,
                "vehicules_disponibles":    int(last[1]) if last and last[1] else None,
                "disponibilite_pct":        round(float(last[2]), 1) if last and last[2] else None,
                "disponibilite_moy_periode": round(float(avg_row[0]), 1) if avg_row and avg_row[0] else None,
                "sinistres_mois_courant":   int(sinistres_mois),
                "taux_sinistralite_pct":    round(float(last[4]), 1) if last and last[4] else None,
                "conso_totale_l":           round(float(last[5]), 0) if last and last[5] else None,
                "conso_moy_l100km":         round(float(last[6]), 1) if last and last[6] else None,
                "tco_moy_par_vehicule_mad": round(float(last[7]), 0) if last and last[7] else None,
                "tco_delta_vs_an_prec":     tco_delta,
                "derniere_date":            str(last[8]) if last else None,

                # RAG cards (cohérent avec les couleurs du screenshot)
                "rag_disponibilite": normalize_rag(
                    "VERT" if (last[2] or 0) >= 90 else "AMBRE" if (last[2] or 0) >= 80 else "ROUGE"
                ),
                "rag_sinistralite":  normalize_rag("VERT" if (last[4] or 1) == 0 else "AMBRE"),
                "rag_tco": normalize_rag(
                    "VERT" if tco_delta is not None and tco_delta <= 0
                    else "AMBRE" if tco_delta is not None and tco_delta <= 5
                    else "ROUGE"
                ),
            },

            # Section 2 — TENDANCES 13 mois
            "trends_13m": [
                {
                    "date":         str(r[0]),
                    "flotte":       int(r[1]) if r[1] else None,
                    "dispo_vehicules": int(r[2]) if r[2] else None,
                    "dispo_pct":    round(float(r[3]), 1) if r[3] else None,
                    "sinistres":    int(r[4]) if r[4] else 0,
                    "sinistralite": round(float(r[5]), 2) if r[5] else None,
                    "conso_totale": round(float(r[6]), 0) if r[6] else None,
                    "conso_l100km": round(float(r[7]), 1) if r[7] else None,
                    "tco":          round(float(r[8]), 0) if r[8] else None,
                }
                for r in trends
            ],

            # Annotation pic sinistres
            "pic_sinistres": {
                "date": str(pic[0]), "valeur": int(pic[1])
            } if pic and pic[1] else None,

            # Section 3 — TCO points clés
            "tco_points_cles": tco_points,

            # Section 3 — Prédictions M+3
            "predictions_m3": fc_results,

            "rag_status": normalize_rag(
                "VERT" if (last[2] or 0) >= 90 else "AMBRE" if (last[2] or 0) >= 80 else "ROUGE"
            ) if last else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard parc auto: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard parc automobile")


# ---------------------------------------------------------------------------
# 8. MAINTENANCE
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/maintenance", tags=["dashboards"])
async def get_maintenance_dashboard(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: dict = Depends(check_page_access("maintenance"))
):
    """
    Page Maintenance (maquette imaginée selon logique métier)

    Section 1 KPIs (Silver — granularité mensuelle) :
      Total OT             ← SUM(Total_Ordres_Travail) — volume interventions
      OT Préventif         ← SUM(Interventions_Preventives)
      OT Correctif         ← SUM(Interventions_Correctives)
      Ratio Préventif      ← AVG(Ratio_Preventif_Pct) cible ≥ 70%
      Taux Réalisation     ← AVG(Taux_Realisation_Preventif_Pct) cible ≥ 85%
      Ruptures Stock       ← SUM(Total_Ruptures_Stock) [ROUGE si > 0]
      % Préventif Réalisé  ← AVG(Pct_Preventif_Realise)

    Section 2 Tendances 13 mois (Silver) :
      BarChart stacked OT Préventif vs Correctif
      LineChart ratio préventif (cible 70%)
      BarChart ruptures de stock par mois

    Section 3 Prédiction M+3 (Gold forecast_maintenance) :
      Volume OT M+3, Ratio Préventif M+3
    """
    try:
        engine = get_db_engine()
        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — KPIs agrégés
            kpi_q = text(f"""
                SELECT
                    SUM(Total_Ordres_Travail)           AS Total_OT,
                    SUM(Interventions_Preventives)      AS OT_Prev,
                    SUM(Interventions_Correctives)      AS OT_Corr,
                    AVG(Ratio_Preventif_Pct)            AS Ratio_Prev,
                    AVG(Taux_Realisation_Preventif_Pct) AS Taux_Real,
                    SUM(Total_Ruptures_Stock)           AS Ruptures,
                    AVG(Pct_Preventif_Realise)          AS Pct_Prev_Realise
                FROM Silver.silver_maintenance
                {silver_where}
            """)
            kpi = conn.execute(kpi_q, silver_params).fetchone()

            # Dernière valeur (pour le titre de section "situation actuelle")
            last_q = text("""
                SELECT TOP 1
                    Total_Ordres_Travail, Ratio_Preventif_Pct,
                    Taux_Realisation_Preventif_Pct, Total_Ruptures_Stock,
                    Pct_Preventif_Realise, DateKey
                FROM Silver.silver_maintenance
                ORDER BY DateKey DESC
            """)
            last = conn.execute(last_q).fetchone()

            # Delta ratio préventif vs mois précédent
            prev_ratio_q = text("""
                SELECT TOP 1 Ratio_Preventif_Pct
                FROM Silver.silver_maintenance
                WHERE DateKey < (SELECT MAX(DateKey) FROM Silver.silver_maintenance)
                ORDER BY DateKey DESC
            """)
            prev_ratio = conn.execute(prev_ratio_q).scalar()

            # Section 2 — Tendances 13 mois
            trend_q = text(f"""
                SELECT
                    DateKey,
                    Total_Ordres_Travail,
                    Interventions_Preventives,
                    Interventions_Correctives,
                    Ratio_Preventif_Pct,
                    Taux_Realisation_Preventif_Pct,
                    Total_Ruptures_Stock,
                    Pct_Preventif_Realise
                FROM Silver.silver_maintenance
                {silver_where}
                  AND DateKey >= DATEADD(month, -13, GETUTCDATE())
                ORDER BY DateKey ASC
            """)
            trends = conn.execute(trend_q, silver_params).fetchall()

            # Section 3 — Prédictions M+3
            fc_kpis = {
                "Total_Ordres_Travail":      "ot_m3",
                "Ratio_Preventif_Pct":       "ratio_prev_m3",
                "Total_Ruptures_Stock":      "ruptures_m3",
            }
            fc_results = {}
            for kpi_name, alias in fc_kpis.items():
                fc_q = text("""
                    SELECT TOP 3 DS, Yhat, Statut_RAG
                    FROM Gold.forecast_maintenance
                    WHERE KPI = :kpi AND Is_Forecast = 1 AND DS > GETUTCDATE()
                    ORDER BY DS ASC
                """)
                rows = conn.execute(fc_q, {"kpi": kpi_name}).fetchall()
                if rows:
                    fc_results[alias] = {
                        "yhat_m3":  round(float(rows[-1][1]), 1) if rows[-1][1] else None,
                        "rag":      normalize_rag(rows[-1][2]),
                        "date_m3":  str(rows[-1][0]),
                    }

            # Alertes maintenance actives
            alertes_q = text("""
                SELECT COUNT(*) FROM Gold.zscore_alerts
                WHERE Domaine = 'Maintenance'
                  AND Est_Active = 1
                  AND Statut_RAG IN ('ROUGE', 'RED')
            """)
            alertes_rouge = conn.execute(alertes_q).scalar() or 0

        ratio_delta = None
        if last and prev_ratio and last[1]:
            ratio_delta = round(float(last[1]) - float(prev_ratio), 1)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "Maintenance",
            "filters_applied": {"date_from": date_from, "date_to": date_to},

            # Section 1 — KPI Cards
            "kpis": {
                "total_ot":              int(kpi[0]) if kpi and kpi[0] else 0,
                "ot_preventif":          int(kpi[1]) if kpi and kpi[1] else 0,
                "ot_correctif":          int(kpi[2]) if kpi and kpi[2] else 0,
                "ratio_preventif_pct":   round(float(kpi[3]), 1) if kpi and kpi[3] else None,
                "ratio_cible":           70,
                "ratio_delta_vs_mois":   ratio_delta,
                "taux_realisation_pct":  round(float(kpi[4]), 1) if kpi and kpi[4] else None,
                "taux_cible":            85,
                "ruptures_stock":        int(kpi[5]) if kpi and kpi[5] else 0,
                "pct_preventif_realise": round(float(kpi[6]), 1) if kpi and kpi[6] else None,
                "alertes_rouge":         int(alertes_rouge),
                "derniere_date":         str(last[5]) if last else None,

                # Situation actuelle (dernière valeur)
                "ot_dernier_mois":       int(last[0]) if last and last[0] else None,
                "ratio_dernier_mois":    round(float(last[1]), 1) if last and last[1] else None,
                "taux_real_dernier_mois": round(float(last[2]), 1) if last and last[2] else None,
                "ruptures_dernier_mois": int(last[3]) if last and last[3] else 0,

                # RAG cards
                "rag_ratio":    normalize_rag("VERT" if (last[1] or 0) >= 70 else "AMBRE" if (last[1] or 0) >= 50 else "ROUGE"),
                "rag_taux":     normalize_rag("VERT" if (last[2] or 0) >= 85 else "AMBRE" if (last[2] or 0) >= 70 else "ROUGE"),
                "rag_ruptures": normalize_rag("VERT" if (last[3] or 1) == 0 else "ROUGE"),
            },

            # Section 2 — Tendances 13 mois
            "trends_13m": [
                {
                    "date":           str(r[0]),
                    "total_ot":       int(r[1]) if r[1] else 0,
                    "ot_preventif":   int(r[2]) if r[2] else 0,
                    "ot_correctif":   int(r[3]) if r[3] else 0,
                    "ratio_prev":     round(float(r[4]), 1) if r[4] else None,
                    "taux_real":      round(float(r[5]), 1) if r[5] else None,
                    "ruptures":       int(r[6]) if r[6] else 0,
                    "pct_realise":    round(float(r[7]), 1) if r[7] else None,
                }
                for r in trends
            ],

            # Section 3 — Prédictions M+3
            "predictions_m3": fc_results,

            "rag_status": normalize_rag(
                "VERT" if (last[1] or 0) >= 70 else "AMBRE" if (last[1] or 0) >= 50 else "ROUGE"
            ) if last else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard maintenance: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard maintenance")


# ---------------------------------------------------------------------------
# 9. FINANCE / GOUVERNANCE
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/finance", tags=["dashboards"])
async def get_finance_dashboard(
    segment: Optional[str] = Query(None, description="Filtre par Département"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    user: dict = Depends(check_page_access("finance"))
):
    """
    Page 2 — Gouvernance & Budget IT (screenshot de référence Power BI)

    Section 1 SANTÉ BUDGÉTAIRE (Silver) :
      Budget Alloué         ← SUM(Budget_Alloue_MAD) toutes directions
      Budget Consommé       ← SUM(Budget_Consomme_MAD)
      Écart Budgétaire      ← AVG(Ecart_Budget_Moyen_Pct) [VERT si négatif = économies]
      ROI Moyen IT          ← AVG(ROI_Moyen_Pct)
      CSAT Utilisateurs     ← AVG(CSAT_IT_Moyen) /5

    Section 2 ÉVOLUTION BUDGET VS CONSOMMATION 12 mois (Silver) :
      BarChart groupé Budget Alloué (bleu) vs Consommé (vert) par mois
      Panel droite : par direction (Département) avec barre % consommé + ROI + CSAT

    Section 3 ADOPTION DIGITALE & PROJETS (Silver) :
      Adoption Digitale Moy ← AVG(Adoption_Digital_Pct)
      Projets Livrés à Temps← AVG(Projets_A_Temps_Pct)
      Coût IT / Employé     ← AVG(Cout_IT_Par_Employe_MAD)

    Prédiction IA (Gold forecast_gouvernance) :
      Tendance coûts J+7
    """
    try:
        engine = get_db_engine()
        silver_where = "WHERE 1=1"
        silver_params: dict = {}
        if segment:
            silver_where += " AND Departement = :segment"
            silver_params["segment"] = segment
        silver_where += build_date_filter(date_from, date_to, silver_params)

        with engine.connect() as conn:

            # Section 1 — KPIs globaux (toutes directions ou filtrés)
            kpi_q = text(f"""
                SELECT
                    SUM(Budget_Alloue_MAD)          AS Budget_Alloue,
                    SUM(Budget_Consomme_MAD)        AS Budget_Consomme,
                    AVG(Ecart_Budget_Moyen_Pct)     AS Ecart_Pct,
                    AVG(ROI_Moyen_Pct)              AS ROI,
                    AVG(CSAT_IT_Moyen)              AS CSAT,
                    AVG(Adoption_Digital_Pct)       AS Adoption,
                    AVG(Projets_A_Temps_Pct)        AS Projets_A_Temps,
                    AVG(Cout_IT_Par_Employe_MAD)    AS Cout_Par_Employe
                FROM Silver.silver_gouvernance
                {silver_where}
            """)
            kpi = conn.execute(kpi_q, silver_params).fetchone()

            # Écart budget calculé (SUM consommé / SUM alloué - 1)
            ecart_reel = None
            if kpi and kpi[0] and kpi[1] and float(kpi[0]) > 0:
                ecart_reel = round(((float(kpi[1]) - float(kpi[0])) / float(kpi[0])) * 100, 1)

            # Section 2 — Évolution mensuelle 12 mois (BarChart groupé)
            budget_trend_q = text(f"""
                SELECT
                    DateKey,
                    SUM(Budget_Alloue_MAD)      AS Alloue,
                    SUM(Budget_Consomme_MAD)    AS Consomme,
                    AVG(Ecart_Budget_Moyen_Pct) AS Ecart,
                    AVG(ROI_Moyen_Pct)          AS ROI
                FROM Silver.silver_gouvernance
                {silver_where}
                  AND DateKey >= DATEADD(month, -12, GETUTCDATE())
                GROUP BY DateKey
                ORDER BY DateKey ASC
            """)
            budget_trends = conn.execute(budget_trend_q, silver_params).fetchall()

            # Section 2 — Par direction (dernière période disponible)
            latest_date_q = text("SELECT MAX(DateKey) FROM Silver.silver_gouvernance")
            latest_date = conn.execute(latest_date_q).scalar()

            by_dept_q = text("""
                SELECT
                    Departement,
                    SUM(Budget_Alloue_MAD)      AS Alloue,
                    SUM(Budget_Consomme_MAD)    AS Consomme,
                    AVG(Ecart_Budget_Moyen_Pct) AS Ecart,
                    AVG(ROI_Moyen_Pct)          AS ROI,
                    AVG(CSAT_IT_Moyen)          AS CSAT,
                    AVG(Projets_A_Temps_Pct)    AS Projets
                FROM Silver.silver_gouvernance
                WHERE DateKey = :latest_date
                GROUP BY Departement
                ORDER BY Departement
            """)
            by_dept = conn.execute(by_dept_q, {"latest_date": latest_date}).fetchall()

            # Liste des départements pour dropdown
            dept_list = [r[0] for r in conn.execute(text("""
                SELECT DISTINCT Departement FROM Silver.silver_gouvernance
                WHERE Departement IS NOT NULL ORDER BY Departement
            """)).fetchall()]

            # Prédiction tendance coûts J+7 (Gold)
            fc_q = text("""
                SELECT TOP 7 DS, Yhat, Statut_RAG
                FROM Gold.forecast_gouvernance
                WHERE KPI = 'Budget_Consomme_MAD' AND Is_Forecast = 1 AND DS > GETUTCDATE()
                ORDER BY DS ASC
            """)
            fc = conn.execute(fc_q).fetchall()

            # Tendance prédiction J+7 (delta %)
            fc_tendance = None
            if fc and len(fc) >= 2 and fc[0][1] and fc[-1][1]:
                fc_tendance = round(
                    ((float(fc[-1][1]) - float(fc[0][1])) / float(fc[0][1])) * 100, 1
                )

            # Risk score gouvernance
            risk_q = text("""
                SELECT TOP 1 Score_Gouvernance, Statut_RAG_Global
                FROM Gold.it_risk_score ORDER BY DateKey DESC
            """)
            risk = conn.execute(risk_q).fetchone()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "domain": "Finance",
            "filters_applied": {"segment": segment, "date_from": date_from, "date_to": date_to},

            # Section 1 — SANTÉ BUDGÉTAIRE
            "kpis": {
                "budget_alloue_mad":        round(float(kpi[0]), 0) if kpi and kpi[0] else None,
                "budget_consomme_mad":      round(float(kpi[1]), 0) if kpi and kpi[1] else None,
                "ecart_budget_pct":         ecart_reel,                      # calculé
                "ecart_budget_avg_pct":     round(float(kpi[2]), 1) if kpi and kpi[2] else None,
                "roi_moyen_pct":            round(float(kpi[3]), 1) if kpi and kpi[3] else None,
                "csat_it_moyen":            round(float(kpi[4]), 2) if kpi and kpi[4] else None,
                "adoption_digital_pct":     round(float(kpi[5]), 1) if kpi and kpi[5] else None,
                "projets_a_temps_pct":      round(float(kpi[6]), 1) if kpi and kpi[6] else None,
                "cout_it_par_employe_mad":  round(float(kpi[7]), 0) if kpi and kpi[7] else None,
                "derniere_date":            str(latest_date) if latest_date else None,

                # RAG
                "rag_ecart": normalize_rag(
                    "VERT" if (ecart_reel or 0) <= 0
                    else "AMBRE" if (ecart_reel or 0) <= 10
                    else "ROUGE"
                ),
                "rag_roi": normalize_rag(
                    "VERT" if (kpi[3] or 0) >= 15 else "AMBRE" if (kpi[3] or 0) >= 5 else "ROUGE"
                ),
            },

            # Section 2 — Évolution budget vs consommation 12 mois
            "budget_trends_12m": [
                {
                    "date":     str(r[0]),
                    "alloue":   round(float(r[1]), 0) if r[1] else None,
                    "consomme": round(float(r[2]), 0) if r[2] else None,
                    "ecart":    round(float(r[3]), 1) if r[3] else None,
                    "roi":      round(float(r[4]), 1) if r[4] else None,
                    "rag": normalize_rag(
                        "VERT" if (r[3] or 0) <= 0
                        else "AMBRE" if (r[3] or 0) <= 10
                        else "ROUGE"
                    ),
                }
                for r in budget_trends
            ],

            # Section 2 — Par direction (dernière période)
            "par_direction": [
                {
                    "departement":  str(r[0]),
                    "alloue":       round(float(r[1]), 0) if r[1] else None,
                    "consomme":     round(float(r[2]), 0) if r[2] else None,
                    "pct_consomme": round((float(r[2]) / float(r[1])) * 100, 1)
                                    if r[1] and r[2] and float(r[1]) > 0 else None,
                    "ecart":        round(float(r[3]), 1) if r[3] else None,
                    "roi":          round(float(r[4]), 1) if r[4] else None,
                    "csat":         round(float(r[5]), 2) if r[5] else None,
                    "projets_a_temps": round(float(r[6]), 1) if r[6] else None,
                    "rag": normalize_rag(
                        "VERT" if r[1] and r[2] and float(r[2]) <= float(r[1])
                        else "ROUGE"
                    ),
                }
                for r in by_dept
            ],

            # Section 3 — Adoption digitale & projets
            "adoption": {
                "adoption_digital_pct":    round(float(kpi[5]), 1) if kpi and kpi[5] else None,
                "projets_a_temps_pct":     round(float(kpi[6]), 1) if kpi and kpi[6] else None,
                "cout_it_par_employe_mad": round(float(kpi[7]), 0) if kpi and kpi[7] else None,
            },

            # Prédiction tendance coûts J+7
            "prediction_ia": {
                "tendance_pct": fc_tendance,
                "points": [
                    {"date": str(r[0]), "yhat": round(float(r[1]), 0) if r[1] else None, "rag": normalize_rag(r[2])}
                    for r in fc
                ],
            } if fc else None,

            "risk_score":       float(risk[0]) if risk and risk[0] else None,
            "rag_status":       normalize_rag(risk[1]) if risk else None,
            "available_depts":  dept_list,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard finance: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard finance")


# ---------------------------------------------------------------------------
# 10. ALERTES CENTRALISÉES
# ---------------------------------------------------------------------------

@router.get("/api/dashboard/alerts", tags=["dashboards"])
async def get_alerts_dashboard(
    domaine: Optional[str] = Query(None, description="Filtre par domaine"),
    priorite: Optional[str] = Query(None, description="Filtre priorité: ROUGE, AMBRE"),
    statut: Optional[str] = Query(None, description="active, acknowledged, resolved"),
    user: dict = Depends(get_current_user)
):
    """
    Page Alertes Centralisées — Gold uniquement

    Synthèse : compteurs par type et domaine
    Alertes Z-Score : anomalies statistiques en cours
    Alertes Prophet : KPIs en trajectoire ROUGE sur horizon futur
    Recommandations : actions ML en attente d'acquittement
    """
    try:
        engine = get_db_engine()

        # Filtres dynamiques
        zs_where = "WHERE Est_Active = 1"
        pa_where = "WHERE Est_Active = 1"
        rec_where = "WHERE 1=1"
        params: dict = {}

        if domaine:
            zs_where += " AND Domaine = :domaine"
            pa_where += " AND domain = :domaine"
            rec_where += " AND Domaine = :domaine"
            params["domaine"] = domaine
        if priorite:
            zs_where += " AND Statut_RAG = :priorite"
            pa_where += " AND rag_status = :priorite"
            params["priorite"] = priorite
        if statut:
            rec_where += " AND Statut = :statut"
            params["statut"] = statut

        with engine.connect() as conn:

            # Compteurs synthèse
            zs_count_q = text(f"""
                SELECT
                    COUNT(*)                                                AS Total,
                    SUM(CASE WHEN Statut_RAG IN ('ROUGE','RED') THEN 1 ELSE 0 END) AS Rouge,
                    SUM(CASE WHEN Statut_RAG IN ('AMBRE','AMBER') THEN 1 ELSE 0 END) AS Ambre
                FROM Gold.zscore_alerts {zs_where}
            """)
            zs_counts = conn.execute(zs_count_q, params).fetchone()

            pa_count_q = text(f"""
                SELECT COUNT(*) FROM Gold.prophet_alerts {pa_where}
            """)
            pa_count = conn.execute(pa_count_q, params).scalar() or 0

            # Alertes Z-Score détaillées
            zs_q = text(f"""
                SELECT TOP 50
                    Id, DateKey, Domaine, GroupKey, KPI,
                    Valeur_Observee, Valeur_Moyenne, Z_Score,
                    Statut_RAG, Direction_Alerte, Est_Active
                FROM Gold.zscore_alerts
                {zs_where}
                ORDER BY
                    CASE Statut_RAG WHEN 'ROUGE' THEN 1 WHEN 'RED' THEN 1
                                    WHEN 'AMBRE' THEN 2 ELSE 3 END,
                    DateKey DESC
            """)
            zs_rows = conn.execute(zs_q, params).fetchall()

            # Alertes Prophet détaillées
            pa_q = text(f"""
                SELECT TOP 20
                    domain, entity, kpi, first_alert_date,
                    rag_status, risk_score, yhat, yhat_lower, yhat_upper
                FROM Gold.prophet_alerts
                {pa_where}
                ORDER BY
                    CASE rag_status WHEN 'ROUGE' THEN 1 WHEN 'RED' THEN 1
                                    WHEN 'AMBRE' THEN 2 ELSE 3 END,
                    first_alert_date ASC
            """)
            pa_rows = conn.execute(pa_q, params).fetchall()

            # Recommandations actives
            rec_q = text(f"""
                SELECT TOP 20
                    Id, DateKey, Domaine, Entite, KPI_Declencheur,
                    Titre, Description, Action_Suggeree,
                    Priorite, Statut_RAG_Source, Statut, Destinataire_Role
                FROM Gold.recommendations
                {rec_where}
                  AND Statut NOT IN ('resolved', 'dismissed')
                ORDER BY
                    CASE Statut_RAG_Source WHEN 'ROUGE' THEN 1 WHEN 'RED' THEN 1
                                           WHEN 'AMBRE' THEN 2 ELSE 3 END,
                    DateKey DESC
            """)
            rec_rows = conn.execute(rec_q, params).fetchall()

            # Répartition par domaine
            repartition_q = text("""
                SELECT Domaine, COUNT(*) AS Nb,
                       SUM(CASE WHEN Statut_RAG IN ('ROUGE','RED') THEN 1 ELSE 0 END) AS Rouge
                FROM Gold.zscore_alerts
                WHERE Est_Active = 1
                GROUP BY Domaine
                ORDER BY Rouge DESC, Nb DESC
            """)
            repartition = conn.execute(repartition_q).fetchall()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filters_applied": {"domaine": domaine, "priorite": priorite, "statut": statut},

            # Compteurs synthèse
            "synthese": {
                "zscore_total":          int(zs_counts[0]) if zs_counts and zs_counts[0] else 0,
                "zscore_rouge":          int(zs_counts[1]) if zs_counts and zs_counts[1] else 0,
                "zscore_ambre":          int(zs_counts[2]) if zs_counts and zs_counts[2] else 0,
                "prophet_actives":       int(pa_count),
                "recommandations_actives": len(rec_rows),
            },

            # Répartition par domaine
            "repartition_par_domaine": [
                {"domaine": r[0], "total": int(r[1]), "rouge": int(r[2])}
                for r in repartition
            ],

            # Alertes Z-Score
            "alerts_zscore": [
                {
                    "id":             int(r[0]),
                    "date":           str(r[1]),
                    "domaine":        str(r[2]),
                    "entite":         str(r[3]) if r[3] else None,
                    "kpi":            str(r[4]),
                    "valeur":         round(float(r[5]), 2) if r[5] else None,
                    "moyenne":        round(float(r[6]), 2) if r[6] else None,
                    "z_score":        round(float(r[7]), 2) if r[7] else None,
                    "rag":            normalize_rag(r[8]),
                    "direction":      str(r[9]),
                }
                for r in zs_rows
            ],

            # Alertes Prophet
            "alerts_prophet": [
                {
                    "domaine":     str(r[0]),
                    "entite":      str(r[1]) if r[1] else None,
                    "kpi":         str(r[2]),
                    "date_alerte": str(r[3]) if r[3] else None,
                    "rag":         normalize_rag(r[4]),
                    "risk_score":  round(float(r[5]), 2) if r[5] else None,
                    "yhat":        round(float(r[6]), 2) if r[6] else None,
                    "yhat_lower":  round(float(r[7]), 2) if r[7] else None,
                    "yhat_upper":  round(float(r[8]), 2) if r[8] else None,
                }
                for r in pa_rows
            ],

            # Recommandations ML
            "recommandations": [
                {
                    "id":          int(r[0]),
                    "date":        str(r[1]),
                    "domaine":     str(r[2]),
                    "entite":      str(r[3]) if r[3] else None,
                    "kpi":         str(r[4]) if r[4] else None,
                    "titre":       str(r[5]),
                    "description": str(r[6]),
                    "action":      str(r[7]) if r[7] else None,
                    "priorite":    str(r[8]),
                    "rag":         normalize_rag(r[9]),
                    "statut":      str(r[10]),
                    "role":        str(r[11]),
                }
                for r in rec_rows
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Dashboard alertes: {e}")
        raise HTTPException(status_code=500, detail="Impossible de récupérer le dashboard alertes")