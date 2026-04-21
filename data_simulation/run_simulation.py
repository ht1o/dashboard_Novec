import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# Import de la configuration
from config import get_db_engine, OUTPUT_DIR

# Import des générateurs spécifiques au domaine
from generators.gen_finance import generate_gouvernance
from generators.gen_infra import generate_infrastructure
from generators.gen_itsm import generate_itsm
from generators.gen_securite import generate_cyber
from generators.gen_itam import generate_itam
from generators.gen_facility import generate_fleet
from generators.gen_maintenance import generate_maintenance
from generators.gen_applications import generate_applications

class OrchestratorSimulator:
    """
    Orchestrateur V2 : Gère l'ordre d'exécution des générateurs
    pour garantir les corrélations inter-domaines.
    
    Ordre d'exécution imposé par les dépendances causales :
    1. Infrastructure (source des anomalies)
    2. ITSM (consomme les anomalies infra)
    3. Cybersécurité (indépendant)
    4. Applications (consomme les anomalies infra)
    5. ITAM (indépendant)
    6. Parc Auto (indépendant)
    7. Maintenance (indépendant)
    8. Gouvernance (consomme le CSAT ITSM)
    """
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        
        # Résolutions temporelles
        self.daterange_hours = pd.date_range(start=start_date, end=end_date, freq='h')
        self.daterange_days = pd.date_range(start=start_date, end=end_date, freq='D')
        self.daterange_months = pd.date_range(start=start_date, end=end_date, freq='MS')
        
        # Configuration SQL (si disponible)
        self.engine = get_db_engine()
        
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

    def save_data(self, df, table_name):
        """Sauvegarde dans SQL Server si possible, sinon en CSV."""
        if self.engine is not None:
            try:
                print(f"  → Insertion SQL Server (table: Bronze.staging_{table_name})...")
                df.to_sql(f'staging_{table_name}', con=self.engine, schema='Bronze', if_exists='append', index=False)
                print(f"  ✅ {len(df)} lignes insérées avec succès.")
                return
            except Exception as e:
                print(f"  ⚠️ Échec SQL: {e}")
        
        # Fallback CSV
        csv_path = os.path.join(OUTPUT_DIR, f"staging_{table_name}.csv")
        df.to_csv(csv_path, index=False)
        print(f"  📁 Fallback CSV: {csv_path} ({len(df)} lignes)")

    def _extract_daily_anomalies(self, df_infra):
        """
        Extrait un dictionnaire {date_str: nb_anomalies} depuis le DataFrame infra.
        Ce dictionnaire sert de pont causal vers ITSM et Applications.
        """
        anomalies = df_infra[df_infra['Is_Anomaly'] == 1].copy()
        anomalies['DateOnly'] = pd.to_datetime(anomalies['Timestamp']).dt.strftime('%Y-%m-%d')
        daily = anomalies.groupby('DateOnly').size().to_dict()
        return daily

    def _extract_monthly_csat(self, df_itsm):
        """
        Extrait un dictionnaire {mois_str: csat_moyen} depuis le DataFrame ITSM.
        Sert de pont causal vers la Gouvernance (Satisfaction globale IT).
        """
        df = df_itsm.copy()
        df['Mois'] = pd.to_datetime(df['Date']).dt.to_period('M').dt.to_timestamp().dt.strftime('%Y-%m-%d')
        monthly = df.groupby('Mois')['CSAT_Score'].mean().to_dict()
        return monthly

    def run(self):
        print("=" * 65)
        print("🚀 DASHBOARD 360 NOVEC — Génération V2 (55 KPIs)")
        print("=" * 65)
        print(f"📅 Période : {self.start_date.strftime('%Y-%m-%d')} → {self.end_date.strftime('%Y-%m-%d')}")
        print()
        
        # --- ÉTAPE 1 : Infrastructure (source des anomalies) ---
        print("[1/8] 🖥️  Infrastructure IT...")
        df_infra = generate_infrastructure(self.daterange_hours, self.start_date)
        infra_daily_anomalies = self._extract_daily_anomalies(df_infra)
        nb_anomalies = sum(infra_daily_anomalies.values())
        print(f"       Anomalies détectées : {nb_anomalies} événements sur {len(infra_daily_anomalies)} jours distincts")
        self.save_data(df_infra, "infrastructure")
        
        # --- ÉTAPE 2 : ITSM (consomme les anomalies infra) ---
        print("[2/8] 🎫 ITSM / Service Desk...")
        df_itsm = generate_itsm(self.daterange_days, infra_daily_anomalies)
        itsm_monthly_csat = self._extract_monthly_csat(df_itsm)
        self.save_data(df_itsm, "itsm_tickets")
        
        # --- ÉTAPE 3 : Cybersécurité (indépendant) ---
        print("[3/8] 🛡️  Cybersécurité...")
        df_cyber = generate_cyber(self.daterange_days, self.start_date)
        self.save_data(df_cyber, "cybersecurity")
        
        # --- ÉTAPE 4 : Applications (consomme anomalies infra) ---
        print("[4/8] 📱 Applications & BI...")
        df_apps = generate_applications(self.daterange_days, self.start_date, infra_daily_anomalies)
        self.save_data(df_apps, "applications")
        
        # --- ÉTAPE 5 : ITAM (indépendant) ---
        print("[5/8] 💻 ITAM / Actifs IT...")
        df_itam = generate_itam(self.daterange_months)
        self.save_data(df_itam, "itam")
        
        # --- ÉTAPE 6 : Parc Auto (indépendant) ---
        print("[6/8] 🚗 Parc Automobile...")
        df_fleet = generate_fleet(self.daterange_days)
        self.save_data(df_fleet, "parc_auto")
        
        # --- ÉTAPE 7 : Maintenance (indépendant) ---
        print("[7/8] 🔧 Maintenance...")
        df_maintenance = generate_maintenance(self.daterange_months)
        self.save_data(df_maintenance, "maintenance")
        
        # --- ÉTAPE 8 : Gouvernance (consomme CSAT ITSM) ---
        print("[8/8] 📊 Gouvernance & Stratégie...")
        df_gouvernance = generate_gouvernance(self.daterange_months, itsm_monthly_csat)
        self.save_data(df_gouvernance, "gouvernance")
        
        # --- RÉSUMÉ STATISTIQUE ---
        print()
        print("=" * 65)
        print("📊 RÉSUMÉ STATISTIQUE DU DATASET GÉNÉRÉ")
        print("=" * 65)
        datasets = {
            'Infrastructure': df_infra,
            'ITSM': df_itsm,
            'Cybersécurité': df_cyber,
            'Applications': df_apps,
            'ITAM': df_itam,
            'Parc Auto': df_fleet,
            'Maintenance': df_maintenance,
            'Gouvernance': df_gouvernance
        }
        total_rows = 0
        total_cols = 0
        for name, df in datasets.items():
            total_rows += len(df)
            total_cols += len(df.columns)
            print(f"  {name:20s} | {len(df):>6} lignes | {len(df.columns):>2} colonnes")
        print(f"  {'─' * 50}")
        print(f"  {'TOTAL':20s} | {total_rows:>6} lignes | {total_cols:>2} colonnes")
        print()
        print("✅ Génération V2 terminée avec succès.")

if __name__ == '__main__':
    # Génération sur 12 mois pour un dataset ML robuste
    end = datetime.now()
    start = end - timedelta(days=365)
    
    orchestrator = OrchestratorSimulator(start, end)
    orchestrator.run()
