"""
test_pipeline_bsg.py — Tests end-to-end du pipeline de données
Dashboard 360 Novec | Phase 2 → Gold (préparé)

Couvre :
  - Cohérence Bronze → Silver (lignes non perdues, valeurs nulles)
  - Corrélations causales inter-domaines (infra → ITSM, ITSM → Gouvernance)
  - Plages de valeurs Silver après transformation
  - [Gold] Structure préparée pour Phase 3

Usage : python tests/test_pipeline.py
        pytest tests/test_pipeline.py -v
"""
import sys
import pytest
import pandas as pd
import numpy as np
from sqlalchemy import text

sys.path.insert(0, ".")
from config import get_db_engine


# ── Fixture globale ───────────────────────────────────────────
@pytest.fixture(scope="session")
def engine():
    eng = get_db_engine()
    if eng is None:
        pytest.skip("SQL Server non disponible — tests pipeline ignorés")
    return eng

def read(engine, schema, table):
    return pd.read_sql(f"SELECT * FROM {schema}.{table}", engine)


# ════════════════════════════════════════════════════════════
# COHÉRENCE Bronze → Silver
# ════════════════════════════════════════════════════════════

class TestBronzeToSilverConsistency:
    """Les tables Silver doivent être des agrégations sans perte d'info critique."""

    def test_infrastructure_silver_less_rows_than_bronze(self, engine):
        """Silver infra = agrégation journalière : doit avoir moins de lignes que Bronze."""
        bronze_count = pd.read_sql(
            "SELECT COUNT(*) AS n FROM Bronze.staging_infrastructure", engine
        ).iloc[0, 0]
        silver_count = pd.read_sql(
            "SELECT COUNT(*) AS n FROM Silver.silver_infrastructure", engine
        ).iloc[0, 0]
        assert silver_count < bronze_count, (
            f"Silver ({silver_count}) devrait avoir moins de lignes que Bronze ({bronze_count})"
        )

    def test_itsm_silver_volume_total_matches_bronze(self, engine):
        """La somme des Volume_Total doit être identique entre Bronze et Silver."""
        bronze_sum = pd.read_sql(
            "SELECT SUM(Volume_Total) AS s FROM Bronze.staging_itsm_tickets", engine
        ).iloc[0, 0]
        silver_sum = pd.read_sql(
            "SELECT SUM(Volume_Total) AS s FROM Silver.silver_itsm", engine
        ).iloc[0, 0]
        assert abs(bronze_sum - silver_sum) < 1, (
            f"Perte de données ITSM : Bronze={bronze_sum}, Silver={silver_sum}"
        )

    def test_maintenance_silver_row_count(self, engine):
        """Maintenance mensuelle : Silver doit avoir ≥ 12 lignes."""
        count = pd.read_sql(
            "SELECT COUNT(*) AS n FROM Silver.silver_maintenance", engine
        ).iloc[0, 0]
        assert count >= 12, f"silver_maintenance trop peu de lignes : {count}"

    def test_gouvernance_silver_departments_present(self, engine):
        """Tous les 4 départements doivent être présents dans Silver gouvernance."""
        df = pd.read_sql(
            "SELECT DISTINCT Departement FROM Silver.silver_gouvernance", engine
        )
        expected = {'IT-Operations', 'Cybersecurité', 'Data', 'Projets'}
        found = set(df['Departement'].tolist())
        missing = expected - found
        assert not missing, f"Départements manquants dans Silver : {missing}"


# ════════════════════════════════════════════════════════════
# PLAGES DE VALEURS SILVER
# ════════════════════════════════════════════════════════════

