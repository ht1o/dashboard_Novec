// ─── Auth ────────────────────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
  role: string
  username: string
}

export interface MeResponse {
  username: string
  role: string
  timestamp: string
}

// ─── RAG ─────────────────────────────────────────────────────────────────────
export type RAGStatus = 'ROUGE' | 'AMBRE' | 'VERT'

// ─── Executive ───────────────────────────────────────────────────────────────
export interface ExecutiveResponse {
  timestamp: string
  scorecard: Record<string, {
    rag: RAGStatus
    kpi_label: string
    kpi_value: number | null
    kpi_unit: string
    action: { titre: string; action: string; rag: RAGStatus } | null
    risk_score: number | null
  }>
  kpis_transversaux: {
    it_risk_score: number | null
    rag_global: RAGStatus | null
    digital_adoption_pct: number | null
    nb_anomalies_if: number
    nb_alertes_rouge: number
    nb_alertes_ambre: number
    top_contributeurs: string | null
    last_update: string | null
  }
  point_attention: {
    titre: string; description: string; action: string
    domaine: string; rag: RAGStatus; priorite: string
  } | null
  predictions_j7: Array<{
    domaine: string; entite: string; kpi: string
    valeur: number | null; rag: RAGStatus; date_alerte: string | null
  }>
}

// ─── Infrastructure ──────────────────────────────────────────────────────────
export interface InfraResponse {
  timestamp: string
  domain: string
  filters_applied: { server: string | null; date_from: string | null; date_to: string | null }
  kpis: {
    uptime_moyen_pct: number | null; cpu_moyen_pct: number | null
    ram_moyen_pct: number | null; disk_moyen_pct: number | null
    latence_moy_ms: number | null; backup_coverage_pct: number | null
    mtbf_moyen_hours: number | null; mttr_moyen_hours: number | null
    total_anomalies: number; nb_serveurs: number; alertes_rouge: number
  }
  resources_avg: { cpu: number | null; ram: number | null; disk: number | null; seuil_critique: 90 }
  trends_30j: Array<{ date: string; uptime: number | null; cpu: number | null; ram: number | null; disk: number | null; anomalies: number }>
  anomalies_weekly: Array<{ semaine: number; debut_semaine: string; nb_anomalies: number }>
  cloud: { instances_actives: number; backup_coverage_pct: number | null; latence_avg_ms: number | null; disponibilite_pct: number | null }
  prediction_ia: { server: string | null; kpi: string | null; date_alerte: string | null; yhat: number | null; rag: RAGStatus | null; risk_score: number | null } | null
  risk_score: number | null
  rag_status: RAGStatus | null
  available_servers: string[]
}

// ─── Finance / Gouvernance ───────────────────────────────────────────────────
export interface FinanceResponse {
  timestamp: string
  domain: string
  filters_applied: { segment: string | null; date_from: string | null; date_to: string | null }
  kpis: {
    budget_alloue_mad: number | null; budget_consomme_mad: number | null
    ecart_budget_pct: number | null; ecart_budget_avg_pct: number | null
    roi_moyen_pct: number | null; csat_it_moyen: number | null
    adoption_digital_pct: number | null; projets_a_temps_pct: number | null
    cout_it_par_employe_mad: number | null; derniere_date: string | null
    rag_ecart: RAGStatus; rag_roi: RAGStatus
  }
  budget_trends_12m: Array<{ date: string; alloue: number | null; consomme: number | null; ecart: number | null; roi: number | null; rag: RAGStatus }>
  par_direction: Array<{ departement: string; alloue: number | null; consomme: number | null; pct_consomme: number | null; ecart: number | null; roi: number | null; csat: number | null; projets_a_temps: number | null; rag: RAGStatus }>
  adoption: { adoption_digital_pct: number | null; projets_a_temps_pct: number | null; cout_it_par_employe_mad: number | null }
  prediction_ia: { tendance_pct: number | null; points: Array<{ date: string; yhat: number | null; rag: string }> } | null
  risk_score: number | null
  rag_status: RAGStatus | null
  available_depts: string[]
}

