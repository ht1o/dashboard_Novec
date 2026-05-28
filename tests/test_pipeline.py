"""
test_pipeline.py — Tests offline du pipeline ML orchestrateur
Dashboard 360° Novec | Tests offline (sans SQL Server)

Valide : RunSummary, import des modules, pipeline dry_run+csv,
gestion d'erreurs partielles, flag skip_scoring.

Usage : pytest tests/test_pipeline.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from ml.pipeline import (
    RunSummary,
    run_pipeline,
    task_isolation_forest,
    task_zscore,
    task_prophet,
    task_arima,
    task_risk_score,
)


# ════════════════════════════════════════════════════════════
# TESTS RUNSUMMARY
# ════════════════════════════════════════════════════════════

class TestRunSummary:

    def test_init(self):
        s = RunSummary("test-001")
        assert s.run_id == "test-001"
        assert s.status == "running"
        assert s.started_at is not None
        assert s.finished_at is None

    def test_finalize(self):
        s = RunSummary("test-002")
        s.finalize(status="success")
        assert s.status == "success"
        assert s.finished_at is not None
        assert s.duration_seconds is not None
        assert s.duration_seconds >= 0

    def test_to_dict(self):
        s = RunSummary("test-003")
        s.if_anomalies_detectees = 42
        s.zscore_alertes_generees = 15
        s.prophet_predictions = 100
        s.arima_predictions = 30
        s.risk_score_global = 55.5
        s.risk_score_rag = "AMBRE"
        s.finalize()

        d = s.to_dict()
        assert d["Run_Id"] == "test-003"
        assert d["IF_Anomalies_Detectees"] == 42
        assert d["ZScore_Alertes_Generees"] == 15
        assert d["Prophet_Predictions"] == 100
        assert d["ARIMA_Predictions"] == 30
        assert d["Risk_Score_Global"] == 55.5
        assert d["Risk_Score_RAG"] == "AMBRE"
        assert d["Status"] == "success"

    def test_print_report_no_crash(self, capsys):
        s = RunSummary("test-004")
        s.risk_score_global = 35.0
        s.risk_score_rag = "VERT"
        s.step_errors.append("Test erreur")
        s.finalize(status="partial")

        s.print_report()  # ne doit pas crasher
        captured = capsys.readouterr()
        assert "PIPELINE ML" in captured.out
        assert "test-004" in captured.out

    def test_duration_none_before_finalize(self):
        s = RunSummary("test-005")
        assert s.duration_seconds is None


# ════════════════════════════════════════════════════════════
# TESTS IMPORT DES MODULES
# ════════════════════════════════════════════════════════════

class TestPipelineImports:
    """Vérifie que tous les modules ML sont importables."""

    def test_import_isolation_forest(self):
        from ml.anomaly_detection.isolation_forest_detector import IsolationForestDetector
        assert IsolationForestDetector is not None

    def test_import_zscore(self):
        from ml.anomaly_detection.zscore_detector import ZScoreDetector
        assert ZScoreDetector is not None

    def test_import_prophet(self):
        from ml.forecasting.prophet_forecaster import ProphetForecaster
        assert ProphetForecaster is not None

    def test_import_arima(self):
        from ml.forecasting.arima_forecaster import ARIMAForecaster
        assert ARIMAForecaster is not None

    def test_import_risk_score(self):
        from ml.scoring.it_risk_score import compute_it_risk_score
        assert compute_it_risk_score is not None


# ════════════════════════════════════════════════════════════
# TESTS PIPELINE DRY_RUN + CSV
# ════════════════════════════════════════════════════════════

class TestPipelineDryRun:

    def test_run_pipeline_dry_run_csv_no_crash(
        self, silver_infra, silver_itsm, silver_cyber, silver_apps,
        silver_itam, silver_parc_auto, silver_maintenance, silver_gouvernance,
    ):
        """
        Pipeline complet en dry_run + CSV mocké → ne doit pas crasher.
        C'est le test le plus important : prouve que la chaîne complète fonctionne.
        """
        # Mock load_from_csv pour IF
        mock_csv_data = {
            "infra": silver_infra,
            "itsm": silver_itsm,
            "cyber": silver_cyber,
            "apps": silver_apps,
        }

        silver_map = {
            "infra": silver_infra, "itsm": silver_itsm,
            "cybersec": silver_cyber, "apps": silver_apps,
            "itam": silver_itam, "parc_auto": silver_parc_auto,
            "maintenance": silver_maintenance, "gouvernance": silver_gouvernance,
        }

        with patch("ml.pipeline.load_from_csv", return_value=mock_csv_data), \
             patch("ml.pipeline.get_db_engine", return_value=None), \
             patch("ml.anomaly_detection.zscore_detector.ZScoreDetector._load_silver",
                   side_effect=lambda dk: silver_map.get(dk, __import__('pandas').DataFrame())), \
             patch("ml.forecasting.prophet_forecaster.ProphetForecaster._load",
                   side_effect=lambda domain, **kw: silver_map.get(domain, __import__('pandas').DataFrame())), \
             patch("ml.forecasting.arima_forecaster.ARIMAForecaster._load_silver",
                   side_effect=lambda dk: silver_map.get(dk, __import__('pandas').DataFrame())):

            summary = run_pipeline(use_csv=True, dry_run=True, skip_scoring=True)

        assert summary.status in ("success", "partial")
        assert summary.if_anomalies_detectees >= 0
        assert summary.zscore_alertes_generees >= 0

    def test_skip_scoring(self):
        """skip_scoring=True → étape 3 ignorée, pas de crash."""
        with patch("ml.pipeline.load_from_csv", return_value={
            "infra": __import__('pandas').DataFrame(),
            "itsm": __import__('pandas').DataFrame(),
            "cyber": __import__('pandas').DataFrame(),
            "apps": __import__('pandas').DataFrame(),
        }), \
             patch("ml.pipeline.get_db_engine", return_value=None):

            summary = run_pipeline(use_csv=True, dry_run=True, skip_scoring=True)

        assert summary.risk_score_global is None


# ════════════════════════════════════════════════════════════
# TESTS GESTION D'ERREURS
# ════════════════════════════════════════════════════════════

class TestPipelineErrorHandling:

    def test_partial_failure_records_errors(self):
        """Si une étape échoue, summary.step_errors le capture."""
        summary = RunSummary("err-test")

        # Simuler une erreur dans task_isolation_forest
        with patch("ml.pipeline.load_from_csv", side_effect=Exception("CSV manquant")):
            task_isolation_forest(None, True, True, summary)

        assert len(summary.step_errors) > 0
        assert "CSV manquant" in summary.step_errors[0]

    def test_risk_score_without_engine(self):
        """Risk Score sans engine → erreur capturée, pas de crash."""
        summary = RunSummary("no-engine")
        task_risk_score(None, dry_run=True, summary=summary)
        assert len(summary.step_errors) > 0 or summary.risk_score_global is None


# ── Exécution directe ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
