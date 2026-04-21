import pandas as pd
import numpy as np

def generate_maintenance(daterange_months):
    """
    Génère les KPIs Maintenance.
    
    Relation inter-domaine :
    - Le ratio préventif/correctif impacte la disponibilité du parc auto
    - Un taux de réalisation préventif bas = plus de correctif le mois suivant
    """
    data = []
    for i, date in enumerate(daterange_months):
        # --- Total ordres de travail ---
        interventions = max(30, int(np.random.normal(120, 15)))
        
        # --- Interventions préventives et correctives ---
        ratio_preventif = np.random.uniform(0.60, 0.85)
        prev = max(0, int(interventions * ratio_preventif))
        corr = interventions - prev
        
        # --- Ratio préventif/correctif en % ---
        ratio_pct = round(float((prev / interventions) * 100), 2) if interventions > 0 else 0.0
        
        # --- Taux de réalisation maintenances préventives ---
        # Représente le % des maintenances prévues effectivement réalisées
        planned_preventive = int(prev * np.random.uniform(1.05, 1.25))  # On planifie toujours plus
        taux_realisation = min(100.0, max(50.0, float((prev / max(1, planned_preventive)) * 100)))
        
        # --- Ruptures de stock pièces détachées ---
        ruptures = max(0, int(np.random.poisson(1.5)))
        
        # Si ruptures élevées, le taux de réalisation baisse
        if ruptures >= 3:
            taux_realisation *= 0.85
        
        data.append({
            'Mois': date.strftime('%Y-%m-%d'),
            'Total_Ordres_Travail': interventions,
            'Interventions_Preventives': prev,
            'Interventions_Correctives': corr,
            'Ratio_Preventif_Pct': ratio_pct,
            'Taux_Realisation_Preventif_Pct': round(taux_realisation, 2),
            'Ruptures_Stock_Pieces': ruptures
        })
    return pd.DataFrame(data)
