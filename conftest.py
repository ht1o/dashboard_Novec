"""
conftest.py — Fixtures pytest partagées
Dashboard 360° Novec | Tests ML offline

Génère des données Silver synthétiques en mémoire pour tester
les moteurs ML sans dépendance à SQL Server.

Chaque fixture injecte des anomalies connues (valeurs extrêmes)
pour que les tests puissent valider la détection.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest
from prefect.testing.utilities import prefect_test_harness

@pytest.fixture(autouse=True, scope="session")
def prefect_test_fixture():
    with prefect_test_harness():
        yield

# ── Path setup ────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "data_simulation"))


# ── Marqueurs pytest ──────────────────────────────────────────
def pytest_configure(config):
    config.addinivalue_line("markers", "online: tests nécessitant SQL Server")


# ── Helpers ───────────────────────────────────────────────────
def _daily_dates(n=365, start="2025-04-01"):
    return pd.date_range(start, periods=n, freq="D")


def _monthly_dates(n=12, start="2025-04-01"):
    return pd.date_range(start, periods=n, freq="MS")


# ════════════════════════════════════════════════════════════
# FIXTURES SILVER — Données synthétiques
# ════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def silver_infra():
    """365 jours × 3 serveurs — données infrastructure avec anomalies."""
    np.random.seed(42)
    dates = _daily_dates(365)
    servers = ["SRV-ERP-01", "SRV-WEB-01", "SRV-DB-01"]
    rows = []
    for srv in servers:
        for d in dates:
            rows.append({
                "DateKey": d,
                "ServerName": srv,
                "CPU_Moyen_Pct": np.clip(np.random.normal(45, 15), 0, 100),
                "CPU_Max_Pct": np.clip(np.random.normal(60, 20), 0, 100),
                "RAM_Moyen_Pct": np.clip(np.random.normal(55, 12), 0, 100),
                "Disk_Moyen_Pct": np.clip(np.random.normal(50, 10), 0, 100),
                "Disk_Max_Pct": np.clip(np.random.normal(60, 12), 0, 100),
                "Latence_Moyenne_ms": max(0, np.random.normal(30, 15)),
                "Disponibilite_Pct": np.clip(np.random.normal(99.5, 0.5), 90, 100),
                "Nb_Anomalies": 0,
                "Taux_Anomalie_Pct": 0.0,
            })
    df = pd.DataFrame(rows)
    # Injecter ~30 anomalies (CPU + RAM + Latence extrêmes)
    idx = np.random.choice(len(df), size=30, replace=False)
    df.loc[idx, "CPU_Moyen_Pct"] = np.random.uniform(92, 100, 30)
    df.loc[idx, "RAM_Moyen_Pct"] = np.random.uniform(90, 99, 30)
    df.loc[idx, "Latence_Moyenne_ms"] = np.random.uniform(250, 500, 30)
    return df


@pytest.fixture(scope="session")
def silver_itsm():
    """365 jours — KPIs service desk."""
    np.random.seed(43)
    dates = _daily_dates(365)
    df = pd.DataFrame({
        "DateKey": dates,
        "Volume_Total": np.clip(np.random.normal(50, 15, 365), 5, None).astype(int),
        "Backlog_Total": np.clip(np.random.normal(20, 8, 365), 0, None).astype(int),
        "MTTR_Moyen_Hours": np.clip(np.random.normal(6, 3, 365), 0.5, None),
        "SLA_Moyen_Pct": np.clip(np.random.normal(95, 3, 365), 70, 100),
        "CSAT_Moyen": np.clip(np.random.normal(4.0, 0.5, 365), 1, 5),
        "Pct_Tickets_P1": np.clip(np.random.normal(5, 3, 365), 0, 30),
        "FCR_Moyen_Pct": np.clip(np.random.normal(70, 10, 365), 30, 100),
    })
    # Injecter 10 jours de crise ITSM
    idx = np.random.choice(365, size=10, replace=False)
    df.loc[idx, "Volume_Total"] = np.random.randint(120, 200, 10)
    df.loc[idx, "Backlog_Total"] = np.random.randint(55, 80, 10)
    df.loc[idx, "MTTR_Moyen_Hours"] = np.random.uniform(25, 40, 10)
    return df


@pytest.fixture(scope="session")
def silver_cyber():
    """365 jours — KPIs cybersécurité."""
    np.random.seed(44)
    dates = _daily_dates(365)
    df = pd.DataFrame({
        "DateKey": dates,
        "Nb_Incidents_Critiques": np.random.poisson(0.3, 365),
        "MTTD_Moyen_Hours": np.clip(np.random.normal(0.5, 0.3, 365), 0.1, None),
        "Total_Vuln_Non_Patchees": np.random.poisson(3, 365),
        "MFA_Adoption_Pct": np.clip(np.random.normal(92, 3, 365), 70, 100),
        "RGPD_Conformite_Pct": np.clip(np.random.normal(94, 3, 365), 70, 100),
        "Taux_Phishing_Moyen_Pct": np.clip(np.random.normal(8, 4, 365), 0, 50),
        "Systemes_Patches_Moyen_Pct": np.clip(np.random.normal(93, 3, 365), 70, 100),
    })
    # Injecter 8 jours de brèche
    idx = np.random.choice(365, size=8, replace=False)
    df.loc[idx, "Nb_Incidents_Critiques"] = np.random.randint(4, 8, 8)
    df.loc[idx, "MTTD_Moyen_Hours"] = np.random.uniform(5, 10, 8)
    df.loc[idx, "Total_Vuln_Non_Patchees"] = np.random.randint(16, 30, 8)
    return df


@pytest.fixture(scope="session")
def silver_apps():
    """365 jours × 3 applications — KPIs applicatifs."""
    np.random.seed(45)
    dates = _daily_dates(365)
    apps = ["App_SIRH", "App_Compta", "App_Core_Metier"]
    rows = []
    for app in apps:
        for d in dates:
            rows.append({
                "DateKey": d,
                "Application_Name": app,
                "Temps_Reponse_Moyen_ms": max(10, np.random.normal(120, 40)),
                "Nb_Bugs_Critiques": max(0, int(np.random.normal(0.3, 0.5))),
                "Disponibilite_Pct": np.clip(np.random.normal(99.8, 0.3), 95, 100),
                "Adoption_PowerBI_Pct": np.clip(np.random.normal(65, 10), 20, 100),
                "Qualite_Donnees_Pct": np.clip(np.random.normal(93, 3), 70, 100),
            })
    df = pd.DataFrame(rows)
    # Injecter anomalies applicatives
    idx = np.random.choice(len(df), size=15, replace=False)
    df.loc[idx, "Temps_Reponse_Moyen_ms"] = np.random.uniform(310, 600, 15)
    df.loc[idx, "Nb_Bugs_Critiques"] = np.random.randint(4, 8, 15)
    return df


@pytest.fixture(scope="session")
def silver_itam():
    """12 mois — KPIs actifs IT."""
    np.random.seed(46)
    dates = _monthly_dates(12)
    df = pd.DataFrame({
        "DateKey": dates,
        "Vetuste_Moyen_Pct": np.clip(np.random.normal(25, 8, 12), 5, 60),
        "CMDB_Couverture_Pct": np.clip(np.random.normal(88, 5, 12), 60, 100),
        "TCO_Moyen_Par_Poste_MAD": np.random.normal(8500, 1200, 12),
        "Conformite_Licences_Pct": np.clip(np.random.normal(90, 5, 12), 60, 100),
        "Total_Postes": np.random.randint(400, 500, 12),
        "TCO_Total_MAD": np.random.normal(3500000, 300000, 12),
    })
    return df


@pytest.fixture(scope="session")
def silver_parc_auto():
    """365 jours — KPIs flotte véhicules."""
    np.random.seed(47)
    dates = _daily_dates(365)
    df = pd.DataFrame({
        "DateKey": dates,
        "Disponibilite_Pct": np.clip(np.random.normal(95, 2, 365), 80, 100),
        "Nb_Sinistres": np.random.poisson(0.2, 365),
        "Taux_Sinistralite_Pct": np.clip(np.random.normal(2, 1.5, 365), 0, 15),
    })
    return df


@pytest.fixture(scope="session")
def silver_maintenance():
    """12 mois — KPIs maintenance."""
    np.random.seed(48)
    dates = _monthly_dates(12)
    df = pd.DataFrame({
        "DateKey": dates,
        "Ratio_Preventif_Pct": np.clip(np.random.normal(75, 8, 12), 40, 100),
        "Total_Ruptures_Stock": np.random.poisson(1.5, 12),
        "Pct_Preventif_Realise": np.clip(np.random.normal(80, 10, 12), 40, 100),
    })
    return df


@pytest.fixture(scope="session")
def silver_gouvernance():
    """12 mois × 4 départements — KPIs gouvernance."""
    np.random.seed(49)
    dates = _monthly_dates(12)
    depts = ["DSI", "Finance", "RH", "Operations"]
    rows = []
    for dept in depts:
        for d in dates:
            rows.append({
                "DateKey": d,
                "Departement": dept,
                "Ecart_Budget_Moyen_Pct": max(0, np.random.normal(7, 5)),
                "ROI_Moyen_Pct": np.random.normal(12, 6),
                "Projets_A_Temps_Pct": np.clip(np.random.normal(75, 12), 30, 100),
                "Adoption_Digital_Pct": np.clip(np.random.normal(60, 15), 20, 100),
                "Cout_IT_Par_Employe_MAD": np.random.normal(15000, 3000),
            })
    return pd.DataFrame(rows)


@pytest.fixture(scope="session")
def all_silver_data(silver_infra, silver_itsm, silver_cyber, silver_apps):
    """Dict de DataFrames pour IsolationForestDetector.run_all()."""
    return {
        "infra": silver_infra,
        "itsm": silver_itsm,
        "cyber": silver_cyber,
        "apps": silver_apps,
    }