// ─── Cybersécurité ───────────────────────────────────────────────────────────
export interface CybersecResponse {
  timestamp: string
  domain: string
  filters_applied: { date_from: string | null; date_to: string | null }
  kpis: {
    incidents_critiques: number; incidents_total_periode: number
    mttd_moyen_hours: number | null; vuln_non_patchees: number
    systemes_patches_pct: number | null; mfa_adoption_pct: number | null
    mfa_delta_vs_an_precedent: number | null; taux_phishing_pct: number | null
    rgpd_conformite_pct: number | null; rgpd_cible: 95; alertes_rouge: number
    derniere_date: string | null
    rag_incidents: string; rag_mttd: string; rag_vuln: string
    rag_patch: string; rag_mfa: string; rag_rgpd: string
  }
  trends_13m: Array<{ date: string; incidents: number; vuln: number; patch_pct: number | null; mfa_pct: number | null; phishing_pct: number | null; rgpd_pct: number | null }>
  predictions_m3: {
    mfa_m3: { yhat_m3: number; rag: string; date_m3: string } | null
    rgpd_m3: { yhat_m3: number; rag: string; date_m3: string } | null
    incidents_m3: { yhat_m3: number; rag: string; date_m3: string } | null
    vuln_m3: { yhat_m3: number; rag: string; date_m3: string } | null
  }
  risk_score: number | null
  rag_status: RAGStatus | null
}

// ─── ITSM ─────────────────────────────────────────────────────────────────────
export interface ITSMResponse {
  timestamp: string
  domain: string
  filters_applied: { date_from: string | null; date_to: string | null; priority: string | null }
  kpis: {
    volume_tickets_jour: number | null; total_p1: number; total_p2: number; total_p3: number
    backlog_total: number; backlog_delta_13m: number | null
    sla_moyen_pct: number | null; sla_cible: 95
    fcr_moyen_pct: number | null; fcr_cible: 70
    mttr_moyen_hours: number | null; mttr_p1_cible: 4
    csat_moyen: number | null; pct_tickets_p1: number | null
    derniere_date: string | null
    periode_volume_total: number | null; periode_sla_moy: number | null
    periode_fcr_moy: number | null; periode_mttr_moy: number | null
    periode_csat_moy: number | null; periode_backlog: number
    periode_p1_total: number; periode_p2_total: number; periode_p3_total: number
  }
  trends_13m: Array<{ date: string; p1: number; p2: number; p3: number; volume_total: number; backlog: number; sla_pct: number | null; mttr: number | null }>
  sla_weekly: Array<{ semaine: number; debut: string; sla_reel: number | null }>
  sla_prediction_j7: Array<{ date: string; yhat: number | null; rag: string }>
  prediction_volume_j7: { points: Array<{ date: string; yhat: number | null; lower: number | null; upper: number | null }>; tendance_pct: number | null } | null
  prediction_ia: { kpi: string | null; date_alerte: string | null; yhat: number | null; rag: string | null } | null
  risk_score: number | null
  rag_status: RAGStatus | null
}

// ─── Applications ─────────────────────────────────────────────────────────────
export interface AppsResponse {
  timestamp: string
  domain: string
  filters_applied: { app: string | null; date_from: string | null; date_to: string | null }
  kpis: {
    disponibilite_moy_pct: number | null; disponibilite_cible: 99
    temps_reponse_moy_ms: number | null; temps_reponse_max_ms: number | null
    bugs_critiques: number; qualite_donnees_pct: number | null
    adoption_powerbi_pct: number | null; nb_applications: number; alertes_rouge: number
  }
  trends_13m: Array<{ date: string; app: string; dispo: number | null; tr_ms: number | null; bugs: number; qualite: number | null }>
  dispo_by_app: Array<{ app: string; dispo: number | null; tr_ms: number | null; bugs: number; rag: RAGStatus }>
  prediction_ia: { app: string | null; kpi: string | null; date_alerte: string | null; yhat: number | null; rag: string | null; risk_score: number | null } | null
  risk_score: number | null
  rag_status: RAGStatus | null
  available_apps: string[]
}

// ─── ITAM ─────────────────────────────────────────────────────────────────────
export interface ITAMResponse {
  timestamp: string
  domain: string
  filters_applied: { date_from: string | null; date_to: string | null }
  kpis: {
    total_postes: number | null; vetuste_pct: number | null; vetuste_seuil_alerte: 30
    tco_moyen_par_poste_mad: number | null; tco_delta_vs_mois_prec: number | null; tco_total_mad: number | null
    conformite_licences_pct: number | null; conformite_cible: 95
    licences_inutilisees: number; delai_mise_dispo_jours: number | null; delai_cible: 3
    cmdb_couverture_pct: number | null; cmdb_cible: 95; alertes_rouge: number; derniere_date: string | null
    rag_vetuste: string; rag_licences: string; rag_delai: string; rag_cmdb: string
  }
  trends_13m: Array<{ date: string; total_postes: number | null; vetuste_pct: number | null; tco_par_poste: number | null; tco_total: number | null; conformite_licences: number | null; licences_inutilisees: number; delai_mise_dispo: number | null; cmdb_couverture: number | null }>
  predictions_m6: {
    vetuste_m6: { yhat_m6: number | null; rag: string; date_m6: string; points: Array<{date: string; yhat: number | null}> } | null
    tco_m6: { yhat_m6: number | null; rag: string; date_m6: string; points: Array<{date: string; yhat: number | null}> } | null
    licences_m6: { yhat_m6: number | null; rag: string; date_m6: string; points: Array<{date: string; yhat: number | null}> } | null
  }
  risk_score: number | null
  rag_status: RAGStatus | null
}

