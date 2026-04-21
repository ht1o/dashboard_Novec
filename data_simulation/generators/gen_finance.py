import pandas as pd
import numpy as np
import random

def generate_gouvernance(daterange_months, itsm_monthly_csat=None):
    """
    Génère les 6 KPIs Gouvernance & Stratégie IT.
    
    Relation inter-domaine :
    - Satisfaction_Globale_IT est influencée par le CSAT ITSM (si disponible)
    - Budget sweep en Q4 (mois >= 10)
    
    Args:
        daterange_months: DateRange mensuel
        itsm_monthly_csat: dict optionnel {mois_str: csat_moyen} pour corrélation
    """
    data = []
    departments = ['IT-Operations', 'Cybersecurité', 'Data', 'Projets']
    total_employes = 850  # Effectif Novec IT estimé
    
    for date in daterange_months:
        for dept in departments:
            month = date.month
            mois_str = date.strftime('%Y-%m-%d')
            
            # --- Budget consommé vs alloué (Saisonnalité Q4) ---
            base_budget = np.random.uniform(100000, 300000)
            if month >= 10:
                conso_ratio = np.random.normal(1.05, 0.08)  # Budget sweep fin d'année
            else:
                conso_ratio = np.random.normal(0.85, 0.05)
            
            budget_consomme = base_budget * conso_ratio
            ecart_budget_pct = round(float(((budget_consomme - base_budget) / base_budget) * 100), 2)
            
            # --- ROI des projets IT ---
            roi = np.random.normal(15, 8)  # Moyenne 15%, écart-type 8%
            
            # --- % projets livrés à temps ---
            projets_a_temps = min(100.0, max(0.0, np.random.normal(75, 10)))
            
            # --- Taux adoption outils digitaux ---
            day_index = (date - daterange_months[0]).days
            adoption_digital = min(100.0, max(0.0, 65.0 + (day_index * 0.02) + np.random.normal(0, 3)))
            
            # --- Satisfaction globale IT (corrélée au CSAT ITSM) ---
            if itsm_monthly_csat and mois_str in itsm_monthly_csat:
                base_satisfaction = itsm_monthly_csat[mois_str] * 0.7 + np.random.normal(0.3, 0.15)
            else:
                base_satisfaction = np.random.normal(3.8, 0.4)
            satisfaction_it = max(1.0, min(5.0, float(base_satisfaction)))
            
            # --- Coût IT par employé (MAD/an) ---
            cout_it = round(float(np.random.normal(9500, 1500)), 2)
            
            data.append({
                'Mois': mois_str,
                'Departement': dept,
                'Budget_Alloue_MAD': round(float(base_budget), 2),
                'Budget_Consomme_MAD': round(float(budget_consomme), 2),
                'Ecart_Budget_Pct': ecart_budget_pct,
                'ROI_Projets_Pct': round(float(roi), 2),
                'Projets_Livres_A_Temps_Pct': round(float(projets_a_temps), 2),
                'Taux_Adoption_Digital_Pct': round(float(adoption_digital), 2),
                'Satisfaction_Globale_IT': round(float(satisfaction_it), 2),
                'Cout_IT_Par_Employe_MAD': cout_it
            })
    return pd.DataFrame(data)
