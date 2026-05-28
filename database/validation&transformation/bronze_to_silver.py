"""
bronze_to_silver.py — Pipeline de transformation Bronze → Silver
Dashboard 360 Novec | Phase 2

Rôle : Lire les tables Bronze, appliquer nettoyage + agrégations,
       écrire dans les tables Silver matérialisées.

"""
import sys
import numpy as np
import pandas as pd
import os

# Remonte 3 niveaux : validation&transformation → database → racine
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ajoute data_simulation au path
sys.path.insert(0, os.path.join(ROOT, "data_simulation"))
from config import get_db_engine


def save_silver(df, table_name, engine):
    """Écrit un DataFrame dans Silver.<table_name> (remplace à chaque run)."""
    try:
        df.to_sql(table_name, con=engine, schema='Silver',
                  if_exists='replace', index=False)
        print(f"  ✅ Silver.{table_name} — {len(df)} lignes / {len(df.columns)} colonnes")
    except Exception as e:
        print(f"  ❌ Silver.{table_name} — ERREUR : {e}")


# ============================================================
# [1/8] INFRASTRUCTURE — agrégation horaire → journalière
# ============================================================
def transform_infrastructure(engine):
    print("[1/8] Infrastructure...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_infrastructure", engine)
    df['DateKey'] = pd.to_datetime(df['Timestamp']).dt.date

    agg = df.groupby(['DateKey', 'ServerName']).agg(
        CPU_Moyen_Pct         = ('CPU_Usage_Pct',        'mean'),
        CPU_Max_Pct           = ('CPU_Usage_Pct',        'max'),
        RAM_Moyen_Pct         = ('RAM_Usage_Pct',        'mean'),
        RAM_Max_Pct           = ('RAM_Usage_Pct',        'max'),
        Disk_Moyen_Pct        = ('Disk_Usage_Pct',       'mean'),
        Disk_Max_Pct          = ('Disk_Usage_Pct',       'max'),
        Latence_Moyenne_ms    = ('Network_Latency_ms',   'mean'),
        Latence_Max_ms        = ('Network_Latency_ms',   'max'),
        Backup_Success_Count  = ('Backup_Success',       'sum'),
        Backup_Coverage_Pct   = ('Backup_Coverage_Pct',  'mean'),
        MTBF_Moyen_Hours      = ('MTBF_Hours',           'mean'),
        MTTR_Moyen_Hours      = ('MTTR_Infra_Hours',     'mean'),
        Nb_Anomalies          = ('Is_Anomaly',           'sum'),
        Nb_Mesures            = ('Is_Anomaly',           'count'),
    ).reset_index()

    # Disponibilité = % d'heures en Uptime_Status=1 (sans .apply())
    dispo = (
        df.groupby(['DateKey', 'ServerName'])['Uptime_Status']
        .mean() * 100.0
    ).reset_index(name='Disponibilite_Pct')
    agg = agg.merge(dispo, on=['DateKey', 'ServerName'], how='left')

    agg['Taux_Anomalie_Pct'] = (
        agg['Nb_Anomalies'] * 100.0 / agg['Nb_Mesures'].replace(0, np.nan)
    ).fillna(0)

    for col in agg.select_dtypes('float').columns:
        agg[col] = agg[col].round(2)

    save_silver(agg, 'silver_infrastructure', engine)


# ============================================================
# [2/8] ITSM
# ============================================================
def transform_itsm(engine):
    print("[2/8] ITSM...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_itsm_tickets", engine)
    df['DateKey'] = pd.to_datetime(df['Date']).dt.date

    agg = df.groupby('DateKey').agg(
        Total_P1          = ('Tickets_P1_Critique', 'sum'),
        Total_P2          = ('Tickets_P2_Majeur',   'sum'),
        Total_P3          = ('Tickets_P3_Mineur',   'sum'),
        Volume_Total      = ('Volume_Total',         'sum'),
        Backlog_Total     = ('Backlog_Non_Resolus',  'sum'),
        SLA_Moyen_Pct     = ('SLA_Respect_Pct',     'mean'),
        FCR_Moyen_Pct     = ('FCR_Pct',             'mean'),
        MTTR_Moyen_Hours  = ('MTTR_Hours',           'mean'),
        CSAT_Moyen        = ('CSAT_Score',           'mean'),
    ).reset_index()

    agg['Pct_Tickets_P1'] = (
        agg['Total_P1'] * 100.0 / agg['Volume_Total'].replace(0, np.nan)
    ).fillna(0)

    for col in agg.select_dtypes('float').columns:
        agg[col] = agg[col].round(2)

    save_silver(agg, 'silver_itsm', engine)


