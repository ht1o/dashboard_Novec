-- =============================================================================
-- GOLD SCHEMA — Tables manquantes
-- Dashboard 360 Novec — Complément au 03_create_gold.sql
-- Base de données : Dashboard360_Bronze
-- =============================================================================
-- Tables ajoutées :
--   ML — Prédictions domaines manquants
--     1. Gold.forecast_parc_auto       — prédictions ARIMA parc automobile
--     2. Gold.forecast_maintenance     — prédictions ARIMA maintenance
--
--   ML — Détection Z-Score
--     3. Gold.zscore_alerts            — alertes Z-Score actives par KPI
--
--   ML — Recommandations automatiques
--     4. Gold.recommendations          — actions correctives générées par le moteur ML
--
--   Application Web — Couche applicative
--     5. Gold.users                    — comptes utilisateurs + rôles JWT
--     6. Gold.pipeline_runs            — historique exécutions pipeline ML
--     7. Gold.alert_acknowledgements   — suivi acquittement alertes par managers
--     8. Gold.audit_log                — traçabilité complète des actions utilisateurs
-- =============================================================================

USE Dashboard360_Bronze;
GO

-- =============================================================================
-- 1. Gold.forecast_parc_auto
--    Prédictions ARIMA : Taux_Sinistralite_Pct, TCO_Moyen_Par_Vehicule_MAD
--    Horizon : 1-3 mois (freq=MS — séries mensuelles courtes)
-- =============================================================================
IF OBJECT_ID('Gold.forecast_parc_auto', 'U') IS NOT NULL
    DROP TABLE Gold.forecast_parc_auto;
GO

CREATE TABLE Gold.forecast_parc_auto (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    KPI                 NVARCHAR(60)    NOT NULL,           -- Taux_Sinistralite_Pct / TCO_Moyen_Par_Vehicule_MAD
    DS                  DATE            NOT NULL,           -- date de prédiction

    Yhat                FLOAT           NOT NULL,
    Yhat_Lower          FLOAT           NOT NULL,
    Yhat_Upper          FLOAT           NOT NULL,
    Trend               FLOAT           NULL,
    Trend_Lower         FLOAT           NULL,
    Trend_Upper         FLOAT           NULL,

    Is_Forecast         BIT             NOT NULL DEFAULT 1,
    Statut_RAG          NVARCHAR(10)    NOT NULL DEFAULT 'VERT'
                            CONSTRAINT CK_FPA_RAG   CHECK (Statut_RAG   IN ('ROUGE', 'AMBRE', 'VERT')),
    Risk_Score          FLOAT           NOT NULL DEFAULT 0
                            CONSTRAINT CK_FPA_Risk  CHECK (Risk_Score   BETWEEN 0 AND 1),
    Source_Modele       NVARCHAR(20)    NOT NULL DEFAULT 'ARIMA'
                            CONSTRAINT CK_FPA_Src   CHECK (Source_Modele IN ('Prophet', 'ARIMA')),

    Date_Calcul         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_FPA   PRIMARY KEY (Id),
    CONSTRAINT UQ_FPA_KPI_DS UNIQUE (KPI, DS)
);

CREATE INDEX IX_FPA_KPI     ON Gold.forecast_parc_auto (KPI, DS);
CREATE INDEX IX_FPA_RAG     ON Gold.forecast_parc_auto (Statut_RAG) WHERE Is_Forecast = 1;

PRINT 'Table Gold.forecast_parc_auto créée.';
GO


-- =============================================================================
-- 2. Gold.forecast_maintenance
--    Prédictions ARIMA : Ratio_Preventif_Pct, Total_Ruptures_Stock
--    Horizon : 3 mois (freq=MS)
-- =============================================================================
IF OBJECT_ID('Gold.forecast_maintenance', 'U') IS NOT NULL
    DROP TABLE Gold.forecast_maintenance;
GO

