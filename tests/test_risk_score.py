"""
test_risk_score.py — Tests unitaires IT Risk Score
Dashboard 360° Novec | Tests offline (sans SQL Server)

Valide : composantes A/K/P, formule globale, pondérations domaines,
seuils RAG, top contributeurs, colonnes Gold.

Usage : pytest tests/test_risk_score.py -v
"""
import json
import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from ml.scoring.it_risk_score import (
    DOMAIN_WEIGHTS,
    W_ANOMALIES,
    W_KPI_ALERTS,
    W_PREDICTIONS,
    RAG_ROUGE_THRESHOLD,
    RAG_AMBRE_THRESHOLD,
    _score_anomalies,
    _score_kpi_alerts,
    _score_predictions,
    _compute_global_score,
    _rag_global,
    _top_contributors,
    compute_it_risk_score,
)


# ════════════════════════════════════════════════════════════
# TESTS CONSTANTES
# ════════════════════════════════════════════════════════════

class TestRiskScoreConstants:

    def test_domain_weights_sum_to_one(self):
        total = sum(DOMAIN_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Somme des poids = {total}, attendu 1.0"

    def test_component_weights_sum_to_one(self):
        total = W_ANOMALIES + W_KPI_ALERTS + W_PREDICTIONS
        assert abs(total - 1.0) < 1e-9

    def test_rag_thresholds_ordered(self):
        assert RAG_AMBRE_THRESHOLD < RAG_ROUGE_THRESHOLD

    def test_six_domains(self):
        assert len(DOMAIN_WEIGHTS) == 6
        expected = {"Infrastructure", "Cybersécurité", "ITSM",
                    "Applications", "ITAM", "Gouvernance"}
        assert set(DOMAIN_WEIGHTS.keys()) == expected


# ════════════════════════════════════════════════════════════
# TESTS COMPOSANTE A — ANOMALIES
# ════════════════════════════════════════════════════════════

class TestScoreAnomalies:

    def test_empty_anomalies(self):
        scores, nb, contribs = _score_anomalies(pd.DataFrame())
        assert all(v == 0.0 for v in scores.values())
        assert nb == 0
        assert contribs == []

    def test_rouge_anomalies_high_score(self):
        """Anomalies ROUGE → score domaine élevé."""
        df = pd.DataFrame({
            "Domaine": ["Infrastructure"] * 10,
            "Statut_RAG": ["ROUGE"] * 3 + ["AMBRE"] * 2 + ["VERT"] * 5,
            "Score_Confiance": [0.9] * 3 + [0.7] * 2 + [0.3] * 5,
        })
        scores, nb, contribs = _score_anomalies(df)
        assert scores["Infrastructure"] > 0
        assert nb == 5  # 3 ROUGE + 2 AMBRE

    def test_multiple_domains(self):
        df = pd.DataFrame({
            "Domaine": ["Infrastructure"] * 5 + ["ITSM"] * 5,
            "Statut_RAG": ["ROUGE"] * 2 + ["VERT"] * 3 + ["AMBRE"] * 3 + ["VERT"] * 2,
            "Score_Confiance": [0.9] * 2 + [0.2] * 3 + [0.7] * 3 + [0.2] * 2,
        })
        scores, nb, contribs = _score_anomalies(df)
        assert scores["Infrastructure"] > 0
        assert scores["ITSM"] > 0
        assert nb == 5  # 2 ROUGE + 3 AMBRE


# ════════════════════════════════════════════════════════════
# TESTS COMPOSANTE K — KPI ALERTS
# ════════════════════════════════════════════════════════════

class TestScoreKPIAlerts:

    def test_empty_alerts(self):
        scores, nb_rouge, contribs = _score_kpi_alerts(pd.DataFrame())
        assert all(v == 0.0 for v in scores.values())
        assert nb_rouge == 0

    def test_rouge_alerts(self):
        df = pd.DataFrame({
            "domain": ["Infrastructure", "Infrastructure", "ITSM"],
            "rag_status": ["ROUGE", "AMBRE", "ROUGE"],
            "risk_score": [0.9, 0.6, 0.85],
        })
        scores, nb_rouge, contribs = _score_kpi_alerts(df)
        assert scores["Infrastructure"] > 0
        assert scores["ITSM"] > 0
        assert nb_rouge == 2


# ════════════════════════════════════════════════════════════
# TESTS COMPOSANTE P — PRÉDICTIONS
# ════════════════════════════════════════════════════════════

class TestScorePredictions:

    def test_empty_predictions(self):
        scores, contribs = _score_predictions([])
        assert all(v == 0.0 for v in scores.values())
        assert contribs == []

    def test_rouge_predictions(self):
        rows = [
            {"domain": "Infrastructure", "kpi": "Disk_Moyen_Pct",
             "risk_score": 0.9, "statut_rag": "ROUGE"},
            {"domain": "ITSM", "kpi": "Backlog_Total",
             "risk_score": 0.6, "statut_rag": "AMBRE"},
        ]
        scores, contribs = _score_predictions(rows)
        assert scores["Infrastructure"] > 0
        assert scores["ITSM"] > 0


# ════════════════════════════════════════════════════════════
# TESTS SCORE GLOBAL
# ════════════════════════════════════════════════════════════

class TestGlobalScore:

    def test_all_zero(self):
        a = {d: 0.0 for d in DOMAIN_WEIGHTS}
        k = {d: 0.0 for d in DOMAIN_WEIGHTS}
        p = {d: 0.0 for d in DOMAIN_WEIGHTS}
        global_score, per_domain = _compute_global_score(a, k, p)
        assert global_score == 0.0
        assert all(v == 0.0 for v in per_domain.values())

    def test_formula_weights(self):
        """Score_Global = A×40% + K×35% + P×25% pondéré par domaine."""
        # Infrastructure = 100 partout
        a = {d: 0.0 for d in DOMAIN_WEIGHTS}
        k = {d: 0.0 for d in DOMAIN_WEIGHTS}
        p = {d: 0.0 for d in DOMAIN_WEIGHTS}
        a["Infrastructure"] = 100.0
        k["Infrastructure"] = 100.0
        p["Infrastructure"] = 100.0

        global_score, per_domain = _compute_global_score(a, k, p)
        # Infrastructure poids = 0.30, score domaine = 100 × (0.40+0.35+0.25) = 100
        # Global = 100 × 0.30 = 30.0
        assert abs(per_domain["Infrastructure"] - 100.0) < 0.1
        assert abs(global_score - 30.0) < 0.1

    def test_score_range(self):
        """Score global doit rester dans [0, 100]."""
        a = {d: 100.0 for d in DOMAIN_WEIGHTS}
        k = {d: 100.0 for d in DOMAIN_WEIGHTS}
        p = {d: 100.0 for d in DOMAIN_WEIGHTS}
        global_score, _ = _compute_global_score(a, k, p)
        assert 0 <= global_score <= 100


# ════════════════════════════════════════════════════════════
# TESTS RAG GLOBAL
# ════════════════════════════════════════════════════════════

class TestRAGGlobal:

    def test_rouge(self):
        assert _rag_global(75.0) == "ROUGE"
        assert _rag_global(70.0) == "ROUGE"

    def test_ambre(self):
        assert _rag_global(50.0) == "AMBRE"
        assert _rag_global(40.0) == "AMBRE"

    def test_vert(self):
        assert _rag_global(30.0) == "VERT"
        assert _rag_global(0.0) == "VERT"

    def test_boundary_rouge_ambre(self):
        assert _rag_global(70.0) == "ROUGE"
        assert _rag_global(69.9) == "AMBRE"

    def test_boundary_ambre_vert(self):
        assert _rag_global(40.0) == "AMBRE"
        assert _rag_global(39.9) == "VERT"


# ════════════════════════════════════════════════════════════
# TESTS TOP CONTRIBUTEURS
# ════════════════════════════════════════════════════════════

class TestTopContributors:

    def test_empty(self):
        result = _top_contributors([], [], [])
        assert result == []

    def test_top_3(self):
        a = [
            {"domaine": "Infrastructure", "source": "anomalies", "contribution": 18.5},
            {"domaine": "ITSM", "source": "anomalies", "contribution": 12.0},
        ]
        k = [
            {"domaine": "Cybersécurité", "source": "prophet_alerts", "contribution": 15.0},
            {"domaine": "Applications", "source": "prophet_alerts", "contribution": 5.0},
        ]
        p = []
        result = _top_contributors(a, k, p, n=3)
        assert len(result) == 3
        # Trié par contribution décroissante
        contribs = [r["contribution"] for r in result]
        assert contribs == sorted(contribs, reverse=True)

    def test_top_n_limit(self):
        contribs = [
            {"domaine": f"D{i}", "source": "test", "contribution": float(i)}
            for i in range(10)
        ]
        result = _top_contributors(contribs, [], [], n=3)
        assert len(result) == 3


# ════════════════════════════════════════════════════════════
# TESTS COMPUTE_IT_RISK_SCORE (mocké)
# ════════════════════════════════════════════════════════════

class TestComputeRiskScore:

    def test_dry_run_returns_dict(self):
        """compute_it_risk_score en dry_run retourne un dict sans écrire."""
        mock_engine = MagicMock()

        with patch("ml.scoring.it_risk_score._load_anomalies", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_prophet_alerts", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_forecast_alerts", return_value=[]):
            result = compute_it_risk_score(
                mock_engine, date_key=date(2025, 6, 15), dry_run=True,
            )

        assert isinstance(result, dict)
        assert "Score_Global" in result
        assert "Statut_RAG_Global" in result
        assert "DateKey" in result
        assert "Top_Contributeurs" in result

    def test_output_columns_gold(self):
        """Toutes les colonnes Gold.it_risk_score doivent être présentes."""
        mock_engine = MagicMock()
        expected_cols = {
            "DateKey", "Score_Infrastructure", "Score_ITSM", "Score_Cybersec",
            "Score_Applications", "Score_ITAM", "Score_Gouvernance",
            "Score_Global", "Statut_RAG_Global", "Top_Contributeurs",
            "Nb_Anomalies_IF", "Nb_Alertes_Rouge", "Nb_Alertes_Ambre",
            "Source_Pipeline", "Date_Calcul",
        }

        with patch("ml.scoring.it_risk_score._load_anomalies", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_prophet_alerts", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_forecast_alerts", return_value=[]):
            result = compute_it_risk_score(
                mock_engine, date_key=date(2025, 6, 15), dry_run=True,
            )

        missing = expected_cols - set(result.keys())
        assert not missing, f"Colonnes Gold manquantes : {missing}"

    def test_score_global_zero_when_no_data(self):
        """Sans données, Score_Global = 0 et RAG = VERT."""
        mock_engine = MagicMock()

        with patch("ml.scoring.it_risk_score._load_anomalies", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_prophet_alerts", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_forecast_alerts", return_value=[]):
            result = compute_it_risk_score(
                mock_engine, date_key=date(2025, 6, 15), dry_run=True,
            )

        assert result["Score_Global"] == 0.0
        assert result["Statut_RAG_Global"] == "VERT"

    def test_top_contributeurs_is_valid_json(self):
        mock_engine = MagicMock()

        with patch("ml.scoring.it_risk_score._load_anomalies", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_prophet_alerts", return_value=pd.DataFrame()), \
             patch("ml.scoring.it_risk_score._load_forecast_alerts", return_value=[]):
            result = compute_it_risk_score(
                mock_engine, date_key=date(2025, 6, 15), dry_run=True,
            )

        # Top_Contributeurs doit être du JSON valide
        parsed = json.loads(result["Top_Contributeurs"])
        assert isinstance(parsed, list)


# ── Exécution directe ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
