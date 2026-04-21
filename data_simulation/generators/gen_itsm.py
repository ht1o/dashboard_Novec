import pandas as pd
import numpy as np
import random

def generate_itsm(daterange_days, infra_daily_anomalies=None):
    """
    Génère les 5 KPIs ITSM / Service Desk.
    
    Relation inter-domaine :
    - Quand l'infra a des anomalies un jour donné, les tickets P1 explosent
    - Le pic du lundi est conservé (saisonnalité hebdomadaire)
    
    Args:
        daterange_days: DateRange journalier
        infra_daily_anomalies: dict optionnel {date_str: nb_anomalies} issu de gen_infra
    """
    data = []
    cumul_backlog = 0  # Le backlog est un stock cumulatif
    
    for date in daterange_days:
        date_str = date.strftime('%Y-%m-%d')
        is_monday = date.weekday() == 0
        
        # --- Volume de base avec saisonnalité lundi ---
        base_tickets = int(np.random.normal(85, 10)) if is_monday else int(np.random.normal(45, 8))
        
        # --- Corrélation Infra → ITSM : les anomalies infra génèrent des tickets P1 ---
        infra_boost = 0
        if infra_daily_anomalies and date_str in infra_daily_anomalies:
            nb_anomalies = infra_daily_anomalies[date_str]
            if nb_anomalies > 0:
                infra_boost = int(nb_anomalies * np.random.uniform(3, 8))
                base_tickets += infra_boost
        
        # Explosion aléatoire du backlog (événement rare)
        if random.random() < 0.03:
            base_tickets = int(base_tickets * 2.5)
        
        base_tickets = max(5, base_tickets)
        
        # --- Répartition P1/P2/P3 ---
        p1_ratio = 0.08 if infra_boost > 0 else 0.05  # Plus de P1 si panne infra
        p1 = max(0, int(base_tickets * p1_ratio))
        p2 = max(0, int(base_tickets * 0.25))
        p3 = max(0, base_tickets - p1 - p2)
        
        # --- SLA respecté (inversement proportionnel au volume) ---
        sla_respect_pct = 99.0 - (base_tickets / 15.0) + np.random.normal(0, 1)
        sla_respect_pct = min(100.0, max(50.0, float(sla_respect_pct)))
        
        # --- MTTR Tickets (corrélé au volume) ---
        mttr_hours = np.random.normal(6, 2) + (base_tickets / 40.0)
        mttr_hours = max(0.5, float(mttr_hours))
        
        # --- FCR (First Call Resolution) ---
        fcr = np.random.normal(65, 8) - (p1 * 2)  # Plus de P1 = FCR plus bas
        fcr = min(100.0, max(20.0, float(fcr)))
        
        # --- Backlog non résolus (stock cumulatif) ---
        nouveaux_non_resolus = max(0, int(base_tickets * np.random.uniform(0.02, 0.08)))
        resolus_du_jour = max(0, int(np.random.normal(nouveaux_non_resolus * 0.85, 2)))
        cumul_backlog = max(0, cumul_backlog + nouveaux_non_resolus - resolus_du_jour)
        
        # --- CSAT Score (corrélé négativement au MTTR) ---
        csat = 5.0 - (mttr_hours / 12.0) + np.random.normal(0, 0.15)
        csat = max(1.0, min(5.0, float(csat)))
        
        data.append({
            'Date': date_str,
            'Tickets_P1_Critique': p1,
            'Tickets_P2_Majeur': p2,
            'Tickets_P3_Mineur': p3,
            'Volume_Total': base_tickets,
            'SLA_Respect_Pct': round(sla_respect_pct, 2),
            'MTTR_Hours': round(mttr_hours, 2),
            'FCR_Pct': round(fcr, 2),
            'Backlog_Non_Resolus': cumul_backlog,
            'CSAT_Score': round(csat, 2)
        })
    return pd.DataFrame(data)
