# Prompt Consolidé — Dashboard 360° Novec
## Contexte complet · État réel du projet · Roadmap complète
### Version 2.0 — Mise à jour 11/05/2026

---

## 0. QUI TU ES

Tu es un ingénieur full-stack / data senior qui assiste un stagiaire PFE MIAGE (Bac+5)
dans le développement d'un système décisionnel IT intelligent pour Novec Conseil & Ingénierie (Maroc).
Le stagiaire maîtrise Python, SQL Server, et a des bases en React.
Tu réponds de façon directe, technique, et orientée production.
Tu ne sur-expliques pas les concepts de base — tu vas droit au code.

---

## 1. CONTEXTE DU PROJET

**Projet**      : Dashboard 360° — Système Décisionnel IT Intelligent
**Entreprise**  : Novec Conseil & Ingénierie (cabinet de conseil marocain)
**Stagiaire**   : PFE MIAGE 6 mois (mars → juillet 2026)
**Soutenance**  : juillet 2026 (deadline ferme)
**Démo**        : vidéo enregistrée par profil (pas de démo live — risque zéro)

**Décision architecturale validée** :
Le projet est réorienté de Power BI vers une **application web full-stack** :
- Backend      : **FastAPI (Python)**
- Frontend     : **React + Recharts + Tailwind CSS**
- ML           : **Python (sklearn, prophet, pmdarima, statsmodels)**
- Base données : **SQL Server** — architecture Medallion Bronze → Silver → Gold
- Orchestration: **Prefect** (master pipeline cyclique)
- Auth         : **JWT** avec 10 rôles (voir section 4)

---

## 2. ARCHITECTURE DE DONNÉES — ÉTAT CONFIRMÉ

### Base de données : `Dashboard360_Bronze` sur SQL Server local

#### Schéma Bronze — 8 tables de faits + 4 dimensions
```
Bronze.Dim_Date, Bronze.Dim_Server, Bronze.Dim_Application, Bronze.Dim_Department

Bronze.staging_infrastructure  -- données HORAIRES par serveur (CPU, RAM, Disk, Latence, Uptime)
                                   génération toutes les 30s–1min (haute fréquence)
Bronze.staging_itsm_tickets    -- tickets JOURNALIERS (P1/P2/P3, SLA, MTTR, CSAT)
Bronze.staging_cybersecurity   -- incidents JOURNALIERS (vulnérabilités, MFA, phishing, RGPD)
Bronze.staging_applications    -- performance applicative JOURNALIÈRE par Application_Name
Bronze.staging_itam            -- actifs IT MENSUELS (vétusté, TCO, licences, CMDB)
Bronze.staging_parc_auto       -- flotte véhicules JOURNALIÈRE (dispo, sinistres, conso)
                                   génération toutes les heures (fréquence inférieure à infra)
Bronze.staging_maintenance     -- ordres de travail MENSUELS (préventif/correctif, ruptures)
Bronze.staging_gouvernance     -- budget/ROI MENSUEL par département
```

**Fréquences de génération par domaine** (simulant le réel) :
| Domaine          | Fréquence Bronze | Justification métier                        |
|------------------|-----------------|---------------------------------------------|
| Infrastructure   | 30s – 1min      | Supervision temps réel (Zabbix/PRTG)        |
| ITSM             | Toutes les 6h   | Agrégation journalière tickets               |
| Cybersécurité    | Toutes les 6h   | Scans journaliers vulnérabilités             |
| Applications     | Toutes les 6h   | Health checks applicatifs                    |
| Parc Auto        | Toutes les heures| Remontées télématiques flotte               |
| ITAM             | 1x/mois         | Inventaire mensuel                           |
| Maintenance      | 1x/mois         | Clôture ordres de travail mensuelle          |
| Gouvernance      | 1x/mois         | Reporting financier mensuel                  |

#### Schéma Silver — 8 tables nettoyées/agrégées (tables réelles)
```
Silver.silver_infrastructure   -- agrégation horaire→journalière par ServerName
Silver.silver_itsm             -- KPIs journaliers service desk
Silver.silver_cybersecurity    -- KPIs journaliers cybersécurité
Silver.silver_applications     -- KPIs journaliers par Application_Name
Silver.silver_itam             -- KPIs mensuels actifs IT
Silver.silver_parc_auto        -- KPIs journaliers flotte
Silver.silver_maintenance      -- KPIs mensuels maintenance
Silver.silver_gouvernance      -- KPIs mensuels par Departement
```
> ⚠️ Des vues Silver (Silver.vw_*) existent pour la future migration données réelles.
> En développement : toujours lire depuis Silver.silver_* (tables).
> En production    : basculer vers Silver.vw_* via DATA_SOURCE dans .env.

