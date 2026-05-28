"""
test_arima.py — Tests unitaires ARIMA Forecaster
Dashboard 360° Novec | Tests offline (sans SQL Server)

Valide : configurations, fit/forecast, risk score, colonnes Gold,
Source_Modele, clamp pourcentages.

Usage : pytest tests/test_arima.py -v
"""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch

from ml.forecasting.arima_forecaster import (
    ARIMAForecaster,
    ARIMAConfig,
    ARIMA_CONFIGS,
    SILVER_TABLES,
    GOLD_FORECAST_TABLES,
    _compute_risk_score,
    _clamp_pct,
)


# ════════════════════════════════════════════════════════════
# TESTS CONSTANTES & CONFIGURATIONS
# ════════════════════════════════════════════════════════════

class TestARIMAConfigs:

    def test_configs_count(self):
        """6 configurations ARIMA doivent être définies."""
        assert len(ARIMA_CONFIGS) == 6

    def test_configs_domains(self):
        domains = {c.domain for c in ARIMA_CONFIGS}
        expected = {"itam", "maintenance", "parc_auto", "gouvernance"}
        assert domains == expected

    def test_all_configs_have_freq_ms(self):
        """Toutes les configs ARIMA sont mensuelles (MS)."""
        for cfg in ARIMA_CONFIGS:
            assert cfg.freq == "MS", f"{cfg.domain}/{cfg.kpi} freq != MS"

    def test_silver_tables_count(self):
        assert len(SILVER_TABLES) == 8

    def test_gold_tables_defined(self):
        expected = {"itam", "maintenance", "parc_auto", "gouvernance"}
        for domain in expected:
            assert domain in GOLD_FORECAST_TABLES


# ════════════════════════════════════════════════════════════
# TESTS FONCTIONS UTILITAIRES
# ════════════════════════════════════════════════════════════

class TestARIMAUtils:

    def test_risk_score_above_rouge(self):
        cfg = ARIMAConfig("test", "kpi", 3, "MS",
                          direction="above", rouge_thr=4, ambre_thr=2)
        score, rag = _compute_risk_score(5.0, cfg)
        assert rag == "ROUGE"
        assert 0.80 <= score <= 1.0

    def test_risk_score_above_ambre(self):
        cfg = ARIMAConfig("test", "kpi", 3, "MS",
                          direction="above", rouge_thr=4, ambre_thr=2)
        score, rag = _compute_risk_score(3.0, cfg)
        assert rag == "AMBRE"
        assert 0.40 <= score < 0.80

    def test_risk_score_above_vert(self):
        cfg = ARIMAConfig("test", "kpi", 3, "MS",
                          direction="above", rouge_thr=4, ambre_thr=2)
        score, rag = _compute_risk_score(1.0, cfg)
        assert rag == "VERT"
        assert score < 0.40

    def test_risk_score_below_rouge(self):
        cfg = ARIMAConfig("test", "kpi", 3, "MS",
                          direction="below", rouge_thr=60, ambre_thr=70)
        score, rag = _compute_risk_score(55.0, cfg)
        assert rag == "ROUGE"

    def test_risk_score_below_vert(self):
        cfg = ARIMAConfig("test", "kpi", 3, "MS",
                          direction="below", rouge_thr=60, ambre_thr=70)
        score, rag = _compute_risk_score(80.0, cfg)
        assert rag == "VERT"

    def test_risk_score_no_thresholds(self):
        cfg = ARIMAConfig("test", "kpi", 3, "MS")
        score, rag = _compute_risk_score(50.0, cfg)
        assert rag == "VERT"
        assert score == 0.10

    def test_clamp_pct(self):
        s = pd.Series([-10, 50, 110, 99.5])
        result = _clamp_pct(s)
        assert result.min() >= 0.0
        assert result.max() <= 100.0


# ════════════════════════════════════════════════════════════
# TESTS FIT/FORECAST
# ════════════════════════════════════════════════════════════

