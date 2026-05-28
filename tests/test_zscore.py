"""
test_zscore.py — Tests unitaires ZScore Detector
Dashboard 360° Novec | Tests offline (sans SQL Server)

Valide : fonctions RAG (_compute_rag, _compute_rag_zscore),
détection par domaine, colonnes Gold, anomalies injectées.

Usage : pytest tests/test_zscore.py -v
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from ml.anomaly_detection.zscore_detector import (
    ZScoreDetector,
    ZSCORE_THRESHOLDS,
    SILVER_TABLES,
    DOMAIN_LABELS,
    _compute_rag,
    _compute_rag_zscore,
)


# ════════════════════════════════════════════════════════════
# TESTS FONCTIONS RAG — direction "above"
# ════════════════════════════════════════════════════════════

class TestComputeRAGAbove:
    """Tests _compute_rag avec direction='above'."""

    @pytest.fixture
    def cpu_threshold(self):
        return {"ambre": 80, "rouge": 95, "direction": "above"}

    def test_rouge(self, cpu_threshold):
        rag, score = _compute_rag(96.0, cpu_threshold)
        assert rag == "ROUGE"
        assert 0.80 <= score <= 1.0

    def test_ambre(self, cpu_threshold):
        rag, score = _compute_rag(85.0, cpu_threshold)
        assert rag == "AMBRE"
        assert 0.60 <= score < 0.80

    def test_vert(self, cpu_threshold):
        rag, score = _compute_rag(50.0, cpu_threshold)
        assert rag == "VERT"
        assert 0.0 <= score < 0.60

    def test_exact_rouge_threshold(self, cpu_threshold):
        rag, _ = _compute_rag(95.0, cpu_threshold)
        assert rag == "ROUGE"

    def test_exact_ambre_threshold(self, cpu_threshold):
        rag, _ = _compute_rag(80.0, cpu_threshold)
        assert rag == "AMBRE"


# ════════════════════════════════════════════════════════════
# TESTS FONCTIONS RAG — direction "below"
# ════════════════════════════════════════════════════════════

class TestComputeRAGBelow:
    """Tests _compute_rag avec direction='below'."""

    @pytest.fixture
    def dispo_threshold(self):
        return {"ambre": 98, "rouge": 95, "direction": "below"}

    def test_rouge(self, dispo_threshold):
        rag, score = _compute_rag(93.0, dispo_threshold)
        assert rag == "ROUGE"
        assert 0.80 <= score <= 1.0

    def test_ambre(self, dispo_threshold):
        rag, score = _compute_rag(96.5, dispo_threshold)
        assert rag == "AMBRE"
        assert 0.60 <= score < 0.80

    def test_vert(self, dispo_threshold):
        rag, score = _compute_rag(99.5, dispo_threshold)
        assert rag == "VERT"


# ════════════════════════════════════════════════════════════
# TESTS FONCTIONS RAG — direction "zscore"
# ════════════════════════════════════════════════════════════

class TestComputeRAGZscore:
    """Tests _compute_rag_zscore pour seuils dynamiques."""

    def test_rouge_high_z(self):
        rag, score = _compute_rag_zscore(z=3.5, ambre_sigma=2.0, rouge_sigma=3.0)
        assert rag == "ROUGE"
        assert 0.80 <= score <= 1.0

    def test_ambre_medium_z(self):
        rag, score = _compute_rag_zscore(z=2.5, ambre_sigma=2.0, rouge_sigma=3.0)
        assert rag == "AMBRE"
        assert 0.60 <= score < 0.80

    def test_vert_low_z(self):
        rag, score = _compute_rag_zscore(z=1.0, ambre_sigma=2.0, rouge_sigma=3.0)
        assert rag == "VERT"
        assert 0.0 <= score < 0.60

    def test_negative_z(self):
        """Z négatif → |Z| utilisé."""
        rag, _ = _compute_rag_zscore(z=-3.5, ambre_sigma=2.0, rouge_sigma=3.0)
        assert rag == "ROUGE"

    def test_zscore_direction_raises(self):
        """_compute_rag avec direction='zscore' doit lever ValueError."""
        with pytest.raises(ValueError, match="zscore"):
            _compute_rag(50, {"ambre": 2.0, "rouge": 3.0, "direction": "zscore"})


# ════════════════════════════════════════════════════════════
# TESTS SCORE_CONFIANCE RANGES
# ════════════════════════════════════════════════════════════

class TestScoreConfidenceRanges:
    """Vérifie que les scores respectent les plages RAG."""

    @pytest.mark.parametrize("value,expected_rag", [
        (96, "ROUGE"), (85, "AMBRE"), (50, "VERT"),
    ])
    def test_above_ranges(self, value, expected_rag):
        thr = {"ambre": 80, "rouge": 95, "direction": "above"}
        rag, score = _compute_rag(value, thr)
        assert rag == expected_rag
        if rag == "ROUGE":
            assert 0.80 <= score <= 1.0
        elif rag == "AMBRE":
            assert 0.60 <= score < 0.80
        else:
            assert 0.0 <= score < 0.60


# ════════════════════════════════════════════════════════════
# TESTS DÉTECTION Z-SCORE PAR DOMAINE
# ════════════════════════════════════════════════════════════

class TestZScoreDetection:
    """Vérifie la détection Z-Score sur données synthétiques."""

    def test_detect_infra(self, silver_infra):
        """Détection sur infrastructure avec données mockées."""
        detector = ZScoreDetector(engine=None)

        with patch.object(detector, "_load_silver", return_value=silver_infra):
            result = detector._detect_domain("infra")

        assert not result.empty
        assert "Domaine" in result.columns
        assert (result["Domaine"] == "Infrastructure").all()
        assert "Statut_RAG" in result.columns

    def test_detect_itsm(self, silver_itsm):
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_itsm):
            result = detector._detect_domain("itsm")
        assert not result.empty
        assert (result["Domaine"] == "ITSM").all()

    def test_detect_cyber(self, silver_cyber):
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_cyber):
            result = detector._detect_domain("cybersec")
        assert not result.empty

    def test_run_all_covers_all_domains(
        self, silver_infra, silver_itsm, silver_cyber, silver_apps,
        silver_itam, silver_parc_auto, silver_maintenance, silver_gouvernance,
    ):
        """run_all() doit couvrir les 8 domaines Silver."""
        detector = ZScoreDetector(engine=None)

        silver_map = {
            "infra": silver_infra, "itsm": silver_itsm,
            "cybersec": silver_cyber, "apps": silver_apps,
            "itam": silver_itam, "parc_auto": silver_parc_auto,
            "maintenance": silver_maintenance, "gouvernance": silver_gouvernance,
        }

        def mock_load(domain_key):
            return silver_map.get(domain_key, pd.DataFrame())

        with patch.object(detector, "_load_silver", side_effect=mock_load):
            results = detector.run_all()

        # Vérifier que chaque domaine a été traité
        assert len(results) == len(SILVER_TABLES)
        non_empty = sum(1 for df in results.values() if not df.empty)
        assert non_empty >= 6, f"Au moins 6 domaines doivent avoir des résultats, trouvé {non_empty}"


# ════════════════════════════════════════════════════════════
# TESTS COLONNES GOLD
# ════════════════════════════════════════════════════════════

class TestZScoreGoldSchema:
    """Vérifie que les colonnes de sortie correspondent au schéma Gold."""

    EXPECTED_COLS = {
        "DateKey", "Domaine", "GroupKey", "Score_IF",
        "Score_Confiance", "Statut_RAG", "Features_Utilisees",
        "Source_Detecteur", "Date_Calcul",
    }

    def test_output_columns(self, silver_infra):
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_infra):
            result = detector._detect_domain("infra")

        actual_cols = set(result.columns)
        missing = self.EXPECTED_COLS - actual_cols
        assert not missing, f"Colonnes Gold manquantes : {missing}"

    def test_score_if_is_nan(self, silver_infra):
        """Score_IF doit être NaN (réservé à Isolation Forest)."""
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_infra):
            result = detector._detect_domain("infra")
        assert result["Score_IF"].isna().all()

    def test_source_detecteur(self, silver_infra):
        """Source_Detecteur doit valoir 'ZScore' partout."""
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_infra):
            result = detector._detect_domain("infra")
        assert (result["Source_Detecteur"] == "ZScore").all()


# ════════════════════════════════════════════════════════════
# TESTS ANOMALIES INJECTÉES
# ════════════════════════════════════════════════════════════

class TestZScoreInjectedAnomalies:
    """Vérifie que les anomalies injectées dans les fixtures sont détectées."""

    def test_high_cpu_detected(self, silver_infra):
        """CPU > 95 (seuil rouge) doit générer des anomalies ROUGE."""
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_infra):
            result = detector._detect_domain("infra")

        cpu_results = result[result["Features_Utilisees"] == "CPU_Moyen_Pct"]
        rouge = cpu_results[cpu_results["Statut_RAG"] == "ROUGE"]
        assert len(rouge) > 0, "Aucun CPU > 95% détecté en ROUGE"

    def test_itsm_crisis_detected(self, silver_itsm):
        """Jours de crise ITSM (MTTR > 24h) doivent être détectés."""
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_itsm):
            result = detector._detect_domain("itsm")

        mttr_results = result[result["Features_Utilisees"] == "MTTR_Moyen_Hours"]
        rouge = mttr_results[mttr_results["Statut_RAG"] == "ROUGE"]
        assert len(rouge) > 0, "Aucune crise MTTR > 24h détectée en ROUGE"


# ════════════════════════════════════════════════════════════
# TESTS SAUVEGARDE
# ════════════════════════════════════════════════════════════

class TestZScoreSave:
    """Vérifie le mode dry_run et le résumé."""

    def test_save_dry_run(self, silver_infra):
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_infra):
            results = {"infra": detector._detect_domain("infra")}

        nb = detector.save_results(results, dry_run=True)
        assert nb >= 0  # dry_run retourne un count sans écrire

    def test_summary_table(self, silver_infra):
        detector = ZScoreDetector(engine=None)
        with patch.object(detector, "_load_silver", return_value=silver_infra):
            results = {"infra": detector._detect_domain("infra")}

        summary_df = detector.summary(results)
        assert not summary_df.empty
        assert "Domaine" in summary_df.columns
        assert "Nb_ROUGE" in summary_df.columns


# ════════════════════════════════════════════════════════════
# TESTS CONSTANTES
# ════════════════════════════════════════════════════════════

class TestZScoreConstants:
    """Vérifie la cohérence des constantes."""

    def test_thresholds_cover_all_domains(self):
        expected = {
            "Infrastructure", "ITSM", "Cybersécurité", "Applications",
            "ITAM", "Parc_Auto", "Maintenance", "Gouvernance",
        }
        actual = set(ZSCORE_THRESHOLDS.keys())
        assert actual == expected

    def test_silver_tables_count(self):
        assert len(SILVER_TABLES) == 8

    def test_domain_labels_consistent(self):
        for key in SILVER_TABLES:
            assert key in DOMAIN_LABELS, f"Clé '{key}' manque dans DOMAIN_LABELS"


# ── Exécution directe ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