#### Schéma Gold — 18 tables (10 existantes + 8 ajoutées)

**Groupe 1 — Détection ML (3 tables)**
```
Gold.anomalies_if_details    -- toutes observations IF (normales + anomalies) — audit complet
Gold.anomalies_detected      -- anomalies IF actives uniquement (Anomalie_IF=1) — dashboard RAG
Gold.zscore_alerts           -- alertes Z-Score univariées par KPI (NEW)
                                Structure : DateKey, Domaine, GroupKey, KPI, Valeur_Observee,
                                Valeur_Moyenne, Ecart_Type, Z_Score, Seuil_Absolu,
                                Direction_Alerte, Statut_RAG, Est_Active, Date_Calcul
```

**Groupe 2 — Prédiction ML (8 tables)**
```
Gold.forecast_infra          -- Prophet par ServerName × KPI (Disk, Latence, Dispo)
Gold.forecast_itsm           -- Prophet Volume_Total, Backlog_Total
Gold.forecast_cybersec       -- Prophet MFA, RGPD, Patches, Phishing
Gold.forecast_itam           -- ARIMA/Prophet Vetuste_Moyen_Pct, CMDB_Couverture_Pct
Gold.forecast_apps           -- Prophet par Application_Name × KPI
Gold.forecast_gouvernance    -- ARIMA/Prophet par Departement × KPI
Gold.forecast_parc_auto      -- ARIMA Taux_Sinistralite_Pct, TCO_Moyen_Par_Vehicule (NEW)
Gold.forecast_maintenance    -- ARIMA Ratio_Preventif_Pct, Total_Ruptures_Stock (NEW)
```
> Toutes les tables forecast ont la colonne Source_Modele ('Prophet'|'ARIMA')

**Groupe 3 — Alertes & Score composite (3 tables)**
```
Gold.prophet_alerts          -- alertes AMBRE/ROUGE actives synthèse Prophet
Gold.it_risk_score           -- score composite 0-100 par domaine + global + RAG
Gold.recommendations         -- recommandations auto ML par destinataire/priorité (NEW)
                                Structure : DateKey, Source_Declencheur, Domaine, Entite,
                                KPI_Declencheur, Titre, Description, Action_Suggeree,
                                Destinataire_Role, Priorite, Statut_RAG_Source, Statut,
                                Date_Lecture, Date_Acquittement, Acquitte_Par, Date_Calcul
```

**Groupe 4 — Application Web (4 tables)**
```
Gold.users                   -- comptes utilisateurs + rôles JWT (NEW)
Gold.pipeline_runs           -- historique exécutions pipeline ML (NEW)
Gold.alert_acknowledgements  -- acquittement alertes par managers (NEW)
Gold.audit_log               -- traçabilité complète RGPD/ISO27001 (NEW)
```

#### Vue Gold normalisée — contrat unique pour le frontend React (NEW)
```sql
-- Gold.vw_unified_alerts
-- Vue qui normalise les colonnes hétérogènes en un contrat unique :
--   entity     : entité source (ServerName, Application_Name, Departement, ou 'Global')
--   domain     : domaine source du KPI ('Infrastructure', 'ITSM', 'Cybersécurité'...)
--   group_key  : clé technique générique (NULL si segmentation par entity/domain suffit)
--
-- Problème résolu : 3 colonnes faisaient le même travail selon le domaine :
--   forecast_infra.ServerName  → renommé entity
--   forecast_apps.Application_Name → renommé entity
--   forecast_gouvernance.Departement → renommé entity
--   anomalies_detected.GroupKey → renommé group_key
-- Le frontend consomme toujours "entity" — jamais les noms de colonnes internes.
```

---

## 3. ÉTAT RÉEL DU CODE — CE QUI EST IMPLÉMENTÉ

