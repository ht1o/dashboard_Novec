import pandas as pd
import numpy as np

def generate_applications(daterange_days, start_date, infra_daily_anomalies=None):
    """
    Génère les 4 KPIs Applications & BI/Data.
    
    Relation inter-domaine :
    - Quand l'infra a une anomalie, la disponibilité de l'app baisse
    - Le temps de réponse augmente si le serveur est surchargé
    
    Args:
        daterange_days: DateRange journalier
        start_date: date de début pour calculer les trends
        infra_daily_anomalies: dict optionnel {date_str: nb_anomalies} issu de gen_infra
    """
    data = []
    apps = ['App_SIRH', 'App_Compta', 'App_Core_Metier']
    
    for date in daterange_days:
        date_str = date.strftime('%Y-%m-%d')
        day_index = (date - start_date).days
        
        # Nombre d'anomalies infra ce jour-là
        nb_anomalies = 0
        if infra_daily_anomalies and date_str in infra_daily_anomalies:
            nb_anomalies = infra_daily_anomalies[date_str]
        
        for app in apps:
            # --- Temps de réponse moyen (ms) ---
            if app == 'App_Core_Metier':
                base_rt = np.random.normal(180, 40)
            else:
                base_rt = np.random.normal(85, 15)
            
            # Corrélation Infra → App : anomalie = temps de réponse explose
            if nb_anomalies > 0 and app == 'App_Core_Metier':
                base_rt += nb_anomalies * np.random.uniform(50, 150)
            
            base_rt = max(10.0, float(base_rt))
            
            # --- Disponibilité application critique (%) ---
            base_dispo = np.random.normal(99.7, 0.2)
            # Corrélation Infra → App : anomalie = disponibilité baisse
            if nb_anomalies > 0:
                base_dispo -= nb_anomalies * np.random.uniform(0.3, 1.5)
            dispo = min(100.0, max(90.0, float(base_dispo)))
            
            # --- Bugs critiques en production ---
            bugs = max(0, int(np.random.poisson(0.3)))
            # Plus de bugs si l'app est stressée
            if base_rt > 300:
                bugs += int(np.random.poisson(1.0))
            
            # --- Qualité données (complétude) ---
            data_qual = min(100.0, max(80.0, float(np.random.normal(96, 2))))
            
            # --- Adoption dashboard Power BI (trend haussier) ---
            adoption_bi = min(100.0, max(30.0, float(65.0 + (day_index * 0.03) + np.random.normal(0, 3))))
            
            data.append({
                'Date': date_str,
                'Application_Name': app,
                'Temps_Reponse_Moyen_ms': round(base_rt, 2),
                'Disponibilite_App_Pct': round(dispo, 2),
                'Bugs_Critiques_Prod': bugs,
                'Qualite_Donnees_Score_Pct': round(data_qual, 2),
                'Adoption_PowerBI_Pct': round(adoption_bi, 2)
            })
    return pd.DataFrame(data)