class TestSilverValueRanges:
    """Vérifie que les colonnes dérivées restent dans des plages cohérentes."""

    def test_infrastructure_cpu_moyen_range(self, engine):
        df = read(engine, 'Silver', 'silver_infrastructure')
        assert df['CPU_Moyen_Pct'].between(0, 100).all(), \
            "CPU_Moyen_Pct hors [0, 100]"

    def test_infrastructure_disponibilite_range(self, engine):
        df = read(engine, 'Silver', 'silver_infrastructure')
        assert df['Disponibilite_Pct'].between(0, 100).all(), \
            "Disponibilite_Pct hors [0, 100]"

    def test_infrastructure_taux_anomalie_non_negative(self, engine):
        df = read(engine, 'Silver', 'silver_infrastructure')
        assert (df['Taux_Anomalie_Pct'] >= 0).all(), \
            "Taux_Anomalie_Pct contient des valeurs négatives"

    def test_itsm_csat_range(self, engine):
        df = read(engine, 'Silver', 'silver_itsm')
        assert df['CSAT_Moyen'].between(1, 5).all(), \
            "CSAT_Moyen hors [1, 5]"

    def test_itsm_sla_range(self, engine):
        df = read(engine, 'Silver', 'silver_itsm')
        assert df['SLA_Moyen_Pct'].between(0, 100).all(), \
            "SLA_Moyen_Pct hors [0, 100]"

    def test_cyber_patches_range(self, engine):
        df = read(engine, 'Silver', 'silver_cybersecurity')
        assert df['Systemes_Patches_Moyen_Pct'].between(0, 100).all(), \
            "Systemes_Patches_Moyen_Pct hors [0, 100]"

    def test_itam_tco_total_positive(self, engine):
        df = read(engine, 'Silver', 'silver_itam')
        assert (df['TCO_Total_MAD'] > 0).all(), \
            "TCO_Total_MAD contient des valeurs ≤ 0"

    def test_parc_auto_disponibilite(self, engine):
        df = read(engine, 'Silver', 'silver_parc_auto')
        assert df['Disponibilite_Pct'].between(0, 100).all(), \
            "Disponibilite_Pct Parc Auto hors [0, 100]"

    def test_maintenance_pct_preventif(self, engine):
        df = read(engine, 'Silver', 'silver_maintenance')
        assert df['Pct_Preventif_Realise'].between(0, 100).all(), \
            "Pct_Preventif_Realise hors [0, 100]"


# ════════════════════════════════════════════════════════════
# CORRÉLATIONS CAUSALES INTER-DOMAINES
# ════════════════════════════════════════════════════════════

class TestCausalCorrelations:
    """
    Vérifie les corrélations causales câblées dans l'orchestrateur.
    Ces tests peuvent être SOFT (warning) sur données simulées courtes.
    """

    def test_anomaly_days_have_more_p1_tickets(self, engine):
        """
        Les jours avec anomalies infra (Nb_Anomalies > 0) doivent avoir
        en moyenne plus de tickets P1 que les jours sans anomalie.
        """
        infra = read(engine, 'Silver', 'silver_infrastructure')
        itsm  = read(engine, 'Silver', 'silver_itsm')

        infra['DateKey'] = pd.to_datetime(infra['DateKey'])
        itsm['DateKey']  = pd.to_datetime(itsm['DateKey'])

        # Agréger infra par date (plusieurs serveurs)
        infra_day = infra.groupby('DateKey')['Nb_Anomalies'].sum().reset_index()
        merged = itsm.merge(infra_day, on='DateKey', how='inner')

        if len(merged) < 30:
            pytest.skip("Pas assez de données pour tester la corrélation")

        mean_p1_anomaly    = merged.loc[merged['Nb_Anomalies'] > 0,  'Total_P1'].mean()
        mean_p1_no_anomaly = merged.loc[merged['Nb_Anomalies'] == 0, 'Total_P1'].mean()

        assert mean_p1_anomaly >= mean_p1_no_anomaly * 0.9, (
            f"Corrélation infra→ITSM P1 faible : "
            f"anomalie={mean_p1_anomaly:.1f} vs normal={mean_p1_no_anomaly:.1f}"
        )

    def test_itsm_csat_correlates_with_gouvernance_satisfaction(self, engine):
        """
        La satisfaction IT mensuelle (gouvernance) doit être corrélée
        positivement avec le CSAT ITSM moyen mensuel.
        """
        itsm = read(engine, 'Silver', 'silver_itsm')
        gouv = read(engine, 'Silver', 'silver_gouvernance')

        itsm['Mois'] = pd.to_datetime(itsm['DateKey']).dt.to_period('M').dt.to_timestamp()
        gouv['Mois'] = pd.to_datetime(gouv['DateKey']).dt.to_period('M').dt.to_timestamp()

        itsm_monthly = itsm.groupby('Mois')['CSAT_Moyen'].mean().reset_index()
        gouv_monthly = (
            gouv.groupby('Mois')['CSAT_IT_Moyen'].mean().reset_index()
        )

        merged = itsm_monthly.merge(gouv_monthly, on='Mois', how='inner')

        if len(merged) < 6:
            pytest.skip("Moins de 6 mois de données — corrélation non testable")

        corr = merged['CSAT_Moyen'].corr(merged['CSAT_IT_Moyen'])
        assert corr > 0.3, (
            f"Corrélation ITSM→Gouvernance trop faible : r={corr:.3f} (attendu > 0.3)"
        )