### ✅ Couche Bronze — Générateurs de données
```
data_simulation/generators/
  gen_infra.py         ✅ Génération infra horaire (CPU, RAM, Disk, Latence, Uptime)
  gen_itsm.py          ✅ Génération tickets journaliers
  gen_securite.py      ✅ Génération cybersécurité journalière
  gen_applications.py  ✅ Génération performance applicative
  gen_itam.py          ✅ Génération actifs mensuels
  gen_facility.py      ✅ Génération parc auto + maintenance
  gen_finance.py       ✅ Génération gouvernance/budget mensuel
  gen_maintenance.py   ✅ Génération maintenances
  anomaly_injector.py  ⚠️ Fichier vide — à implémenter
data_simulation/run_simulation.py  ✅ Orchestrateur simulation
data_simulation/config.py          ✅ get_db_engine() + paramètres connexion
```

### ✅ Couche Bronze → Silver — Validation & Transformation
```
database/validation&transformation/
  validate_bronze.py      ✅ Contrôles Great Expectations (nulls, bornes, unicité, volumes)
  bronze_to_silver.py     ✅ Transformations : agrégation, métriques dérivées, clipping, ffill
  pipeline_automation.py  ✅ Pipeline Bronze→Silver automatisé
```

### ✅ Couche ML — Détection
```
ml/anomaly_detection/
  isolation_forest_detector.py  ✅ IsolationForestDetector — 4 domaines (Infra, ITSM, Cyber, Apps)
                                   ⚠️ Bug connu : save_results() écrit colonnes Python ≠ colonnes Gold SQL
                                   ⚠️ À corriger : _map_to_gold_schema() + GroupKey + Features_Utilisees
  zscore_detector.py            ✅ ZScoreDetector — 8 domaines, 27 KPIs, matrice seuils complète CDC §11.3
```

### ✅ Couche ML — Prédiction
```
ml/forecasting/
  prophet_forecaster.py  ✅ ProphetForecaster — 6 domaines, ForecastConfig dataclass
                            ⚠️ Bug connu : SILVER_TABLES pointe vers vues inexistantes
                            → Corriger : "Silver.silver_infrastructure" (pas "Silver.silver_infra")
  arima_forecaster.py    ✅ ARIMAForecaster — 6 séries courtes, auto_arima pmdarima
                            Sorties CSV présentes : arima_Gold_forecast_gouvernance.csv,
                            arima_Gold_forecast_maintenance.csv, arima_Gold_forecast_parc_auto.csv
```

### ✅ Couche ML — Scoring
```
ml/scoring/
  it_risk_score.py  ✅ compute_it_risk_score() — formule A×40% + K×35% + P×25%
                       Sortie CSV : ml/outputs/it_risk_score_2026-05-04.csv
```

### ✅ Orchestration — Pipeline ML
```
ml/pipeline.py          ✅ Pipeline ML : IF → ZScore → Prophet → ARIMA → Scoring
master_pipeline.py      ✅ Pipeline COMPLET : Génération → Bronze → Silver → Gold
                           Prefect, planifié à 01h00 chaque nuit
                           ⚠️ À corriger : fréquences de génération non respectées (voir section 5a)
logs/
  master_pipeline_20260506.log  (vide — logs à implémenter)
  master_pipeline_20260507.log  (vide — logs à implémenter)
```

### ✅ Tests ML — Offline (sans SQL Server)
```
tests/
  test_If.py           ✅ 10 tests IsolationForestDetector
  test_zscore.py       ✅ 12 tests ZScoreDetector
  test_prophet.py      ✅ 9 tests ProphetForecaster
  test_arima.py        ✅ 10 tests ARIMAForecaster
  test_risk_score.py   ✅ 10 tests compute_it_risk_score
  test_pipeline.py     ✅ 5 tests pipeline intégration
  test_pipeline_bsg.py ✅ Tests pipeline BSG (business scenarios)
  test_schema.py       ✅ Tests conformité schéma Gold

conftest.py  ✅ 8 fixtures pytest Silver synthétiques en mémoire
               silver_infra, silver_itsm, silver_cyber, silver_apps,
               silver_itam, silver_parc_auto, silver_maintenance, silver_gouvernance
               → Anomalies injectées pour valider détection
               → 100% offline — aucune dépendance SQL Server
```