CREATE TABLE Gold.forecast_maintenance (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    KPI                 NVARCHAR(60)    NOT NULL,           -- Ratio_Preventif_Pct / Total_Ruptures_Stock
    DS                  DATE            NOT NULL,

    Yhat                FLOAT           NOT NULL,
    Yhat_Lower          FLOAT           NOT NULL,
    Yhat_Upper          FLOAT           NOT NULL,
    Trend               FLOAT           NULL,
    Trend_Lower         FLOAT           NULL,
    Trend_Upper         FLOAT           NULL,

    Is_Forecast         BIT             NOT NULL DEFAULT 1,
    Statut_RAG          NVARCHAR(10)    NOT NULL DEFAULT 'VERT'
                            CONSTRAINT CK_FM_RAG    CHECK (Statut_RAG   IN ('ROUGE', 'AMBRE', 'VERT')),
    Risk_Score          FLOAT           NOT NULL DEFAULT 0
                            CONSTRAINT CK_FM_Risk   CHECK (Risk_Score   BETWEEN 0 AND 1),
    Source_Modele       NVARCHAR(20)    NOT NULL DEFAULT 'ARIMA'
                            CONSTRAINT CK_FM_Src    CHECK (Source_Modele IN ('Prophet', 'ARIMA')),

    Date_Calcul         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_FM    PRIMARY KEY (Id),
    CONSTRAINT UQ_FM_KPI_DS UNIQUE (KPI, DS)
);

CREATE INDEX IX_FM_KPI      ON Gold.forecast_maintenance (KPI, DS);
CREATE INDEX IX_FM_RAG      ON Gold.forecast_maintenance (Statut_RAG) WHERE Is_Forecast = 1;

PRINT 'Table Gold.forecast_maintenance créée.';
GO


-- =============================================================================
-- 3. Gold.zscore_alerts
--    Alertes Z-Score actives : une ligne par KPI en anomalie univariée.
--    Complémentaire à anomalies_detected (IF = multivarié, Z-Score = scalaire).
--
--    Différence fondamentale avec anomalies_detected :
--      anomalies_detected → "ce cluster de métriques combinées est anormal"
--      zscore_alerts      → "ce KPI précis vaut X, soit Z=3.8 écarts-types"
--    Les deux alimentent le dashboard RAG mais avec des lectures différentes.
-- =============================================================================
IF OBJECT_ID('Gold.zscore_alerts', 'U') IS NOT NULL
    DROP TABLE Gold.zscore_alerts;
GO

CREATE TABLE Gold.zscore_alerts (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    -- ── Identification ───────────────────────────────────────────────────────
    DateKey             DATE            NOT NULL,
    Domaine             NVARCHAR(50)    NOT NULL,           -- Infrastructure / ITSM / ...
    GroupKey            NVARCHAR(100)   NULL,               -- ServerName / Application_Name / NULL si global

    -- ── KPI en anomalie ──────────────────────────────────────────────────────
    KPI                 NVARCHAR(60)    NOT NULL,           -- nom exact de la colonne Silver
    Valeur_Observee     FLOAT           NOT NULL,           -- valeur brute du KPI ce jour
    Valeur_Moyenne      FLOAT           NOT NULL,           -- moyenne historique (fenêtre glissante)
    Ecart_Type          FLOAT           NOT NULL,           -- écart-type historique
    Z_Score             FLOAT           NOT NULL,           -- (Valeur_Observee - Moyenne) / Ecart_Type

    -- ── Seuil configuré ──────────────────────────────────────────────────────
    Seuil_Absolu        FLOAT           NULL,               -- seuil métier absolu (ex: CPU > 85%)
    Direction_Alerte    NVARCHAR(10)    NOT NULL
                            CONSTRAINT CK_ZA_Dir    CHECK (Direction_Alerte IN ('above', 'below', 'zscore')),

    -- ── Niveau d'alerte ──────────────────────────────────────────────────────
    -- ROUGE : |Z| > 3  OU valeur > seuil_rouge
    -- AMBRE : |Z| > 2  OU valeur > seuil_ambre
    Statut_RAG          NVARCHAR(10)    NOT NULL
                            CONSTRAINT CK_ZA_RAG    CHECK (Statut_RAG   IN ('ROUGE', 'AMBRE')),

    -- ── Gestion du cycle de vie ──────────────────────────────────────────────
    Est_Active          BIT             NOT NULL DEFAULT 1,
    Date_Calcul         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_ZA    PRIMARY KEY (Id)
);

-- Index pour les lectures dashboard (alertes actives par domaine)
CREATE INDEX IX_ZA_Date_Domaine ON Gold.zscore_alerts (DateKey, Domaine);
CREATE INDEX IX_ZA_Active_RAG   ON Gold.zscore_alerts (Est_Active, Statut_RAG, Z_Score DESC)
                                 WHERE Est_Active = 1;
CREATE INDEX IX_ZA_GroupKey     ON Gold.zscore_alerts (GroupKey) WHERE GroupKey IS NOT NULL;

