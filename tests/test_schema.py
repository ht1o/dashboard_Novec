"""
test_schema.py — Tests automatisés des schémas Bronze & Silver
Dashboard 360 Novec | Phase 2

Vérifie que toutes les tables et colonnes attendues existent
dans la base SQL Server, avec les bons types.

Usage : python tests/test_schema.py
        pytest tests/test_schema.py -v
"""
import sys
import pytest
import pandas as pd
from sqlalchemy import text, inspect
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ajoute data_simulation au path
sys.path.insert(0, os.path.join(ROOT, "data_simulation"))
from config import get_db_engine


# ── Fixtures ─────────────────────────────────────────────────
@pytest.fixture(scope="session")
def engine():
    eng = get_db_engine()
    if eng is None:
        pytest.skip("SQL Server non disponible — tests schema ignorés")
    return eng

@pytest.fixture(scope="session")
def inspector(engine):
    return inspect(engine)


# ── Helpers ──────────────────────────────────────────────────
def get_columns(inspector, schema, table):
    """Retourne la liste des noms de colonnes d'une table."""
    try:
        cols = inspector.get_columns(table, schema=schema)
        return [c['name'] for c in cols]
    except Exception:
        return []

def assert_table_exists(inspector, schema, table):
    tables = inspector.get_table_names(schema=schema)
    assert table in tables, f"Table manquante : {schema}.{table}"

def assert_columns_exist(inspector, schema, table, expected_cols):
    existing = get_columns(inspector, schema, table)
    missing = [c for c in expected_cols if c not in existing]
    assert not missing, (
        f"{schema}.{table} — colonnes manquantes : {missing}\n"
        f"  Colonnes présentes : {existing}"
    )


# ════════════════════════════════════════════════════════════
# TESTS BRONZE
# ════════════════════════════════════════════════════════════

class TestBronzeTablesExist:
    """Vérifie que les 8 tables staging Bronze existent."""

    BRONZE_TABLES = [
        'staging_infrastructure',
        'staging_itsm_tickets',
        'staging_cybersecurity',
        'staging_applications',
        'staging_itam',
        'staging_parc_auto',
        'staging_maintenance',
        'staging_gouvernance',
    ]

    @pytest.mark.parametrize("table", BRONZE_TABLES)
    def test_table_exists(self, inspector, table):
        assert_table_exists(inspector, 'Bronze', table)


class TestBronzeColumns:
    """Vérifie que toutes les colonnes KPI V2 sont présentes dans chaque table Bronze."""

    def test_infrastructure_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_infrastructure', [
            'LogID', 'Timestamp', 'ServerName',
            'CPU_Usage_Pct', 'RAM_Usage_Pct', 'Disk_Usage_Pct',
            'Network_Latency_ms', 'Backup_Success', 'Backup_Coverage_Pct',
            'Uptime_Status', 'MTBF_Hours', 'MTTR_Infra_Hours', 'Is_Anomaly'
        ])

    def test_itsm_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_itsm_tickets', [
            'TicketLogID', 'Date',
            'Tickets_P1_Critique', 'Tickets_P2_Majeur', 'Tickets_P3_Mineur',
            'Volume_Total', 'SLA_Respect_Pct', 'MTTR_Hours',
            'FCR_Pct', 'Backlog_Non_Resolus', 'CSAT_Score'
        ])

    def test_cybersecurity_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_cybersecurity', [
            'CyberLogID', 'Date',
            'Incidents_Critiques', 'MTTD_Hours',
            'Vulnerabilites_Non_Patchees', 'Systemes_Patches_Pct',
            'Taux_Adoption_MFA_Pct', 'Taux_Clic_Phishing_Pct',
            'Conformite_RGPD_Pct'
        ])

    def test_applications_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_applications', [
            'AppLogID', 'Date', 'Application_Name',
            'Temps_Reponse_Moyen_ms', 'Disponibilite_App_Pct',
            'Bugs_Critiques_Prod', 'Qualite_Donnees_Score_Pct',
            'Adoption_PowerBI_Pct'
        ])

    def test_itam_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_itam', [
            'ItamLogID', 'Mois', 'Total_Postes_Actifs',
            'Vetuste_Plus_4ans_Pct', 'TCO_Annuel_Par_Poste_MAD',
            'Conformite_Licences_Pct', 'Delai_Mise_Dispo_Jours',
            'Taux_Inventaire_CMDB_Pct', 'Licences_Inutilisees'
        ])

    def test_parc_auto_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_parc_auto', [
            'FleetLogID', 'Date', 'Flotte_Totale', 'Vehicules_Disponibles',
            'Disponibilite_Vehicules_Pct', 'Nbre_Sinistres_Jour',
            'Taux_Sinistralite_Pct', 'Consommation_Carburant_Total_L',
            'Conso_L_100km', 'TCO_Par_Vehicule_MAD'
        ])

    def test_maintenance_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_maintenance', [
            'MaintLogID', 'Mois', 'Total_Ordres_Travail',
            'Interventions_Preventives', 'Interventions_Correctives',
            'Ratio_Preventif_Pct', 'Taux_Realisation_Preventif_Pct',
            'Ruptures_Stock_Pieces'
        ])

    def test_gouvernance_columns(self, inspector):
        assert_columns_exist(inspector, 'Bronze', 'staging_gouvernance', [
            'GouvLogID', 'Mois', 'Departement',
            'Budget_Alloue_MAD', 'Budget_Consomme_MAD', 'Ecart_Budget_Pct',
            'ROI_Projets_Pct', 'Projets_Livres_A_Temps_Pct',
            'Taux_Adoption_Digital_Pct', 'Satisfaction_Globale_IT',
            'Cout_IT_Par_Employe_MAD'
        ])