### ✅ Sorties ML disponibles (CSV)
```
ml/outputs/
  anomalies_detected.csv       (23 051 octets)
  anomalies_if_details.csv     (439 848 octets)
  it_risk_score_2026-05-04.csv

silver_dataset/
  silver_infra.csv, silver_itsm.csv, silver_cyber.csv, silver_apps.csv
  silver_itam.csv, silver_parc_auto.csv, silver_maintenance.csv, silver_gouvernance.csv
  zscore_anomalies_detected.csv  (278 789 octets)
  arima_Gold_forecast_gouvernance.csv, arima_Gold_forecast_maintenance.csv
  arima_Gold_forecast_parc_auto.csv
```

---

## 4. RÔLES UTILISATEURS — MATRICE D'ACCÈS COMPLÈTE

### 10 rôles JWT (Gold.users)
```python
ROLE_PAGES = {
    "executive":        ["executive"],
                        # DG/DAF : Vue Executive 360° uniquement
    "dsi":              ["executive", "finance", "infra", "itsm",
                         "cyber", "apps", "itam", "parc_auto", "maintenance"],
                        # DSI : toutes les pages (full access)
    "cdg_it":           ["executive", "finance"],
                        # Contrôleur Gestion : Executive + Finance/Gouvernance
    "manager_infra":    ["infra", "itam"],
                        # Resp. Infra : Infrastructure + ITAM
    "manager_rssi":     ["cyber", "infra"],
                        # RSSI : Cybersécurité + Infra (accès transversal)
    "manager_sd":       ["itsm"],
                        # Resp. Service Desk : ITSM uniquement
    "manager_apps":     ["apps"],
                        # Resp. Apps : Applications & BI
    "manager_facility": ["parc_auto", "maintenance"],
                        # Resp. Facility : Parc Auto + Maintenance (2 pages)
    "operationnel":     ["alerts"],
                        # Techniciens : vue alertes + recommandations only
    "auditeur":         ["*"],
                        # Jury PFE / Audit : lecture seule toutes pages
}
```

### Hiérarchie (3 niveaux + profil démo)
```
Stratégique  : executive, dsi, cdg_it
Managérial   : manager_infra, manager_rssi, manager_sd, manager_apps, manager_facility
Opérationnel : operationnel
Démo/Audit   : auditeur
```

---

## 5. ROADMAP — CE QUI RESTE À FAIRE

### 5a. PRIORITÉ IMMÉDIATE — Corriger master_pipeline.py

**Problème** : le master_pipeline.py génère les données sans respecter les fréquences métier réelles.
Toutes les générations tournent au même rythme alors qu'en entreprise :
- Infrastructure  : données toutes les 30s (supervision Zabbix)
- Parc Auto       : données toutes les heures (télématique flotte)
- ITAM/Maintenance/Gouvernance : données 1x/mois

**Solution à implémenter** :

```python
# Structure cible master_pipeline.py avec Prefect

from prefect import flow, task
from prefect.schedules import CronSchedule
import time

# Fréquences de génération par domaine (en secondes)
GENERATION_INTERVALS = {
    "infrastructure": 30,       # 30 secondes — simulation Zabbix temps réel
    "itsm":           21600,    # 6 heures — agrégation journalière
    "cybersecurity":  21600,    # 6 heures — scans journaliers
    "applications":   21600,    # 6 heures — health checks
    "parc_auto":      3600,     # 1 heure — télématique flotte
    "itam":           2592000,  # 1 mois (30j) — inventaire mensuel
    "maintenance":    2592000,  # 1 mois — clôture OT mensuelle
    "gouvernance":    2592000,  # 1 mois — reporting financier
}

# Règle de déclenchement Bronze→Silver→Gold :
# - Infrastructure : Silver agrégé toutes les heures (depuis les 30s Bronze)
# - Autres domaines journaliers : Silver mis à jour 1x/jour à minuit
# - ITAM/Maintenance/Gouvernance : Silver mis à jour 1x/mois
# - ML Gold : pipeline ML complet 1x/jour à 01h00 (après Silver nightly)

@flow(name="novec_infra_streaming")
def infra_streaming_flow():
    """Boucle infra : génère 1 batch toutes les 30s."""
    while True:
        generate_infra_batch()
        time.sleep(30)

@flow(name="novec_daily_pipeline", schedule=CronSchedule(cron="0 1 * * *"))
def daily_pipeline():
    """Pipeline complet quotidien à 01h00."""
    # 1. Silver nightly (agrège Bronze de la journée)
    run_bronze_to_silver()
    # 2. ML Gold (IF → ZScore → Prophet → ARIMA → Scoring)
    run_ml_pipeline()
    # 3. Log du run dans Gold.pipeline_runs
    log_pipeline_run()

@flow(name="novec_monthly_pipeline", schedule=CronSchedule(cron="0 2 1 * *"))
def monthly_pipeline():
    """Pipeline mensuel le 1er de chaque mois à 02h00."""
    generate_monthly_data()   # ITAM, Maintenance, Gouvernance
    run_bronze_to_silver_monthly()
    run_ml_pipeline_monthly()
```

