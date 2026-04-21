import pandas as pd
import numpy as np

def generate_fleet(daterange_days):
    """
    Génère les 4 KPIs Parc Automobile.
    
    Patterns simulés :
    - Disponibilité influencée par la sinistralité
    - TCO par véhicule corrélé à la consommation carburant
    - Taux sinistralité = Sinistres cumulés / Flotte totale
    - Consommation en L/100km (plus réaliste que total litres)
    """
    data = []
    flotte_totale = 150
    km_journaliers_flotte = 12000  # km parcourus par jour par toute la flotte
    
    for date in daterange_days:
        is_weekend = date.weekday() >= 5
        
        # --- Véhicules disponibles ---
        if is_weekend:
            vehicules_dispo = int(flotte_totale * np.random.uniform(0.92, 0.98))
        else:
            vehicules_dispo = int(flotte_totale * np.random.uniform(0.82, 0.95))
        
        disponibilite_pct = round(float((vehicules_dispo / flotte_totale) * 100), 2)
        
        # --- Sinistres du jour (Poisson) ---
        sinistres = int(np.random.poisson(0.15))
        
        # --- Taux sinistralité (cumulable, mais on le calcule par jour) ---
        taux_sinistralite = round(float((sinistres / flotte_totale) * 100), 4)
        
        # --- Consommation carburant ---
        conso_totale_l = max(0, float(np.random.normal(4200, 350)))
        # L/100km = (Total litres / Total km) * 100
        conso_l_100km = round(float((conso_totale_l / km_journaliers_flotte) * 100), 2)
        
        # --- TCO par véhicule (MAD/an estimé, proratisé au jour) ---
        # TCO influencé par la consommation et la sinistralité
        tco_base_annuel = 28000 + (conso_l_100km * 500) + (sinistres * 5000)
        tco_par_vehicule = round(float(np.random.normal(tco_base_annuel, 2000)), 2)
        
        data.append({
            'Date': date.strftime('%Y-%m-%d'),
            'Flotte_Totale': flotte_totale,
            'Vehicules_Disponibles': vehicules_dispo,
            'Disponibilite_Vehicules_Pct': disponibilite_pct,
            'Nbre_Sinistres_Jour': sinistres,
            'Taux_Sinistralite_Pct': taux_sinistralite,
            'Consommation_Carburant_Total_L': round(conso_totale_l, 2),
            'Conso_L_100km': conso_l_100km,
            'TCO_Par_Vehicule_MAD': tco_par_vehicule
        })
    return pd.DataFrame(data)