# ============================================================
# [3/8] CYBERSÉCURITÉ
# ============================================================
def transform_cyber(engine):
    print("[3/8] Cybersécurité...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_cybersecurity", engine)
    df['DateKey'] = pd.to_datetime(df['Date']).dt.date

    agg = df.groupby('DateKey').agg(
        Nb_Incidents_Critiques      = ('Incidents_Critiques',        'sum'),
        MTTD_Moyen_Hours            = ('MTTD_Hours',                 'mean'),
        Total_Vuln_Non_Patchees     = ('Vulnerabilites_Non_Patchees', 'sum'),
        Systemes_Patches_Moyen_Pct  = ('Systemes_Patches_Pct',       'mean'),
        MFA_Adoption_Pct            = ('Taux_Adoption_MFA_Pct',      'mean'),
        Taux_Phishing_Moyen_Pct     = ('Taux_Clic_Phishing_Pct',     'mean'),
        RGPD_Conformite_Pct         = ('Conformite_RGPD_Pct',        'mean'),
    ).reset_index()

    for col in agg.select_dtypes('float').columns:
        agg[col] = agg[col].round(2)

    save_silver(agg, 'silver_cybersecurity', engine)


# ============================================================
# [4/8] APPLICATIONS
# ============================================================
def transform_applications(engine):
    print("[4/8] Applications...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_applications", engine)
    df['DateKey'] = pd.to_datetime(df['Date']).dt.date

    agg = df.groupby(['DateKey', 'Application_Name']).agg(
        Temps_Reponse_Moyen_ms = ('Temps_Reponse_Moyen_ms',    'mean'),
        Temps_Reponse_Max_ms   = ('Temps_Reponse_Moyen_ms',    'max'),
        Disponibilite_Pct      = ('Disponibilite_App_Pct',     'mean'),
        Nb_Bugs_Critiques      = ('Bugs_Critiques_Prod',       'sum'),
        Qualite_Donnees_Pct    = ('Qualite_Donnees_Score_Pct', 'mean'),
        Adoption_PowerBI_Pct   = ('Adoption_PowerBI_Pct',      'mean'),
    ).reset_index()

    for col in agg.select_dtypes('float').columns:
        agg[col] = agg[col].round(2)

    save_silver(agg, 'silver_applications', engine)


# ============================================================
# [5/8] ITAM
# ============================================================
def transform_itam(engine):
    print("[5/8] ITAM...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_itam", engine)
    df['DateKey'] = pd.to_datetime(df['Mois']).dt.date

    df['TCO_Total_MAD'] = (
        df['Total_Postes_Actifs'] * df['TCO_Annuel_Par_Poste_MAD']
    ).round(2)

    out = df.rename(columns={
        'Total_Postes_Actifs':      'Total_Postes',
        'Vetuste_Plus_4ans_Pct':    'Vetuste_Moyen_Pct',
        'TCO_Annuel_Par_Poste_MAD': 'TCO_Moyen_Par_Poste_MAD',
        'Delai_Mise_Dispo_Jours':   'Delai_Mise_Dispo_Moyen_Jours',
        'Taux_Inventaire_CMDB_Pct': 'CMDB_Couverture_Pct',
        'Licences_Inutilisees':     'Total_Licences_Inutilisees',
    })[['DateKey', 'Total_Postes', 'Vetuste_Moyen_Pct',
        'TCO_Moyen_Par_Poste_MAD', 'TCO_Total_MAD',
        'Conformite_Licences_Pct', 'Total_Licences_Inutilisees',
        'Delai_Mise_Dispo_Moyen_Jours', 'CMDB_Couverture_Pct']]

    save_silver(out, 'silver_itam', engine)