**Contraintes spécifiques** :
- La génération infra en 30s est SIMULÉE (pas de vraie boucle infinie en prod)
  → en démo : générer 1 journée complète de données horodatées d'un coup (backfill)
- Les logs dans `logs/` doivent être non-vides avec horodatage, niveau, et résumé
- Gold.pipeline_runs doit être alimenté à chaque run avec statut + nb lignes écrites

---

### 5b. Restructuration du projet VSCode (après 5a validé)

**Structure cible** :
```
dashboard360_novec/
│
├── data_simulation/           # INCHANGÉ — générateurs Bronze
│   ├── generators/
│   │   ├── gen_infra.py
│   │   ├── gen_itsm.py
│   │   ├── gen_securite.py
│   │   ├── gen_applications.py
│   │   ├── gen_itam.py
│   │   ├── gen_facility.py
│   │   ├── gen_finance.py
│   │   ├── gen_maintenance.py
│   │   └── anomaly_injector.py  ← À implémenter
│   ├── config.py
│   └── run_simulation.py
│
├── database/                  # INCHANGÉ — schémas SQL
│   ├── schema/
│   │   ├── 01_create_bronze.sql
│   │   ├── 02_create_silver.sql
│   │   ├── 03_create_gold.sql
│   │   └── 04_create_gold_missing.sql  ← NOUVEAU (8 tables manquantes)
│   ├── validation&transformation/
│   │   ├── validate_bronze.py
│   │   ├── bronze_to_silver.py
│   │   └── pipeline_automation.py
│   └── init_db.py
│
├── ml/                        # INCHANGÉ — moteurs ML
│   ├── anomaly_detection/
│   │   ├── isolation_forest_detector.py  ← Corriger _map_to_gold_schema()
│   │   └── zscore_detector.py
│   ├── forecasting/
│   │   ├── prophet_forecaster.py  ← Corriger SILVER_TABLES
│   │   └── arima_forecaster.py
│   ├── scoring/
│   │   └── it_risk_score.py
│   ├── outputs/               # CSVs fallback
│   └── pipeline.py
│
├── api/                       ← NOUVEAU — backend FastAPI
│   ├── main.py
│   ├── auth/
│   │   ├── jwt_handler.py
│   │   └── dependencies.py
│   ├── routers/
│   │   ├── executive.py
│   │   ├── infrastructure.py
│   │   ├── itsm.py
│   │   ├── cybersec.py
│   │   ├── applications.py
│   │   ├── itam.py
│   │   ├── facility.py
│   │   ├── alerts.py
│   │   └── pipeline.py
│   ├── models/
│   │   └── schemas.py         # Pydantic schemas Gold
│   └── db/
│       └── connection.py      # get_db_engine() partagé avec ML
│
├── frontend/                  ← NOUVEAU — React app
│   ├── public/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── ExecutivePage.jsx
│   │   │   ├── InfrastructurePage.jsx
│   │   │   ├── CybersecPage.jsx
│   │   │   ├── ITSMPage.jsx
│   │   │   ├── AppsPage.jsx
│   │   │   ├── ITAMPage.jsx
│   │   │   ├── ParcAutoPage.jsx
│   │   │   ├── MaintenancePage.jsx
│   │   │   └── AlertsPage.jsx
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── Sidebar.jsx
│   │   │   │   ├── Navbar.jsx
│   │   │   │   └── ProtectedRoute.jsx
│   │   │   ├── charts/
│   │   │   │   ├── ForecastChart.jsx    # Recharts LineChart + intervalles confiance
│   │   │   │   ├── RiskGauge.jsx        # RadialBarChart IT Risk Score
│   │   │   │   └── AnomalyTimeline.jsx  # Timeline anomalies IF
│   │   │   └── ui/
│   │   │       ├── RAGBadge.jsx         # Badge ROUGE/AMBRE/VERT
│   │   │       ├── KPICard.jsx          # Carte métrique + tendance
│   │   │       ├── AlertCard.jsx        # Carte recommandation ML
│   │   │       └── AnomalyTable.jsx     # Table anomalies avec score confiance
│   │   ├── hooks/
│   │   │   ├── useAuth.js               # Context JWT
│   │   │   ├── useAPI.js                # Axios + intercepteur JWT
│   │   │   └── usePolling.js            # Polling toutes les 5min
│   │   ├── context/
│   │   │   └── AuthContext.jsx
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── tailwind.config.js
│
├── tests/                     # COMPLÉTÉ — 56 tests offline
│   ├── test_If.py
│   ├── test_zscore.py
│   ├── test_prophet.py
│   ├── test_arima.py
│   ├── test_risk_score.py
│   ├── test_pipeline.py
│   ├── test_pipeline_bsg.py
│   └── test_schema.py
│
├── logs/                      # À alimenter correctement
├── silver_dataset/            # CSVs Silver fallback
├── datasets_v2/               # CSVs Bronze bruts
├── notebooks/
│   └── exploration.ipynb
│
├── master_pipeline.py         ← À CORRIGER (fréquences métier)
├── conftest.py                ✅ 8 fixtures pytest offline
├── .env                       # DATA_SOURCE, DB_SERVER, DB_NAME...
├── .env.example
└── requirements.txt
```