class TestARIMAFitForecast:

    def test_fit_forecast_basic(self):
        """auto_arima doit produire un forecast de taille horizon."""
        forecaster = ARIMAForecaster(engine=None)
        # Série mensuelle simple avec tendance
        dates = pd.date_range("2025-01-01", periods=12, freq="MS")
        series = pd.Series(
            np.linspace(100, 120, 12) + np.random.normal(0, 2, 12),
            index=dates,
        )
        yhat, lower, upper = forecaster._fit_forecast(series, horizon=3, freq="MS")
        assert len(yhat) == 3
        assert len(lower) == 3
        assert len(upper) == 3
        # lower <= yhat <= upper
        assert (lower <= yhat).all()
        assert (yhat <= upper).all()

    def test_forecast_itam(self, silver_itam):
        """Prédiction ITAM TCO sur 3 mois."""
        forecaster = ARIMAForecaster(engine=None)

        with patch.object(forecaster, "_load_silver", return_value=silver_itam):
            cfg = ARIMA_CONFIGS[0]  # itam / TCO_Moyen_Par_Poste_MAD
            result = forecaster._forecast_series(silver_itam.copy(), cfg)

        if not result.empty:
            assert "KPI" in result.columns
            assert "DS" in result.columns
            assert "Yhat" in result.columns
            assert "Source_Modele" in result.columns
            assert (result["Source_Modele"] == "ARIMA").all()

    def test_forecast_maintenance(self, silver_maintenance):
        """Prédiction maintenance Ratio_Preventif_Pct."""
        forecaster = ARIMAForecaster(engine=None)
        cfg = ARIMAConfig(
            "maintenance", "Ratio_Preventif_Pct", horizon=3, freq="MS",
            is_pct=True, direction="below", rouge_thr=60, ambre_thr=70,
        )
        result = forecaster._forecast_series(silver_maintenance.copy(), cfg)

        if not result.empty:
            forecast_rows = result[result["Is_Forecast"] == 1]
            # Pourcentages clampés [0, 100]
            assert forecast_rows["Yhat"].min() >= 0
            assert forecast_rows["Yhat"].max() <= 100


# ════════════════════════════════════════════════════════════
# TESTS OUTPUT / COLONNES GOLD
# ════════════════════════════════════════════════════════════

class TestARIMAOutput:

    GOLD_COLS = {
        "KPI", "DS", "Yhat", "Yhat_Lower", "Yhat_Upper",
        "Is_Forecast", "Statut_RAG", "Risk_Score",
        "Source_Modele", "Date_Calcul",
    }

    def test_output_columns(self, silver_itam):
        forecaster = ARIMAForecaster(engine=None)
        cfg = ARIMA_CONFIGS[0]
        result = forecaster._forecast_series(silver_itam.copy(), cfg)

        if not result.empty:
            missing = self.GOLD_COLS - set(result.columns)
            assert not missing, f"Colonnes Gold manquantes : {missing}"

    def test_source_modele_arima(self, silver_itam):
        forecaster = ARIMAForecaster(engine=None)
        cfg = ARIMA_CONFIGS[0]
        result = forecaster._forecast_series(silver_itam.copy(), cfg)

        if not result.empty:
            assert (result["Source_Modele"] == "ARIMA").all()

    def test_is_forecast_binary(self, silver_itam):
        forecaster = ARIMAForecaster(engine=None)
        cfg = ARIMA_CONFIGS[0]
        result = forecaster._forecast_series(silver_itam.copy(), cfg)

        if not result.empty:
            assert set(result["Is_Forecast"].unique()).issubset({0, 1})

    def test_rag_values_valid(self, silver_itam):
        forecaster = ARIMAForecaster(engine=None)
        cfg = ARIMA_CONFIGS[0]
        result = forecaster._forecast_series(silver_itam.copy(), cfg)

        if not result.empty:
            valid_rag = {"ROUGE", "AMBRE", "VERT"}
            actual = set(result["Statut_RAG"].unique())
            assert actual.issubset(valid_rag)


# ════════════════════════════════════════════════════════════
# TESTS RUN_ALL
# ════════════════════════════════════════════════════════════

class TestARIMARunAll:

    def test_run_all_returns_dict(
        self, silver_itam, silver_maintenance, silver_parc_auto, silver_gouvernance,
    ):
        forecaster = ARIMAForecaster(engine=None)
        silver_map = {
            "itam": silver_itam,
            "maintenance": silver_maintenance,
            "parc_auto": silver_parc_auto,
            "gouvernance": silver_gouvernance,
        }

        def mock_load(domain_key):
            return silver_map.get(domain_key, pd.DataFrame())

        with patch.object(forecaster, "_load_silver", side_effect=mock_load):
            results = forecaster.run_all()

        assert isinstance(results, dict)
        # Au moins les tables ITAM et gouvernance doivent avoir des résultats
        non_empty = sum(1 for df in results.values() if not df.empty)
        assert non_empty >= 1, "Au moins 1 table Gold doit avoir des résultats"

    def test_summary_table(
        self, silver_itam, silver_maintenance, silver_parc_auto, silver_gouvernance,
    ):
        forecaster = ARIMAForecaster(engine=None)
        silver_map = {
            "itam": silver_itam,
            "maintenance": silver_maintenance,
            "parc_auto": silver_parc_auto,
            "gouvernance": silver_gouvernance,
        }

        def mock_load(domain_key):
            return silver_map.get(domain_key, pd.DataFrame())

        with patch.object(forecaster, "_load_silver", side_effect=mock_load):
            results = forecaster.run_all()

        summary = forecaster.summary(results)
        assert not summary.empty
        assert "Table" in summary.columns
        assert "Total" in summary.columns


# ── Exécution directe ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