# ============================================================
# [6/8] PARC AUTO
# ============================================================
def transform_parc_auto(engine):
    print("[6/8] Parc Auto...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_parc_auto", engine)
    df['DateKey'] = pd.to_datetime(df['Date']).dt.date

    agg = df.groupby('DateKey').agg(
        Flotte_Totale               = ('Flotte_Totale',                 'max'),
        Vehicules_Disponibles       = ('Vehicules_Disponibles',          'sum'),
        Disponibilite_Pct           = ('Disponibilite_Vehicules_Pct',    'mean'),
        Nb_Sinistres                = ('Nbre_Sinistres_Jour',            'sum'),
        Taux_Sinistralite_Pct       = ('Taux_Sinistralite_Pct',          'mean'),
        Conso_Totale_L              = ('Consommation_Carburant_Total_L', 'sum'),
        Conso_Moyenne_L100km        = ('Conso_L_100km',                  'mean'),
        TCO_Moyen_Par_Vehicule_MAD  = ('TCO_Par_Vehicule_MAD',           'mean'),
    ).reset_index()

    for col in agg.select_dtypes('float').columns:
        agg[col] = agg[col].round(2)

    save_silver(agg, 'silver_parc_auto', engine)


# ============================================================
# [7/8] MAINTENANCE
# ============================================================
def transform_maintenance(engine):
    print("[7/8] Maintenance...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_maintenance", engine)
    df['DateKey'] = pd.to_datetime(df['Mois']).dt.date

    df['Pct_Preventif_Realise'] = (
        df['Interventions_Preventives'] * 100.0
        / df['Total_Ordres_Travail'].replace(0, np.nan)
    ).fillna(0).round(2)

    # Renommage pour alignement avec le nom attendu côté Silver/ARIMA
    df = df.rename(columns={'Ruptures_Stock_Pieces': 'Total_Ruptures_Stock'})

    cols = ['DateKey', 'Total_Ordres_Travail', 'Interventions_Preventives',
            'Interventions_Correctives', 'Ratio_Preventif_Pct',
            'Taux_Realisation_Preventif_Pct', 'Total_Ruptures_Stock',  # ← corrigé
            'Pct_Preventif_Realise']

    save_silver(df[cols], 'silver_maintenance', engine)


# ============================================================
# [8/8] GOUVERNANCE
# ============================================================
def transform_gouvernance(engine):
    print("[8/8] Gouvernance...")
    df = pd.read_sql("SELECT * FROM Bronze.staging_gouvernance", engine)
    df['DateKey'] = pd.to_datetime(df['Mois']).dt.date

    agg = df.groupby(['DateKey', 'Departement']).agg(
        Budget_Alloue_MAD       = ('Budget_Alloue_MAD',         'sum'),
        Budget_Consomme_MAD     = ('Budget_Consomme_MAD',        'sum'),
        Ecart_Budget_Moyen_Pct  = ('Ecart_Budget_Pct',           'mean'),
        ROI_Moyen_Pct           = ('ROI_Projets_Pct',            'mean'),
        Projets_A_Temps_Pct     = ('Projets_Livres_A_Temps_Pct', 'mean'),
        Adoption_Digital_Pct    = ('Taux_Adoption_Digital_Pct',  'mean'),
        CSAT_IT_Moyen           = ('Satisfaction_Globale_IT',     'mean'),
        Cout_IT_Par_Employe_MAD = ('Cout_IT_Par_Employe_MAD',     'mean'),
    ).reset_index()

    for col in agg.select_dtypes('float').columns:
        agg[col] = agg[col].round(2)

    save_silver(agg, 'silver_gouvernance', engine)


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("  BRONZE → SILVER — Dashboard 360 Novec")
    print("=" * 60)

    engine = get_db_engine()
    if engine is None:
        print("❌ Impossible de se connecter à SQL Server. Vérifiez le .env")
        sys.exit(1)
    print("[OK] Connexion établie.\n")

    transform_infrastructure(engine)
    transform_itsm(engine)
    transform_cyber(engine)
    transform_applications(engine)
    transform_itam(engine)
    transform_parc_auto(engine)
    transform_maintenance(engine)
    transform_gouvernance(engine)

    print()
    print("=" * 60)
    print("✅ Pipeline Bronze → Silver terminé avec succès.")
    print("=" * 60)


if __name__ == '__main__':
    main()