PRINT 'Table Gold.zscore_alerts créée.';
GO


-- =============================================================================
-- 4. Gold.recommendations
--    Recommandations automatiques générées par le moteur ML.
--    Source : règles if/then sur les sorties IF + Z-Score + Prophet (CDC §11.7).
--
--    Exemples de règles :
--      IF anomalie_IF (CPU+RAM+Latence)  → "Déclencher P1 ITSM — Vérifier serveur X"
--      IF Z-Score SLA_P1 < 85% 3j        → "Allouer technicien Service Desk"
--      IF Prophet saturation disque 14j  → "Commander capacité disque"
--      IF IT Risk Score > 60 (Rouge) 2j  → "Convoquer comité de crise IT"
-- =============================================================================
IF OBJECT_ID('Gold.recommendations', 'U') IS NOT NULL
    DROP TABLE Gold.recommendations;
GO

CREATE TABLE Gold.recommendations (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    -- ── Contexte déclencheur ─────────────────────────────────────────────────
    DateKey             DATE            NOT NULL,
    Source_Declencheur  NVARCHAR(20)    NOT NULL
                            CONSTRAINT CK_REC_Src   CHECK (Source_Declencheur IN (
                                'IsolationForest', 'ZScore', 'Prophet', 'ARIMA', 'RiskScore'
                            )),
    Domaine             NVARCHAR(50)    NOT NULL,
    Entite              NVARCHAR(100)   NULL,               -- serveur, app, département, NULL si global
    KPI_Declencheur     NVARCHAR(60)    NULL,               -- KPI qui a déclenché la règle

    -- ── Contenu de la recommandation ─────────────────────────────────────────
    Titre               NVARCHAR(200)   NOT NULL,           -- résumé court (affiché dans la liste)
    Description         NVARCHAR(MAX)   NOT NULL,           -- texte complet de la recommandation
    Action_Suggeree     NVARCHAR(MAX)   NULL,               -- action concrète à entreprendre

    -- ── Ciblage ──────────────────────────────────────────────────────────────
    -- Rôle destinataire (aligné sur les rôles JWT de l'application)
    Destinataire_Role   NVARCHAR(50)    NOT NULL
                            CONSTRAINT CK_REC_Role  CHECK (Destinataire_Role IN (
                                'dsi', 'manager_infra', 'manager_rssi', 'manager_sd',
                                'manager_apps', 'manager_facility', 'operationnel', 'executive'
                            )),

    -- ── Priorité ─────────────────────────────────────────────────────────────
    -- P1 Critique : action immédiate (< 2h)
    -- P2 Haute    : action sous 48h
    -- P3 Normale  : action planifiée
    Priorite            NVARCHAR(15)    NOT NULL DEFAULT 'P2_Haute'
                            CONSTRAINT CK_REC_Prio  CHECK (Priorite IN ('P1_Critique', 'P2_Haute', 'P3_Normale')),
    Statut_RAG_Source   NVARCHAR(10)    NOT NULL DEFAULT 'ROUGE'
                            CONSTRAINT CK_REC_RAG   CHECK (Statut_RAG_Source IN ('ROUGE', 'AMBRE', 'VERT')),

    -- ── Cycle de vie ─────────────────────────────────────────────────────────
    -- pending    : générée, non lue
    -- read       : lue par le destinataire
    -- acknowledged : prise en compte, action en cours
    -- resolved   : résolue / clôturée
    -- dismissed  : ignorée / non pertinente
    Statut              NVARCHAR(20)    NOT NULL DEFAULT 'pending'
                            CONSTRAINT CK_REC_Statut CHECK (Statut IN (
                                'pending', 'read', 'acknowledged', 'resolved', 'dismissed'
                            )),

    Date_Lecture        DATETIME2       NULL,               -- renseigné par l'API quand lue
    Date_Acquittement   DATETIME2       NULL,
    Acquitte_Par        NVARCHAR(100)   NULL,               -- username qui a acquitté
    Date_Calcul         DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_REC   PRIMARY KEY (Id)
);

CREATE INDEX IX_REC_Destinataire ON Gold.recommendations (Destinataire_Role, Statut, Priorite);
CREATE INDEX IX_REC_Date_Domaine ON Gold.recommendations (DateKey, Domaine);
CREATE INDEX IX_REC_Pending      ON Gold.recommendations (Statut, Priorite, DateKey DESC)
                                  WHERE Statut IN ('pending', 'read');

PRINT 'Table Gold.recommendations créée.';
GO


-- =============================================================================
-- 5. Gold.users
--    Comptes utilisateurs de l'application web.
--    Authentification JWT côté FastAPI — cette table est la source de vérité.
--
--    NB : les mots de passe sont stockés hashés (bcrypt via passlib).
--    JAMAIS stocker le mot de passe en clair.
-- =============================================================================
IF OBJECT_ID('Gold.users', 'U') IS NOT NULL
    DROP TABLE Gold.users;
GO

CREATE TABLE Gold.users (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    -- ── Identité ─────────────────────────────────────────────────────────────
    Username            NVARCHAR(50)    NOT NULL,
    Email               NVARCHAR(150)   NOT NULL,
    Nom_Complet         NVARCHAR(150)   NULL,

    -- ── Sécurité ─────────────────────────────────────────────────────────────
    Password_Hash       NVARCHAR(255)   NOT NULL,           -- bcrypt hash
    Is_Active           BIT             NOT NULL DEFAULT 1,

    -- ── Rôle applicatif ──────────────────────────────────────────────────────
    -- Aligné exactement sur ROLE_PAGES dans FastAPI
    Role                NVARCHAR(50)    NOT NULL
                            CONSTRAINT CK_USR_Role  CHECK (Role IN (
                                'executive',        -- DG / DAF : Vue Executive seulement
                                'dsi',              -- DSI : toutes les pages
                                'manager_infra',    -- Resp. Infra : Infra + ITAM
                                'manager_rssi',     -- RSSI : Cyber + Infra (transversal)
                                'manager_sd',       -- Resp. Service Desk : ITSM
                                'manager_apps',     -- Resp. Apps : Applications
                                'manager_facility', -- Resp. Facility : Parc Auto + Maintenance
                                'cdg_it',           -- Contrôleur gestion : Finance + Gouvernance
                                'operationnel',     -- Techniciens : vue alertes only
                                'auditeur'          -- Lecture seule toutes pages (jury/audit)
                            )),

    -- ── Métadonnées ──────────────────────────────────────────────────────────
    Derniere_Connexion  DATETIME2       NULL,
    Date_Creation       DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    Date_Modification   DATETIME2       NULL,

    CONSTRAINT PK_USR   PRIMARY KEY (Id),
    CONSTRAINT UQ_USR_Username UNIQUE (Username),
    CONSTRAINT UQ_USR_Email    UNIQUE (Email)
);

-- Données initiales — comptes de démonstration (à hasher avant insertion réelle)
-- Les hash ci-dessous sont des placeholders — générer avec bcrypt en Python
INSERT INTO Gold.users (Username, Email, Nom_Complet, Password_Hash, Role) VALUES
('dsi_demo',        'dsi@novec.ma',         'Directeur IT',          '$PLACEHOLDER_HASH', 'dsi'),
('executive_demo',  'dg@novec.ma',          'Direction Générale',    '$PLACEHOLDER_HASH', 'executive'),
('infra_demo',      'infra@novec.ma',        'Responsable Infra',    '$PLACEHOLDER_HASH', 'manager_infra'),
('rssi_demo',       'rssi@novec.ma',         'RSSI',                 '$PLACEHOLDER_HASH', 'manager_rssi'),
('sd_demo',         'servicedesk@novec.ma',  'Resp. Service Desk',   '$PLACEHOLDER_HASH', 'manager_sd'),
('apps_demo',       'apps@novec.ma',         'Resp. Applications',   '$PLACEHOLDER_HASH', 'manager_apps'),
('facility_demo',   'facility@novec.ma',     'Resp. Facility',       '$PLACEHOLDER_HASH', 'manager_facility'),
('cdg_demo',        'cdg@novec.ma',          'Contrôleur Gestion',   '$PLACEHOLDER_HASH', 'cdg_it'),
('tech_demo',       'tech@novec.ma',         'Technicien',           '$PLACEHOLDER_HASH', 'operationnel'),
('auditeur_demo',   'audit@novec.ma',        'Jury PFE',             '$PLACEHOLDER_HASH', 'auditeur');
GO

PRINT 'Table Gold.users créée avec 10 comptes de démonstration.';
GO


-- =============================================================================
-- 6. Gold.pipeline_runs
--    Historique des exécutions du pipeline ML (Prefect + manuel).
--    Alimentée par pipeline.py à chaque run.
--    Lue par l'endpoint GET /api/health et la page Executive.
-- =============================================================================
IF OBJECT_ID('Gold.pipeline_runs', 'U') IS NOT NULL
    DROP TABLE Gold.pipeline_runs;
GO

CREATE TABLE Gold.pipeline_runs (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    -- ── Identification du run ────────────────────────────────────────────────
    Run_Id              NVARCHAR(50)    NOT NULL,           -- UUID généré par pipeline.py
    Triggered_By        NVARCHAR(50)    NOT NULL DEFAULT 'scheduler'
                            CONSTRAINT CK_PR_Trigger CHECK (Triggered_By IN (
                                'scheduler',    -- Prefect planifié
                                'api',          -- POST /api/pipeline/trigger
                                'manual',        -- exécution manuelle locale
                                'master_pipeline'   -- orchestrateur unifié   
                            )),
    Triggered_By_User   NVARCHAR(50)    NULL,               -- username si déclenché via API

    -- ── Timing ───────────────────────────────────────────────────────────────
    Started_At          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
    Finished_At         DATETIME2       NULL,
    Duration_Seconds    INT             NULL,               -- calculé à la fin du run

    -- ── Statut global ────────────────────────────────────────────────────────
    Status              NVARCHAR(20)    NOT NULL DEFAULT 'running'
                            CONSTRAINT CK_PR_Status CHECK (Status IN (
                                'running', 'success', 'partial', 'failed'
                            )),
    Error_Message       NVARCHAR(MAX)   NULL,               -- renseigné si Status = 'failed'

    -- ── Résultats par étape ──────────────────────────────────────────────────
    IF_Anomalies_Detectees      INT     NULL,               -- nb lignes écrites dans anomalies_detected
    ZScore_Alertes_Generees     INT     NULL,               -- nb lignes écrites dans zscore_alerts
    Prophet_Predictions         INT     NULL,               -- nb lignes écrites dans forecast_*
    ARIMA_Predictions           INT     NULL,
    Recommendations_Generees    INT     NULL,               -- nb lignes écrites dans recommendations
    Risk_Score_Global           FLOAT   NULL,               -- valeur du score calculé ce run
    Risk_Score_RAG              NVARCHAR(10) NULL,

    CONSTRAINT PK_PR    PRIMARY KEY (Id),
    CONSTRAINT UQ_PR_RunId UNIQUE (Run_Id)
);

CREATE INDEX IX_PR_Started  ON Gold.pipeline_runs (Started_At DESC);
CREATE INDEX IX_PR_Status   ON Gold.pipeline_runs (Status, Started_At DESC);

PRINT 'Table Gold.pipeline_runs créée.';
GO


-- =============================================================================
-- 7. Gold.alert_acknowledgements
--    Suivi de la prise en charge des alertes par les managers.
--    Permet de fermer la boucle : alerte générée → vue → acquittée → résolue.
--
--    Lie Gold.recommendations (Id) à Gold.users (Username).
--    L'API met à jour cette table quand un manager clique "Prendre en charge".
-- =============================================================================
IF OBJECT_ID('Gold.alert_acknowledgements', 'U') IS NOT NULL
    DROP TABLE Gold.alert_acknowledgements;
GO

CREATE TABLE Gold.alert_acknowledgements (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    -- ── Référence à la recommandation ────────────────────────────────────────
    Recommendation_Id   INT             NOT NULL,
    -- FK logique (pas de FOREIGN KEY pour éviter les contraintes en cas de replace)
    -- Jointure : Gold.recommendations.Id = Gold.alert_acknowledgements.Recommendation_Id

    -- ── Utilisateur ──────────────────────────────────────────────────────────
    Username            NVARCHAR(50)    NOT NULL,           -- qui a acquitté
    Role_Au_Moment      NVARCHAR(50)    NOT NULL,           -- rôle au moment de l'action

    -- ── Action ───────────────────────────────────────────────────────────────
    Action              NVARCHAR(20)    NOT NULL
                            CONSTRAINT CK_ACK_Action CHECK (Action IN (
                                'read',             -- alerte lue
                                'acknowledged',     -- prise en charge
                                'resolved',         -- problème résolu
                                'dismissed',        -- ignorée / faux positif
                                'escalated'         -- escaladée au niveau supérieur
                            )),
    Commentaire         NVARCHAR(500)   NULL,               -- note du manager

    -- ── Timing ───────────────────────────────────────────────────────────────
    Created_At          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_ACK   PRIMARY KEY (Id)
);

CREATE INDEX IX_ACK_Reco    ON Gold.alert_acknowledgements (Recommendation_Id, Created_At DESC);
CREATE INDEX IX_ACK_User    ON Gold.alert_acknowledgements (Username, Created_At DESC);

PRINT 'Table Gold.alert_acknowledgements créée.';
GO


-- =============================================================================
-- 8. Gold.audit_log
--    Traçabilité complète de toutes les actions utilisateurs dans l'application.
--    Obligatoire pour la conformité (RGPD, ISO 27001) — mentionné dans le CDC.
--    Lue par le profil DSI uniquement.
-- =============================================================================
IF OBJECT_ID('Gold.audit_log', 'U') IS NOT NULL
    DROP TABLE Gold.audit_log;
GO

CREATE TABLE Gold.audit_log (
    Id                  INT             IDENTITY(1,1)   NOT NULL,

    -- ── Qui ──────────────────────────────────────────────────────────────────
    Username            NVARCHAR(50)    NOT NULL,
    Role                NVARCHAR(50)    NOT NULL,

    -- ── Quoi ─────────────────────────────────────────────────────────────────
    Action              NVARCHAR(100)   NOT NULL,
    -- Exemples : 'LOGIN', 'VIEW_PAGE', 'TRIGGER_PIPELINE',
    --            'ACKNOWLEDGE_ALERT', 'EXPORT_DATA', 'LOGOUT'
    Resource            NVARCHAR(200)   NULL,               -- page ou endpoint accédé
    Resource_Id         NVARCHAR(100)   NULL,               -- ID de la ressource si applicable
    Details             NVARCHAR(MAX)   NULL,               -- JSON avec détails additionnels

    -- ── Résultat ─────────────────────────────────────────────────────────────
    Success             BIT             NOT NULL DEFAULT 1,
    Error_Message       NVARCHAR(500)   NULL,

    -- ── Contexte technique ───────────────────────────────────────────────────
    IP_Address          NVARCHAR(50)    NULL,
    User_Agent          NVARCHAR(500)   NULL,
    Session_Id          NVARCHAR(100)   NULL,

    Created_At          DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_AL    PRIMARY KEY (Id)
);

CREATE INDEX IX_AL_User     ON Gold.audit_log (Username, Created_At DESC);
CREATE INDEX IX_AL_Action   ON Gold.audit_log (Action,   Created_At DESC);
CREATE INDEX IX_AL_Date     ON Gold.audit_log (Created_At DESC);

PRINT 'Table Gold.audit_log créée.';
GO


-- =============================================================================
-- MISE À JOUR — Ajouter Source_Modele aux tables forecast existantes
--   (si pas déjà présente — idempotent)
-- =============================================================================

-- forecast_infra
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('Gold.forecast_infra') AND name = 'Source_Modele'
)
BEGIN
    ALTER TABLE Gold.forecast_infra
    ADD Source_Modele NVARCHAR(20) NOT NULL DEFAULT 'Prophet'
        CONSTRAINT CK_FI_Src CHECK (Source_Modele IN ('Prophet', 'ARIMA'));
    PRINT 'Colonne Source_Modele ajoutée à Gold.forecast_infra';
