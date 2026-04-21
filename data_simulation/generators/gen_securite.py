import pandas as pd
import numpy as np

def generate_cyber(daterange_days, start_date):
    """
    Génère les 6 KPIs Cybersécurité & Conformité.
    
    Patterns simulés :
    - Tendance progressive : MFA monte, Phishing baisse (sensibilisation)
    - MTTD corrélé au nombre d'incidents (plus d'incidents = détection plus lente)
    - % patchés suit un cycle de patch Tuesday (pic mensuel)
    - RGPD augmente progressivement (mise en conformité)
    """
    data = []
    for date in daterange_days:
        day_index = (date - start_date).days
        month = date.month
        
        # --- Incidents sécurité (Poisson, événements rares) ---
        incidents = int(np.random.poisson(lam=0.15))
        
        # --- MTTD : Temps moyen de détection ---
        # Si incident, le temps de détection augmente
        if incidents > 0:
            mttd = max(0.1, float(np.random.normal(2.5, 1.0)))
        else:
            mttd = max(0.1, float(np.random.normal(0.5, 0.2)))
        
        # --- Vulnérabilités critiques non corrigées ---
        vuln = int(np.random.poisson(lam=1.5))
        
        # --- % Systèmes patchés (cycle Patch Tuesday) ---
        # Juste après le patch Tuesday (2e mardi du mois), le taux monte
        day_of_month = date.day
        if 14 <= day_of_month <= 20:
            patch_rate = min(100.0, np.random.normal(96, 2))
        else:
            patch_rate = min(100.0, np.random.normal(90, 3))
        patch_rate = max(70.0, float(patch_rate))
        
        # --- Taux MFA (trend haussier progressif) ---
        mfa_rate = min(100.0, 78.0 + (day_index * 0.04) + np.random.normal(0, 1))
        mfa_rate = max(50.0, float(mfa_rate))
        
        # --- Taux clic Phishing (trend baissier - sensibilisation) ---
        phishing_click_rate = max(0.5, 16.0 - (day_index * 0.025) + np.random.normal(0, 0.8))
        
        # --- Conformité RGPD (progression lente) ---
        rgpd = min(100.0, 80.0 + (day_index * 0.03) + np.random.normal(0, 1.5))
        rgpd = max(60.0, float(rgpd))
        
        data.append({
            'Date': date.strftime('%Y-%m-%d'),
            'Incidents_Critiques': incidents,
            'MTTD_Hours': round(mttd, 2),
            'Vulnerabilites_Non_Patchees': vuln,
            'Systemes_Patches_Pct': round(patch_rate, 2),
            'Taux_Adoption_MFA_Pct': round(mfa_rate, 2),
            'Taux_Clic_Phishing_Pct': round(float(phishing_click_rate), 2),
            'Conformite_RGPD_Pct': round(rgpd, 2)
        })
    return pd.DataFrame(data)