// ─── Parc Auto ───────────────────────────────────────────────────────────────
export interface ParcAutoResponse {
  timestamp: string
  domain: string
  filters_applied: { date_from: string | null; date_to: string | null; vehicule_dept: string | null }
  kpis: {
    flotte_totale: number | null; vehicules_disponibles: number | null
    disponibilite_pct: number | null; disponibilite_moy_periode: number | null
    sinistres_mois_courant: number; taux_sinistralite_pct: number | null
    conso_totale_l: number | null; conso_moy_l100km: number | null
    tco_moy_par_vehicule_mad: number | null; tco_delta_vs_an_prec: number | null
    derniere_date: string | null
    rag_disponibilite: string; rag_sinistralite: string; rag_tco: string
  }
  trends_13m: Array<{ date: string; flotte: number | null; dispo_vehicules: number | null; dispo_pct: number | null; sinistres: number; sinistralite: number | null; conso_totale: number | null; conso_l100km: number | null; tco: number | null }>
  pic_sinistres: { date: string; valeur: number } | null
  tco_points_cles: Array<{ date: string; tco: number | null; rag: RAGStatus }>
  predictions_m3: {
    conso_m3?: { yhat_m3: number | null; rag: string; date_m3: string }
    sinistres_m3?: { yhat_m3: number | null; rag: string; date_m3: string }
    tco_m3?: { yhat_m3: number | null; rag: string; date_m3: string }
  }
  rag_status: RAGStatus | null
}

// ─── Maintenance ─────────────────────────────────────────────────────────────
export interface MaintenanceResponse {
  timestamp: string
  domain: string
  filters_applied: { date_from: string | null; date_to: string | null }
  kpis: {
    total_ot: number; ot_preventif: number; ot_correctif: number
    ratio_preventif_pct: number | null; ratio_cible: 70; ratio_delta_vs_mois: number | null
    taux_realisation_pct: number | null; taux_cible: 85; ruptures_stock: number
    pct_preventif_realise: number | null; alertes_rouge: number; derniere_date: string | null
    ot_dernier_mois: number | null; ratio_dernier_mois: number | null
    taux_real_dernier_mois: number | null; ruptures_dernier_mois: number
    rag_ratio: string; rag_taux: string; rag_ruptures: string
  }
  trends_13m: Array<{ date: string; total_ot: number; ot_preventif: number; ot_correctif: number; ratio_prev: number | null; taux_real: number | null; ruptures: number; pct_realise: number | null }>
  predictions_m3: {
    ot_m3?: { yhat_m3: number | null; rag: string; date_m3: string }
    ratio_prev_m3?: { yhat_m3: number | null; rag: string; date_m3: string }
    ruptures_m3?: { yhat_m3: number | null; rag: string; date_m3: string }
  }
  rag_status: RAGStatus | null
}

// ─── Alerts Dashboard ────────────────────────────────────────────────────────
export interface AlertsDashboardResponse {
  timestamp: string
  filters_applied: { domaine: string | null; priorite: string | null; statut: string | null }
  synthese: {
    zscore_total: number; zscore_rouge: number; zscore_ambre: number
    prophet_actives: number; recommandations_actives: number
  }
  repartition_par_domaine: Array<{ domaine: string; total: number; rouge: number }>
  alerts_zscore: Array<{ id: number; date: string; domaine: string; entite: string | null; kpi: string; valeur: number | null; moyenne: number | null; z_score: number | null; rag: string; direction: string }>
  alerts_prophet: Array<{ domaine: string; entite: string | null; kpi: string; date_alerte: string | null; rag: string; risk_score: number | null; yhat: number | null; yhat_lower: number | null; yhat_upper: number | null }>
  recommandations: Array<{ id: number; date: string; domaine: string; entite: string | null; kpi: string | null; titre: string; description: string; action: string | null; priorite: string; rag: string; statut: string; role: string }>
}

// ─── Risk Score ───────────────────────────────────────────────────────────────
export interface RiskScoreLatest {
  global_score: number | null
  rag_global: RAGStatus | null
  scores_par_domaine: Record<string, number | null>
  timestamp: string
}