END

-- forecast_itsm
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('Gold.forecast_itsm') AND name = 'Source_Modele'
)
BEGIN
    ALTER TABLE Gold.forecast_itsm
    ADD Source_Modele NVARCHAR(20) NOT NULL DEFAULT 'Prophet'
        CONSTRAINT CK_FITSM_Src CHECK (Source_Modele IN ('Prophet', 'ARIMA'));
    PRINT 'Colonne Source_Modele ajoutée à Gold.forecast_itsm';
END

-- forecast_cybersec
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('Gold.forecast_cybersec') AND name = 'Source_Modele'
)
BEGIN
    ALTER TABLE Gold.forecast_cybersec
    ADD Source_Modele NVARCHAR(20) NOT NULL DEFAULT 'Prophet'
        CONSTRAINT CK_FCS_Src CHECK (Source_Modele IN ('Prophet', 'ARIMA'));
    PRINT 'Colonne Source_Modele ajoutée à Gold.forecast_cybersec';
END

-- forecast_itam
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('Gold.forecast_itam') AND name = 'Source_Modele'
)
BEGIN
    ALTER TABLE Gold.forecast_itam
    ADD Source_Modele NVARCHAR(20) NOT NULL DEFAULT 'ARIMA'
        CONSTRAINT CK_FITAM_Src CHECK (Source_Modele IN ('Prophet', 'ARIMA'));
    PRINT 'Colonne Source_Modele ajoutée à Gold.forecast_itam';