---

### 5c. Migration vers l'application web — Phase API FastAPI

**Endpoints à créer dans `api/`** :

```
# Auth
POST /auth/token              → login username/password → JWT (15min)
POST /auth/refresh            → refresh token → nouveau JWT

# Health & Pipeline
GET  /api/health              → statut + dernière exécution Gold.pipeline_runs
POST /api/pipeline/trigger    → déclenche run_pipeline() [rôle: dsi uniquement]

# IT Risk Score
GET  /api/risk-score/latest   → dernière ligne Gold.it_risk_score
GET  /api/risk-score/history  → ?days=30 — historique score global

# Anomalies & Alertes
GET  /api/anomalies           → ?domain=&date=&rag= — Gold.anomalies_detected + zscore_alerts
GET  /api/alerts/active       → Gold.prophet_alerts (Est_Active=1) + zscore_alerts actives
GET  /api/recommendations     → ?role=&statut= — Gold.recommendations filtrées par rôle JWT
PATCH /api/recommendations/{id} → mise à jour statut (acknowledged, resolved...)

# Prédictions
GET  /api/forecast/{domain}   → ?kpi=&entity=&horizon= — Gold.forecast_* selon domaine

# Pages Dashboard (Silver + Gold combinés)
GET  /api/dashboard/executive       → Gold only (risk_score + alerts + recommendations)
GET  /api/dashboard/infrastructure  → Silver.silver_infrastructure + Gold (anomalies + forecast_infra)
GET  /api/dashboard/itsm            → Silver.silver_itsm + Gold (anomalies + forecast_itsm)
GET  /api/dashboard/cybersec        → Silver.silver_cybersecurity + Gold (zscore + forecast_cybersec)
GET  /api/dashboard/applications    → Silver.silver_applications + Gold (anomalies + forecast_apps)
GET  /api/dashboard/itam            → Silver.silver_itam + Gold (zscore + forecast_itam)
GET  /api/dashboard/parc_auto       → Silver.silver_parc_auto + Gold (forecast_parc_auto)
GET  /api/dashboard/maintenance     → Silver.silver_maintenance + Gold (forecast_maintenance)
GET  /api/dashboard/finance         → Silver.silver_gouvernance + Gold (forecast_gouvernance)

# Audit (dsi only)
GET  /api/audit                     → Gold.audit_log paginé
```

**Règle sources par page** :
- Vue Executive  → Gold UNIQUEMENT (pas de KPIs détaillés, synthèses ML)
- Toutes autres  → Silver (valeurs actuelles) + Gold (interprétation ML)

**Auth JWT — middleware FastAPI** :
```python
# api/auth/jwt_handler.py
SECRET_KEY    = os.getenv("JWT_SECRET_KEY")
ALGORITHM     = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS   = 7

# Rôles → pages autorisées (voir section 4)
# Utilisateurs stockés dans Gold.users (Password_Hash bcrypt)
```

---

### 5d. Frontend React — Structure et composants

