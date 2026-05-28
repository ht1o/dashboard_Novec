"""
test_prophet.py — Tests unitaires Prophet Forecaster
Dashboard 360° Novec | Tests offline (sans SQL Server)

Valide : prédictions par domaine, RAG status, is_forecast flag,
clamp pourcentages, alert summary, run_all().

Note : Prophet est lent — on utilise des séries courtes (60 jours)
pour garder les tests rapides (< 30s total).

Usage : pytest tests/test_prophet.py -v
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from ml.forecasting.prophet_forecaster import (
    ProphetForecaster,
    ForecastConfig,
    FORECAST_CONFIGS,
    SILVER_TABLES,
    _rag_status,
    _normalize_score,
)


# ════════════════════════════════════════════════════════════
# FIXTURES LOCALES (séries courtes pour vitesse)
# ════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def short_itsm():
    """60 jours ITSM — série courte pour Prophet."""
    np.random.seed(50)
    dates = pd.date_range("2025-06-01", periods=60, freq="D")
    return pd.DataFrame({
        "DateKey": dates,
        "Volume_Total": np.clip(np.random.normal(50, 15, 60), 5, None).astype(int),
        "Backlog_Total": np.clip(np.random.normal(20, 8, 60), 0, None).astype(int),
        "MTTR_Moyen_Hours": np.clip(np.random.normal(6, 3, 60), 0.5, None),
        "SLA_Moyen_Pct": np.clip(np.random.normal(95, 3, 60), 70, 100),
        "CSAT_Moyen": np.clip(np.random.normal(4.0, 0.5, 60), 1, 5),
        "Pct_Tickets_P1": np.clip(np.random.normal(5, 3, 60), 0, 30),
        "FCR_Moyen_Pct": np.clip(np.random.normal(70, 10, 60), 30, 100),
    })


@pytest.fixture(scope="module")
def short_infra():
    """60 jours × 1 serveur — série courte pour Prophet."""
    np.random.seed(51)
    dates = pd.date_range("2025-06-01", periods=60, freq="D")
    return pd.DataFrame({
        "DateKey": dates,
        "ServerName": "SRV-TEST-01",
        "CPU_Moyen_Pct": np.clip(np.random.normal(45, 15, 60), 0, 100),
        "RAM_Moyen_Pct": np.clip(np.random.normal(55, 12, 60), 0, 100),
        "Disk_Moyen_Pct": np.clip(np.random.normal(50, 10, 60), 0, 100),
        "Latence_Moyenne_ms": np.clip(np.random.normal(30, 15, 60), 0, None),
        "Disponibilite_Pct": np.clip(np.random.normal(99.5, 0.5, 60), 90, 100),
    })


# ════════════════════════════════════════════════════════════
# TESTS INITIALISATION
# ════════════════════════════════════════════════════════════

class TestProphetInit:

    def test_init_without_engine(self):
        forecaster = ProphetForecaster(engine=None)
        assert forecaster.engine is None

    def test_configs_defined(self):
        """Au moins 10 configurations Prophet doivent être définies."""
        assert len(FORECAST_CONFIGS) >= 10

    def test_silver_tables_defined(self):
        expected_keys = {"infra", "itsm", "cybersec", "itam", "apps", "gouvernance"}
        assert set(SILVER_TABLES.keys()) == expected_keys


# ════════════════════════════════════════════════════════════
# TESTS FONCTIONS UTILITAIRES
# ════════════════════════════════════════════════════════════

class TestProphetUtils:

    def test_rag_status_above_rouge(self):
        cfg = ForecastConfig(alert_threshold=80.0, alert_direction="above")
        row = pd.Series({"yhat": 85, "yhat_upper": 90, "yhat_lower": 80})
        assert _rag_status(row, cfg) == "ROUGE"

    def test_rag_status_above_ambre(self):
        cfg = ForecastConfig(alert_threshold=80.0, alert_direction="above")
        row = pd.Series({"yhat": 75, "yhat_upper": 82, "yhat_lower": 68})
        assert _rag_status(row, cfg) == "AMBRE"

    def test_rag_status_above_vert(self):
        cfg = ForecastConfig(alert_threshold=80.0, alert_direction="above")
        row = pd.Series({"yhat": 50, "yhat_upper": 60, "yhat_lower": 40})
        assert _rag_status(row, cfg) == "VERT"

    def test_rag_status_below_rouge(self):
        cfg = ForecastConfig(alert_threshold=95.0, alert_direction="below")
        row = pd.Series({"yhat": 90, "yhat_upper": 93, "yhat_lower": 87})
        assert _rag_status(row, cfg) == "ROUGE"

    def test_rag_status_no_threshold(self):
        cfg = ForecastConfig(alert_threshold=None)
        row = pd.Series({"yhat": 50, "yhat_upper": 60, "yhat_lower": 40})
        assert _rag_status(row, cfg) == "VERT"

    def test_normalize_score_range(self):
        score = _normalize_score(85, 80, 90, 80.0, "above")
        assert 0.0 <= score <= 1.0

    def test_normalize_score_no_threshold(self):
        score = _normalize_score(50, 40, 60, None, "above")
        assert score == 0.0


# ════════════════════════════════════════════════════════════
# TESTS PRÉDICTION
# ════════════════════════════════════════════════════════════

class TestProphetForecast:

    def test_forecast_itsm(self, short_itsm):
        """Prédiction ITSM Volume_Total."""
        forecaster = ProphetForecaster(engine=None)
        with patch.object(forecaster, "_load", return_value=short_itsm):
            result = forecaster.forecast_itsm()

        assert not result.empty
        assert "kpi" in result.columns
        assert "ds" in result.columns
        assert "yhat" in result.columns
        assert "is_forecast" in result.columns

    def test_is_forecast_flag(self, short_itsm):
        """Historique = False, futur = True."""
        forecaster = ProphetForecaster(engine=None)
        with patch.object(forecaster, "_load", return_value=short_itsm):
            result = forecaster.forecast_itsm()

        if not result.empty:
            hist = result[~result["is_forecast"]]
            future = result[result["is_forecast"]]
            assert len(hist) > 0, "Pas de données historiques"
            assert len(future) > 0, "Pas de prédictions futures"

    def test_forecast_infrastructure_per_server(self, short_infra):
        """Prédiction infra groupée par serveur."""
        forecaster = ProphetForecaster(engine=None)
        with patch.object(forecaster, "_load", return_value=short_infra):
            result = forecaster.forecast_infrastructure()

        if not result.empty:
            assert "server_name" in result.columns
            assert "kpi" in result.columns

    def test_rag_column_present(self, short_itsm):
        forecaster = ProphetForecaster(engine=None)
        with patch.object(forecaster, "_load", return_value=short_itsm):
            result = forecaster.forecast_itsm()

        assert "rag_status" in result.columns
        valid_rag = {"ROUGE", "AMBRE", "VERT"}
        actual_rag = set(result["rag_status"].unique())
        assert actual_rag.issubset(valid_rag), f"RAG invalides : {actual_rag - valid_rag}"


# ════════════════════════════════════════════════════════════
# TESTS ALERT SUMMARY
# ════════════════════════════════════════════════════════════

class TestProphetAlerts:

    def test_build_alert_summary_empty(self):
        forecasts = {"itsm": pd.DataFrame()}
        result = ProphetForecaster.build_alert_summary(forecasts)
        assert result.empty

    def test_build_alert_summary_filters_future_only(self):
        """Seules les prédictions futures AMBRE/ROUGE sont retenues."""
        df = pd.DataFrame({
            "ds": pd.date_range("2025-06-01", periods=5),
            "kpi": "Volume_Total",
            "domain": "ITSM",
            "yhat": [50, 55, 60, 120, 130],
            "yhat_lower": [40, 45, 50, 100, 110],
            "yhat_upper": [60, 65, 70, 140, 150],
            "rag_status": ["VERT", "VERT", "VERT", "AMBRE", "ROUGE"],
            "risk_score": [0.1, 0.2, 0.3, 0.6, 0.9],
            "is_forecast": [False, False, True, True, True],
        })
        result = ProphetForecaster.build_alert_summary({"itsm": df})
        assert len(result) >= 1
        assert "VERT" not in result["rag_status"].values


# ════════════════════════════════════════════════════════════
# TESTS RUN_ALL
# ════════════════════════════════════════════════════════════

class TestProphetRunAll:

    def test_run_all_returns_dict(self, short_itsm, short_infra):
        forecaster = ProphetForecaster(engine=None)

        def mock_load(domain, date_col="DateKey"):
            if domain == "itsm":
                return short_itsm
            elif domain == "infra":
                return short_infra
            else:
                return pd.DataFrame({"DateKey": pd.date_range("2025-01-01", periods=5)})

        with patch.object(forecaster, "_load", side_effect=mock_load):
            results = forecaster.run_all()

        assert isinstance(results, dict)
        assert "alerts" in results
        expected_keys = {"infra", "itsm", "cybersec", "itam", "apps", "gouvernance", "alerts"}
        assert set(results.keys()) == expected_keys


# ── Exécution directe ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