END

-- forecast_apps
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('Gold.forecast_apps') AND name = 'Source_Modele'
)
BEGIN
    ALTER TABLE Gold.forecast_apps
    ADD Source_Modele NVARCHAR(20) NOT NULL DEFAULT 'Prophet'
        CONSTRAINT CK_FA_Src CHECK (Source_Modele IN ('Prophet', 'ARIMA'));
    PRINT 'Colonne Source_Modele ajoutée à Gold.forecast_apps';
END

-- forecast_gouvernance
IF NOT EXISTS (
    SELECT 1 FROM sys.columns
    WHERE object_id = OBJECT_ID('Gold.forecast_gouvernance') AND name = 'Source_Modele'
)
BEGIN
    ALTER TABLE Gold.forecast_gouvernance
    ADD Source_Modele NVARCHAR(20) NOT NULL DEFAULT 'ARIMA'
        CONSTRAINT CK_FG_Src CHECK (Source_Modele IN ('Prophet', 'ARIMA'));
    PRINT 'Colonne Source_Modele ajoutée à Gold.forecast_gouvernance';
END
GO


-- =============================================================================
-- VÉRIFICATION FINALE — Inventaire complet du schéma Gold
-- =============================================================================
SELECT
    t.name          AS [Table Gold],
    (
        SELECT COUNT(*) FROM sys.columns c
        WHERE c.object_id = t.object_id
    )               AS [Nb colonnes],
    CASE t.name
        WHEN 'anomalies_if_details'     THEN 'ML — Détection IF (toutes obs)'
        WHEN 'anomalies_detected'       THEN 'ML — Anomalies IF actives'
        WHEN 'zscore_alerts'            THEN 'ML — Alertes Z-Score univariées   ← NOUVEAU'
        WHEN 'forecast_infra'           THEN 'ML — Prédictions Infrastructure'
        WHEN 'forecast_itsm'            THEN 'ML — Prédictions ITSM'
        WHEN 'forecast_cybersec'        THEN 'ML — Prédictions Cybersécurité'
        WHEN 'forecast_itam'            THEN 'ML — Prédictions ITAM'
        WHEN 'forecast_apps'            THEN 'ML — Prédictions Applications'
        WHEN 'forecast_gouvernance'     THEN 'ML — Prédictions Gouvernance'
        WHEN 'forecast_parc_auto'       THEN 'ML — Prédictions Parc Auto ARIMA ← NOUVEAU'
        WHEN 'forecast_maintenance'     THEN 'ML — Prédictions Maintenance ARIMA← NOUVEAU'
        WHEN 'prophet_alerts'           THEN 'ML — Alertes Prophet synthétiques'
        WHEN 'it_risk_score'            THEN 'ML — Score IT Risk composite'
        WHEN 'recommendations'          THEN 'App — Recommandations auto ML     ← NOUVEAU'
        WHEN 'users'                    THEN 'App — Utilisateurs JWT            ← NOUVEAU'
        WHEN 'pipeline_runs'            THEN 'App — Historique pipeline ML      ← NOUVEAU'
        WHEN 'alert_acknowledgements'   THEN 'App — Acquittements alertes       ← NOUVEAU'
        WHEN 'audit_log'                THEN 'App — Traçabilité RGPD/ISO27001   ← NOUVEAU'
        ELSE '—'
    END             AS [Rôle]
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name = 'Gold'
ORDER BY
    CASE
        WHEN t.name LIKE 'anomalies%'   THEN 1
        WHEN t.name LIKE 'zscore%'      THEN 2
        WHEN t.name LIKE 'forecast%'    THEN 3
        WHEN t.name LIKE 'prophet%'     THEN 4
        WHEN t.name = 'it_risk_score'   THEN 5
        WHEN t.name = 'recommendations' THEN 6
        WHEN t.name = 'users'           THEN 7
        WHEN t.name = 'pipeline_runs'   THEN 8
        ELSE 9
    END,
    t.name;
GO

PRINT '=== Schéma Gold complet — 18 tables au total. ===';
GO