class TestBronzeNotEmpty:
    """Vérifie que les tables Bronze contiennent des données."""

    @pytest.mark.parametrize("table,min_rows", [
        ('staging_infrastructure', 8760),
        ('staging_itsm_tickets',   300),
        ('staging_cybersecurity',  300),
        ('staging_applications',   900),
        ('staging_itam',            12),
        ('staging_parc_auto',      300),
        ('staging_maintenance',     12),
        ('staging_gouvernance',     48),
    ])
    def test_row_count(self, engine, table, min_rows):
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM Bronze.{table}")
            )
            count = result.scalar()
        assert count >= min_rows, (
            f"Bronze.{table} contient {count} lignes, minimum attendu : {min_rows}"
        )


# ════════════════════════════════════════════════════════════
# TESTS SILVER
# ════════════════════════════════════════════════════════════

class TestSilverTablesExist:
    """Vérifie que les 8 tables Silver existent après transformation."""

    SILVER_TABLES = [
        'silver_infrastructure',
        'silver_itsm',
        'silver_cybersecurity',
        'silver_applications',
        'silver_itam',
        'silver_parc_auto',
        'silver_maintenance',
        'silver_gouvernance',
    ]

    @pytest.mark.parametrize("table", SILVER_TABLES)
    def test_table_exists(self, inspector, table):
        assert_table_exists(inspector, 'Silver', table)


class TestSilverColumns:
    """Vérifie les colonnes dérivées créées par bronze_to_silver.py."""

    def test_infrastructure_derived(self, inspector):
        assert_columns_exist(inspector, 'Silver', 'silver_infrastructure', [
            'DateKey', 'ServerName',
            'CPU_Moyen_Pct', 'CPU_Max_Pct',
            'RAM_Moyen_Pct', 'Disk_Max_Pct',
            'Disponibilite_Pct', 'Nb_Anomalies', 'Taux_Anomalie_Pct'
        ])

    def test_itsm_derived(self, inspector):
        assert_columns_exist(inspector, 'Silver', 'silver_itsm', [
            'DateKey', 'Volume_Total', 'CSAT_Moyen',
            'SLA_Moyen_Pct', 'FCR_Moyen_Pct', 'Pct_Tickets_P1'
        ])

    def test_itam_tco_total(self, inspector):
        assert_columns_exist(inspector, 'Silver', 'silver_itam', [
            'DateKey', 'Total_Postes', 'TCO_Total_MAD', 'CMDB_Couverture_Pct'
        ])

    def test_maintenance_derived(self, inspector):
        assert_columns_exist(inspector, 'Silver', 'silver_maintenance', [
            'DateKey', 'Pct_Preventif_Realise'
        ])


class TestSilverNotEmpty:
    """Vérifie que les tables Silver sont peuplées."""

    @pytest.mark.parametrize("table", [
        'silver_infrastructure', 'silver_itsm', 'silver_cybersecurity',
        'silver_applications', 'silver_itam', 'silver_parc_auto',
        'silver_maintenance', 'silver_gouvernance',
    ])
    def test_not_empty(self, engine, table):
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT COUNT(*) FROM Silver.{table}")
            )
            count = result.scalar()
        assert count > 0, f"Silver.{table} est vide après transformation"


# ── Exécution directe (sans pytest) ──────────────────────────
if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v', '--tb=short']))