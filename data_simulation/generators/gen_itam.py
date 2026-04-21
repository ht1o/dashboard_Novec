import pandas as pd
import numpy as np

def generate_itam(daterange_months):
    """
    Génère les 5 KPIs ITAM / Gestion des Actifs IT.
    
    Patterns simulés :
    - Vétusté du parc influence la fiabilité Infrastructure (relation causale)
    - Conformité licences fluctue autour de 97% (audits périodiques)
    - Délai de mise à disposition dépend du stock de pièces
    - CMDB se dégrade lentement sans nettoyage
    """
    data = []
    for i, date in enumerate(daterange_months):
        # --- Total postes actifs ---
        total_assets = int(np.random.normal(2000, 15))
        
        # --- Taux de vétusté du parc (>4 ans) ---
        # Légère hausse naturelle si pas de renouvellement
        vetuste_rate = min(40.0, max(5.0, float(np.random.normal(20, 4) + (i * 0.3))))
        
        # --- TCO annuel par poste (MAD) ---
        # TCO augmente avec la vétusté (corrélation positive)
        tco_base = 5500 + (vetuste_rate * 120)  # Plus c'est vieux, plus ça coûte
        tco_poste = max(3000.0, float(np.random.normal(tco_base, 300)))
        
        # --- Taux conformité licences logicielles ---
        conformite_licences = min(100.0, max(85.0, float(np.random.normal(97, 2))))
        
        # --- Délai moyen mise à disposition (jours) ---
        delai_dispo = max(1.0, float(np.random.normal(4, 1.5)))
        
        # --- Taux inventaire à jour (CMDB) ---
        # Se dégrade lentement sans effort de mise à jour
        cmdb_rate = min(100.0, max(75.0, float(np.random.normal(92, 3) - (i * 0.2))))
        
        # --- Licences inutilisées (pour optimisation coûts) ---
        licences_inutilisees = max(0, int(np.random.normal(110, 20)))
        
        data.append({
            'Mois': date.strftime('%Y-%m-%d'),
            'Total_Postes_Actifs': total_assets,
            'Vetuste_Plus_4ans_Pct': round(vetuste_rate, 2),
            'TCO_Annuel_Par_Poste_MAD': round(tco_poste, 2),
            'Conformite_Licences_Pct': round(conformite_licences, 2),
            'Delai_Mise_Dispo_Jours': round(delai_dispo, 2),
            'Taux_Inventaire_CMDB_Pct': round(cmdb_rate, 2),
            'Licences_Inutilisees': licences_inutilisees
        })
    return pd.DataFrame(data)