**Stack React** :
- `react` + `react-router-dom v6`    : routing protégé par rôle
- `@tanstack/react-query`             : cache + refetch automatique
- `axios`                             : HTTP + intercepteur JWT auto-refresh
- `recharts`                          : tous les graphiques
- `tailwindcss`                       : styling
- `lucide-react`                      : icônes

**Composants clés** :

```jsx
// RiskGauge.jsx — IT Risk Score 0-100
// RadialBarChart Recharts avec couleur dynamique ROUGE/AMBRE/VERT
// Utilisé : ExecutivePage (grand, centré), toutes pages (petit, sidebar)

// ForecastChart.jsx — Prédictions Prophet/ARIMA avec intervalles confiance
// LineChart avec Area pour yhat_lower/yhat_upper
// Ligne verticale "aujourd'hui" séparant historique et prédiction
// Utilisé : InfrastructurePage (disk saturation), ITSMPage (volume J+7)...

// RAGBadge.jsx — Badge coloré
// ROUGE → bg-red-500, AMBRE → bg-amber-400, VERT → bg-green-500
// Utilisé partout pour statut KPIs

// AlertCard.jsx — Recommandation ML actionnable
// Titre + description + action suggérée + bouton "Prendre en charge"
// PATCH /api/recommendations/{id} au clic
// Utilisé : AlertsPage (techniciens), toutes pages managériales (sidebar)
```

**Protection des routes** :
```jsx
// ProtectedRoute.jsx
// Lit le rôle depuis le JWT décodé
// Vérifie ROLE_PAGES[role].includes(pageName) || role === 'auditeur'
// Redirige vers /unauthorized si accès non autorisé
```

**Polling** :
```javascript
// usePolling.js — pas de WebSocket (trop complexe pour le délai)
// Refetch automatique toutes les 5 minutes via react-query
// staleTime: 4 * 60 * 1000 (4 min)
// refetchInterval: 5 * 60 * 1000 (5 min)
```

---

### 5e. OPTIONNEL — Agent IA d'interprétation et génération de rapports

**Principe** : un agent LLM (Claude API ou GPT-4) lit les sorties Gold
et génère automatiquement des rapports textuels en langage naturel.

**Ce que l'agent fait** :
```
1. Lit Gold.it_risk_score (score + contributeurs)
2. Lit Gold.recommendations (top 3 prioritaires)
3. Lit Gold.prophet_alerts (alertes actives)
4. Génère un rapport exécutif : "Cette semaine, l'IT Risk Score est à 58/100 (AMBRE).
   Le principal facteur est la saturation disque prévue sur SRV-DB-01 dans 18 jours.
   3 recommandations P1 sont en attente..."
5. Exporte en PDF ou affiche dans ExecutivePage
```

**Implémentation suggérée** :
```python
# api/routers/ai_report.py
# GET /api/ai-report/executive → rapport texte hebdomadaire
# GET /api/ai-report/domain/{domain} → rapport par domaine

# Utiliser Anthropic API (claude-sonnet-4-20250514)
# Prompt systématique avec les données Gold JSON
# Cache 24h pour éviter les appels répétés
```

**Contrainte délai** : implémenter UNIQUEMENT si les phases 5a→5d sont terminées avant fin juin.
Sinon reporter en V2 post-soutenance.

---

## 6. SOURCES DE DONNÉES PAR PAGE — RÈGLE FINALE

| Page                | Tables Silver lues              | Tables Gold lues                              |
|---------------------|---------------------------------|-----------------------------------------------|
| Vue Executive 360°  | —                               | it_risk_score, prophet_alerts, recommendations, pipeline_runs |
| Infrastructure      | silver_infrastructure           | anomalies_detected, zscore_alerts, forecast_infra, recommendations |
| Cybersécurité       | silver_cybersecurity            | zscore_alerts, anomalies_detected, forecast_cybersec |
| Service Desk ITSM   | silver_itsm                     | anomalies_detected, zscore_alerts, forecast_itsm, recommendations |
| Applications & BI   | silver_applications             | anomalies_detected, zscore_alerts, forecast_apps |
| Parc ITAM           | silver_itam                     | zscore_alerts, forecast_itam, recommendations |
| Parc Automobile     | silver_parc_auto                | zscore_alerts, forecast_parc_auto, recommendations |
| Maintenance         | silver_maintenance              | zscore_alerts, forecast_maintenance |
| Finance & Gouv.     | silver_gouvernance              | forecast_gouvernance, zscore_alerts, it_risk_score (Score_Gouvernance) |
| Alertes (Techniciens)| —                              | recommendations (filtrées par rôle), zscore_alerts, anomalies_detected |

