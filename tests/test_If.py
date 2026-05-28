"""
test_If.py — Tests unitaires Isolation Forest Detector
Dashboard 360° Novec | Tests offline (sans SQL Server)

Valide : détection multivariée, score de confiance, taux d'anomalies,
colonnes résultat, gestion des cas limites.

Usage : pytest tests/test_If.py -v
"""
import numpy as np
import pandas as pd
import pytest

from ml.anomaly_detection.isolation_forest_detector import (
    IsolationForestDetector,
    CONTAMINATION,
    N_ESTIMATORS,
)


# ════════════════════════════════════════════════════════════
# TESTS INITIALISATION
# ════════════════════════════════════════════════════════════

class TestIFInit:
    """Vérifie les hyperparamètres par défaut."""

    def test_default_contamination(self):
        detector = IsolationForestDetector()
        assert detector.contamination == CONTAMINATION

    def test_custom_contamination(self):
        detector = IsolationForestDetector(contamination=0.10)
        assert detector.contamination == 0.10

    def test_n_estimators_constant(self):
        assert N_ESTIMATORS == 100


# ════════════════════════════════════════════════════════════
# TESTS DÉTECTION PAR DOMAINE
# ════════════════════════════════════════════════════════════

class TestIFDetection:
    """Vérifie la détection sur chaque domaine Silver."""

    def test_detect_infrastructure(self, silver_infra):
        detector = IsolationForestDetector()
        result = detector.detect_infrastructure(silver_infra)

        assert not result.empty, "Résultat infrastructure ne devrait pas être vide"
        assert "Anomalie_IF" in result.columns
        assert "Score_IF" in result.columns
        assert "Score_Confiance" in result.columns
        assert "Domaine" in result.columns
        assert (result["Domaine"] == "Infrastructure").all()

    def test_detect_infrastructure_per_server(self, silver_infra):
        """Vérifie qu'un modèle est entraîné PAR SERVEUR."""
        detector = IsolationForestDetector()
        result = detector.detect_infrastructure(silver_infra)
        servers_in = silver_infra["ServerName"].nunique()
        servers_out = result["ServerName"].nunique()
        assert servers_out == servers_in, (
            f"Attendu {servers_in} serveurs, trouvé {servers_out}"
        )

    def test_detect_itsm(self, silver_itsm):
        detector = IsolationForestDetector()
        result = detector.detect_itsm(silver_itsm)

        assert not result.empty
        assert (result["Domaine"] == "ITSM").all()
        # ITSM n'a pas de group_col → pas de colonne ServerName
        assert "ServerName" not in result.columns

    def test_detect_cybersecurity(self, silver_cyber):
        detector = IsolationForestDetector()
        result = detector.detect_cybersecurity(silver_cyber)

        assert not result.empty
        assert (result["Domaine"] == "Cybersécurité").all()

    def test_detect_applications(self, silver_apps):
        detector = IsolationForestDetector()
        result = detector.detect_applications(silver_apps)

        assert not result.empty
        assert (result["Domaine"] == "Applications").all()
        # Groupé par Application_Name
        assert "Application_Name" in result.columns

    def test_run_all(self, all_silver_data):
        """run_all() concatène les 4 domaines."""
        detector = IsolationForestDetector()
        result = detector.run_all(all_silver_data)

        assert not result.empty
        domaines = set(result["Domaine"].unique())
        expected = {"Infrastructure", "ITSM", "Cybersécurité", "Applications"}
        assert domaines == expected, f"Domaines manquants : {expected - domaines}"


# ════════════════════════════════════════════════════════════
# TESTS QUALITÉ DES RÉSULTATS
# ════════════════════════════════════════════════════════════

class TestIFQuality:
    """Vérifie la cohérence des scores et taux."""

    def test_anomaly_rate_near_contamination(self, silver_infra):
        """Le taux d'anomalies doit être proche de contamination (5%)."""
        detector = IsolationForestDetector(contamination=0.05)
        result = detector.detect_infrastructure(silver_infra)
        rate = result["Anomalie_IF"].mean()
        # Tolérance : entre 2% et 10% (marge large car par serveur)
        assert 0.02 <= rate <= 0.10, f"Taux anomalies {rate:.2%} hors tolérance"

    def test_score_confiance_range(self, all_silver_data):
        """Score_Confiance doit être dans [0, 1]."""
        detector = IsolationForestDetector()
        result = detector.run_all(all_silver_data)
        assert result["Score_Confiance"].min() >= 0.0, "Score < 0 détecté"
        assert result["Score_Confiance"].max() <= 1.0, "Score > 1 détecté"

    def test_anomalie_if_binary(self, all_silver_data):
        """Anomalie_IF doit être 0 ou 1."""
        detector = IsolationForestDetector()
        result = detector.run_all(all_silver_data)
        assert set(result["Anomalie_IF"].unique()).issubset({0, 1})

    def test_anomalies_have_high_confidence(self, all_silver_data):
        """Les anomalies (IF=1) devraient avoir un Score_Confiance élevé."""
        detector = IsolationForestDetector()
        result = detector.run_all(all_silver_data)
        anomalies = result[result["Anomalie_IF"] == 1]
        if not anomalies.empty:
            mean_conf = anomalies["Score_Confiance"].mean()
            assert mean_conf > 0.5, (
                f"Confiance moyenne anomalies = {mean_conf:.2f}, attendu > 0.5"
            )


# ════════════════════════════════════════════════════════════
# TESTS CAS LIMITES
# ════════════════════════════════════════════════════════════

class TestIFEdgeCases:
    """Gestion des entrées vides ou trop petites."""

    def test_empty_dataframe(self):
        detector = IsolationForestDetector()
        empty_df = pd.DataFrame(columns=[
            "DateKey", "CPU_Moyen_Pct", "RAM_Moyen_Pct",
            "Latence_Moyenne_ms", "Disk_Moyen_Pct",
            "Disponibilite_Pct", "ServerName",
        ])
        result = detector.detect_infrastructure(empty_df)
        assert result.empty

    def test_small_group_skipped(self):
        """Groupe < 10 lignes → ignoré (pas de crash)."""
        detector = IsolationForestDetector()
        small_df = pd.DataFrame({
            "DateKey": pd.date_range("2025-01-01", periods=5),
            "ServerName": "SRV-TINY",
            "CPU_Moyen_Pct": [50, 55, 60, 52, 48],
            "RAM_Moyen_Pct": [40, 42, 38, 41, 39],
            "Latence_Moyenne_ms": [20, 25, 22, 21, 23],
            "Disk_Moyen_Pct": [30, 32, 28, 31, 29],
            "Disponibilite_Pct": [99.9, 99.8, 99.9, 99.7, 99.9],
        })
        result = detector.detect_infrastructure(small_df)
        assert result.empty, "Groupe de 5 lignes devrait être ignoré"

    def test_run_all_with_missing_domain(self):
        """run_all avec un domaine manquant → pas de crash."""
        detector = IsolationForestDetector()
        partial_data = {
            "infra": pd.DataFrame(),
            "itsm": pd.DataFrame(),
            "cyber": pd.DataFrame(),
            "apps": pd.DataFrame(),
        }
        result = detector.run_all(partial_data)
        assert result.empty


# ── Exécution directe ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