# ════════════════════════════════════════════════════════════
# ABSENCE DE NULLS DANS SILVER
# ════════════════════════════════════════════════════════════

class TestSilverNoNullsOnCriticalCols:
    """Les colonnes DateKey ne doivent jamais être NULL dans Silver."""

    @pytest.mark.parametrize("table", [
        'silver_infrastructure', 'silver_itsm', 'silver_cybersecurity',
        'silver_applications', 'silver_itam', 'silver_parc_auto',
        'silver_maintenance', 'silver_gouvernance',
    ])
    def test_datekey_not_null(self, engine, table):
        count = pd.read_sql(
            f"SELECT COUNT(*) AS n FROM Silver.{table} WHERE DateKey IS NULL",
            engine
        ).iloc[0, 0]
        assert count == 0, f"Silver.{table} contient {count} lignes avec DateKey NULL"


# ════════════════════════════════════════════════════════════
# PRÉPARATION GOLD (Phase 3 — structure prête)
# ════════════════════════════════════════════════════════════

class TestGoldReadiness:
    """
    Vérifie que les données Silver ont la structure nécessaire
    pour alimenter la couche Gold (IT Risk Score, agrégations mensuelles).
    Ces tests valident la COMPATIBILITÉ, pas encore les tables Gold.
    """

    def test_silver_has_enough_history_for_ml(self, engine):
        """Il doit y avoir au moins 90 jours de données pour les modèles ML."""
        df = pd.read_sql(
            "SELECT MIN(DateKey) AS min_d, MAX(DateKey) AS max_d "
            "FROM Silver.silver_infrastructure",
            engine
        )
        min_d = pd.to_datetime(df.iloc[0, 0])
        max_d = pd.to_datetime(df.iloc[0, 1])
        days  = (max_d - min_d).days
        assert days >= 90, (
            f"Historique insuffisant pour ML : {days} jours (minimum 90)"
        )

    def test_silver_infra_has_anomaly_column_for_isolation_forest(self, engine):
        """La colonne Nb_Anomalies est requise comme vérité terrain pour Isolation Forest."""
        df = read(engine, 'Silver', 'silver_infrastructure')
        assert 'Nb_Anomalies' in df.columns, \
            "Colonne Nb_Anomalies manquante dans silver_infrastructure"
        assert df['Nb_Anomalies'].sum() > 0, \
            "Nb_Anomalies est toujours 0 — données anomalies non propagées"

    def test_silver_itam_tco_ready_for_regression(self, engine):
        """TCO_Total_MAD et Vetuste_Moyen_Pct doivent exister pour la régression TCO."""
        df = read(engine, 'Silver', 'silver_itam')
        for col in ['TCO_Total_MAD', 'Vetuste_Moyen_Pct', 'TCO_Moyen_Par_Poste_MAD']:
            assert col in df.columns, f"Colonne manquante pour régression TCO : {col}"
            assert df[col].notna().all(), f"{col} contient des NaN"

    def test_silver_gouvernance_all_departments(self, engine):
        """Les 4 départements doivent avoir des données pour le Risk Score composite."""
        df = pd.read_sql(
            "SELECT DISTINCT Departement FROM Silver.silver_gouvernance", engine
        )
        assert len(df) >= 4, (
            f"Seulement {len(df)} département(s) dans silver_gouvernance — "
            f"Risk Score composite impossible"
        )


# ── Exécution directe ─────────────────────────────────────────
if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v', '--tb=short']))