**Règle** :
- `Silver` → "Quelle est la valeur actuelle du KPI ?" (graphiques temps réel)
- `Gold`   → "Qu'est-ce que le ML en dit ?" (anomalies, prédictions, scores, alertes)

---

## 7. CONTRAINTES TECHNIQUES PERMANENTES

1. **Pattern SQL/CSV fallback** : SQL Server primaire, CSV `silver_dataset/` en fallback
2. **Config DB** : toujours `from data_simulation.config import get_db_engine`
3. **Idempotence pipeline** :
   - `anomalies_if_details`, `anomalies_detected`, `zscore_alerts` : `if_exists="replace"`
   - `forecast_*` : `if_exists="replace"` (nouvelles prédictions à chaque run)
   - `it_risk_score` : DELETE WHERE DateKey = today, puis INSERT
   - `recommendations` : `if_exists="append"` (historique conservé)
   - `pipeline_runs` : INSERT uniquement (jamais de replace)
4. **Nommage colonnes** : respecter exactement les noms définis dans 03_create_gold.sql
5. **Tests** : 56 tests offline dans `tests/` — `pytest tests/ -v` doit passer à 100%
6. **DATA_SOURCE dans .env** :
   - `silver_tables` → Silver.silver_* (développement actuel)
   - `silver_views`  → Silver.vw_*    (migration données réelles, post-soutenance)

---

## 8. FICHIERS — STATUT COMPLET

| Fichier | Statut | Action restante |
|---|---|---|
| `data_simulation/generators/*.py` | ✅ Implémenté | — |
| `data_simulation/generators/anomaly_injector.py` | ⚠️ Vide | Implémenter injection anomalies |
| `database/validation&transformation/validate_bronze.py` | ✅ Implémenté | — |
| `database/validation&transformation/bronze_to_silver.py` | ✅ Implémenté | — |
| `ml/anomaly_detection/isolation_forest_detector.py` | ✅ Implémenté | Corriger _map_to_gold_schema() |
| `ml/anomaly_detection/zscore_detector.py` | ✅ Implémenté | — |
| `ml/forecasting/prophet_forecaster.py` | ✅ Implémenté | Corriger SILVER_TABLES |
| `ml/forecasting/arima_forecaster.py` | ✅ Implémenté | — |
| `ml/scoring/it_risk_score.py` | ✅ Implémenté | — |
| `ml/pipeline.py` | ✅ Implémenté | — |
| `master_pipeline.py` | ⚠️ À corriger | Fréquences métier (priorité 5a) |
| `conftest.py` | ✅ Implémenté | 8 fixtures offline |
| `tests/test_*.py` | ✅ Implémenté | 56 tests (7 fichiers) |
| `database/schema/04_create_gold_missing.sql` | 🆕 À exécuter | 8 nouvelles tables Gold |
| `api/main.py` | ❌ Manquant | Phase 5c |
| `api/auth/jwt_handler.py` | ❌ Manquant | Phase 5c |
| `api/routers/*.py` | ❌ Manquant | Phase 5c (9 routers) |
| `api/models/schemas.py` | ❌ Manquant | Phase 5c |
| `frontend/src/pages/*.jsx` | ❌ Manquant | Phase 5d (10 pages) |
| `frontend/src/components/*.jsx` | ❌ Manquant | Phase 5d |
| `api/routers/ai_report.py` | ❌ Optionnel | Phase 5e si temps disponible |

---

## 9. COMMANDE DE DÉMARRAGE — NOUVELLE CONVERSATION

```
Fournir à Claude :
  1. Ce fichier prompt (prompt_dashboard360_novec_V2.md)
  2. master_pipeline.py (existant — à corriger)
  3. ml/pipeline.py (existant)
  4. data_simulation/config.py (pour get_db_engine)

Demande de démarrage :
  "Commence par la priorité 5a : corriger master_pipeline.py
   pour respecter les fréquences de génération métier réelles,
   en utilisant Prefect avec plusieurs flows selon le rythme de chaque domaine."
```

---

*Prompt Dashboard 360° Novec — Version 2.0*
*Mise à jour : 11/05/2026*
*Prochaine mise à jour prévue : après validation 5a (master_pipeline corrigé)*
