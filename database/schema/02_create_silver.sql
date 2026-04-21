-- ============================================================
--  DASHBOARD 360 NOVEC — Silver Layer V2
--  Fichier  : 02_create_silver.sql
--  Objectif : Vues d'agrégation Bronze → Silver
--             Couche d'abstraction pour Power BI & ML
--  Ordre    : Respecte les dépendances causales de run_simulation.py
-- ============================================================

-- Création du schéma Silver si inexistant
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'Silver')
    EXEC('CREATE SCHEMA Silver');
GO

-- ============================================================
-- [1/8] INFRASTRUCTURE IT
--       Agrégation horaire → journalière par serveur
--       Expose : saturation, disponibilité, anomalies
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_infrastructure_kpis AS
SELECT
    CAST(Timestamp AS DATE)             AS DateKey,
    ServerName,

    -- Charge moyenne
    AVG(CPU_Usage_Pct)                  AS CPU_Moyen_Pct,
    MAX(CPU_Usage_Pct)                  AS CPU_Max_Pct,
    AVG(RAM_Usage_Pct)                  AS RAM_Moyen_Pct,
    MAX(RAM_Usage_Pct)                  AS RAM_Max_Pct,
    AVG(Disk_Usage_Pct)                 AS Disk_Moyen_Pct,
    MAX(Disk_Usage_Pct)                 AS Disk_Max_Pct,   -- trend saturation disque

    -- Réseau
    AVG(Network_Latency_ms)             AS Latence_Moyenne_ms,
    MAX(Network_Latency_ms)             AS Latence_Max_ms,

    -- Disponibilité
    SUM(CASE WHEN Uptime_Status = 1 THEN 1 ELSE 0 END) * 100.0
        / COUNT(*)                      AS Disponibilite_Pct,

    -- Résilience
    AVG(MTBF_Hours)                     AS MTBF_Moyen_Hours,
    AVG(MTTR_Infra_Hours)               AS MTTR_Moyen_Hours,
    AVG(Backup_Coverage_Pct)            AS Backup_Coverage_Moyen_Pct,
    SUM(CAST(Backup_Success AS INT))    AS Backup_Success_Count,

    -- Anomalies (vérité terrain pour Isolation Forest)
    SUM(CAST(Is_Anomaly AS INT))        AS Nb_Anomalies,
    COUNT(*)                            AS Nb_Mesures,
    SUM(CAST(Is_Anomaly AS INT)) * 100.0
        / NULLIF(COUNT(*), 0)           AS Taux_Anomalie_Pct

FROM Bronze.staging_infrastructure
-- FROM Bronze.real_zabbix_data        -- ← décommenter lors de la migration réelle
GROUP BY
    CAST(Timestamp AS DATE),
    ServerName;
GO

-- ============================================================
-- [2/8] ITSM / SERVICE DESK
--       Granularité journalière → KPIs opérationnels
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_itsm_kpis AS
SELECT
    CAST(Date AS DATE)                  AS DateKey,

    -- Volume
    SUM(Tickets_P1_Critique)            AS Total_P1,
    SUM(Tickets_P2_Majeur)              AS Total_P2,
    SUM(Tickets_P3_Mineur)              AS Total_P3,
    SUM(Volume_Total)                   AS Volume_Total,
    SUM(Backlog_Non_Resolus)            AS Backlog_Total,

    -- Performance
    AVG(SLA_Respect_Pct)                AS SLA_Moyen_Pct,
    AVG(FCR_Pct)                        AS FCR_Moyen_Pct,    -- First Call Resolution
    AVG(MTTR_Hours)                     AS MTTR_Moyen_Hours,

    -- Satisfaction
    AVG(CSAT_Score)                     AS CSAT_Moyen,

    -- Ratio criticité (utile pour Z-Score alerting)
    SUM(Tickets_P1_Critique) * 100.0
        / NULLIF(SUM(Volume_Total), 0)  AS Pct_Tickets_P1

FROM Bronze.staging_itsm_tickets
GROUP BY CAST(Date AS DATE);
GO

-- ============================================================
-- [3/8] CYBERSÉCURITÉ
--       KPIs journaliers + conformité
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_cyber_kpis AS
SELECT
    CAST(Date AS DATE)                  AS DateKey,

    -- Incidents
    SUM(Incidents_Critiques)            AS Nb_Incidents_Critiques,
    AVG(MTTD_Hours)                     AS MTTD_Moyen_Hours,      -- Mean Time to Detect

    -- Vulnérabilités
    SUM(Vulnerabilites_Non_Patchees)    AS Total_Vuln_Non_Patchees,
    AVG(Systemes_Patches_Pct)           AS Systemes_Patches_Moyen_Pct,

    -- Comportement utilisateurs
    AVG(Taux_Adoption_MFA_Pct)          AS MFA_Adoption_Pct,
    AVG(Taux_Clic_Phishing_Pct)         AS Taux_Phishing_Moyen_Pct,

    -- Conformité réglementaire
    AVG(Conformite_RGPD_Pct)            AS RGPD_Conformite_Pct

FROM Bronze.staging_cybersecurity
GROUP BY CAST(Date AS DATE);
GO

-- ============================================================
-- [4/8] APPLICATIONS & BI
--       Performance applicative journalière par application
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_applications_kpis AS
SELECT
    CAST(Date AS DATE)                  AS DateKey,
    Application_Name,

    -- Performance
    AVG(Temps_Reponse_Moyen_ms)         AS Temps_Reponse_Moyen_ms,
    MAX(Temps_Reponse_Moyen_ms)         AS Temps_Reponse_Max_ms,

    -- Disponibilité
    AVG(Disponibilite_App_Pct)          AS Disponibilite_Pct,

    -- Qualité
    SUM(Bugs_Critiques_Prod)            AS Nb_Bugs_Critiques,
    AVG(Qualite_Donnees_Score_Pct)      AS Qualite_Donnees_Pct,

    -- Adoption BI
    AVG(Adoption_PowerBI_Pct)           AS Adoption_PowerBI_Pct

FROM Bronze.staging_applications
GROUP BY CAST(Date AS DATE), Application_Name;
GO

-- ============================================================
-- [5/8] ITAM — ACTIFS IT
--       Granularité mensuelle (pas d'agrégation supplémentaire)
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_itam_kpis AS
SELECT
    CAST(Mois AS DATE)                  AS DateKey,

    -- Parc
    SUM(Total_Postes_Actifs)            AS Total_Postes,
    AVG(Vetuste_Plus_4ans_Pct)           AS Vetuste_Moyen_Pct,

    -- Financier
    AVG(TCO_Annuel_Par_Poste_MAD)       AS TCO_Moyen_Par_Poste_MAD,
    SUM(Total_Postes_Actifs * TCO_Annuel_Par_Poste_MAD)
                                        AS TCO_Total_MAD,       -- pour régression

    -- Conformité
    AVG(Conformite_Licences_Pct)        AS Conformite_Licences_Pct,
    SUM(Licences_Inutilisees)           AS Total_Licences_Inutilisees,

    -- Service
    AVG(Delai_Mise_Dispo_Jours)         AS Delai_Mise_Dispo_Moyen_Jours,
    AVG(Taux_Inventaire_CMDB_Pct)       AS CMDB_Couverture_Pct

FROM Bronze.staging_itam
GROUP BY CAST(Mois AS DATE);
GO

-- ============================================================
-- [6/8] PARC AUTOMOBILE
--       KPIs journaliers de flotte
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_parc_auto_kpis AS
SELECT
    CAST(Date AS DATE)                  AS DateKey,

    -- Flotte
    MAX(Flotte_Totale)                  AS Flotte_Totale,
    SUM(Vehicules_Disponibles)          AS Vehicules_Disponibles,
    AVG(Disponibilite_Vehicules_Pct)    AS Disponibilite_Pct,

    -- Sinistralité
    SUM(Nbre_Sinistres_Jour)            AS Nb_Sinistres,
    AVG(Taux_Sinistralite_Pct)          AS Taux_Sinistralite_Pct,

    -- Consommation & Coût
    SUM(Consommation_Carburant_Total_L) AS Conso_Totale_L,
    AVG(Conso_L_100km)                  AS Conso_Moyenne_L100km,
    AVG(TCO_Par_Vehicule_MAD)           AS TCO_Moyen_Par_Vehicule_MAD

FROM Bronze.staging_parc_auto
GROUP BY CAST(Date AS DATE);
GO

-- ============================================================
-- [7/8] MAINTENANCE
--       Granularité mensuelle
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_maintenance_kpis AS
SELECT
    CAST(Mois AS DATE)                  AS DateKey,

    -- Volume d'ordres
    SUM(Total_Ordres_Travail)           AS Total_OT,
    SUM(Interventions_Preventives)      AS OT_Preventif,
    SUM(Interventions_Correctives)      AS OT_Correctif,

    -- Ratios
    AVG(Ratio_Preventif_Pct)            AS Ratio_Preventif_Pct,
    AVG(Taux_Realisation_Preventif_Pct) AS Taux_Realisation_Preventif_Pct,

    -- Disponibilité pièces (impact sur préventif)
    SUM(Ruptures_Stock_Pieces)          AS Total_Ruptures_Stock,

    -- Indicateur dérivé : efficacité maintenance
    SUM(Interventions_Preventives) * 100.0
        / NULLIF(SUM(Total_Ordres_Travail), 0)
                                        AS Pct_Preventif_Realise

FROM Bronze.staging_maintenance
GROUP BY CAST(Mois AS DATE);
GO

-- ============================================================
-- [8/8] GOUVERNANCE & STRATÉGIE
--       Granularité mensuelle par département
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_gouvernance_kpis AS
SELECT
    CAST(Mois AS DATE)                  AS DateKey,
    Departement,

    -- Budget
    SUM(Budget_Alloue_MAD)              AS Budget_Alloue_MAD,
    SUM(Budget_Consomme_MAD)            AS Budget_Consomme_MAD,
    AVG(Ecart_Budget_Pct)               AS Ecart_Budget_Moyen_Pct,

    -- Performance projets
    AVG(ROI_Projets_Pct)                AS ROI_Moyen_Pct,
    AVG(Projets_Livres_A_Temps_Pct)     AS Projets_A_Temps_Pct,

    -- Digital & IT
    AVG(Taux_Adoption_Digital_Pct)      AS Adoption_Digital_Pct,
    AVG(Satisfaction_Globale_IT)        AS CSAT_IT_Moyen,          -- alimenté par ITSM
    AVG(Cout_IT_Par_Employe_MAD)        AS Cout_IT_Par_Employe_MAD

FROM Bronze.staging_gouvernance
GROUP BY CAST(Mois AS DATE), Departement;
GO

-- ============================================================
-- VUE CONSOLIDÉE — IT Risk Score (entrée Gold Layer)
--   Agrège les KPIs critiques de tous les domaines
--   sur une base journalière pour le scoring ML
-- ============================================================
CREATE OR ALTER VIEW Silver.vw_daily_risk_inputs AS
SELECT
    d.DateKey,

    -- Infrastructure
    COALESCE(i.Taux_Anomalie_Pct,   0)  AS Infra_Taux_Anomalie_Pct,
    COALESCE(i.Disponibilite_Pct,   100) AS Infra_Dispo_Pct,
    COALESCE(i.CPU_Moyen_Pct,       0)  AS Infra_CPU_Moyen_Pct,
    COALESCE(i.Disk_Max_Pct,        0)  AS Infra_Disk_Max_Pct,

    -- ITSM
    COALESCE(t.SLA_Moyen_Pct,       100) AS ITSM_SLA_Pct,
    COALESCE(t.Total_P1,            0)  AS ITSM_Tickets_P1,
    COALESCE(t.CSAT_Moyen,          5)  AS ITSM_CSAT,

    -- Cybersécurité
    COALESCE(c.Nb_Incidents_Critiques, 0) AS Cyber_Incidents_Critiques,
    COALESCE(c.Systemes_Patches_Moyen_Pct, 100) AS Cyber_Patch_Pct,
    COALESCE(c.RGPD_Conformite_Pct, 100) AS Cyber_RGPD_Pct,

    -- Applications
    COALESCE(a.Disponibilite_Pct,   100) AS App_Dispo_Pct,
    COALESCE(a.Nb_Bugs_Critiques,   0)  AS App_Bugs_Critiques,

    -- Parc Auto
    COALESCE(p.Disponibilite_Pct,   100) AS Fleet_Dispo_Pct,
    COALESCE(p.Taux_Sinistralite_Pct, 0) AS Fleet_Sinistralite_Pct

FROM (
    -- Spine de dates : toutes les dates présentes dans le dataset
    SELECT DISTINCT CAST(Timestamp AS DATE) AS DateKey
    FROM Bronze.staging_infrastructure
) d
LEFT JOIN (
    SELECT DateKey,
           AVG(Taux_Anomalie_Pct)  AS Taux_Anomalie_Pct,
           AVG(Disponibilite_Pct)  AS Disponibilite_Pct,
           AVG(CPU_Moyen_Pct)      AS CPU_Moyen_Pct,
           MAX(Disk_Max_Pct)       AS Disk_Max_Pct
    FROM Silver.vw_infrastructure_kpis
    GROUP BY DateKey
) i ON d.DateKey = i.DateKey
LEFT JOIN Silver.vw_itsm_kpis       t ON d.DateKey = t.DateKey
LEFT JOIN Silver.vw_cyber_kpis      c ON d.DateKey = c.DateKey
LEFT JOIN (
    SELECT DateKey,
           AVG(Disponibilite_Pct)  AS Disponibilite_Pct,
           SUM(Nb_Bugs_Critiques)  AS Nb_Bugs_Critiques
    FROM Silver.vw_applications_kpis
    GROUP BY DateKey
) a ON d.DateKey = a.DateKey
LEFT JOIN Silver.vw_parc_auto_kpis  p ON d.DateKey = p.DateKey;
GO

-- ============================================================
-- INDEXES DE SUPPORT SUR LES TABLES BRONZE
--   (améliorent les performances des vues Silver ci-dessus)
-- ============================================================

-- Infrastructure : accès par date (agrégation journalière)
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('Bronze.staging_infrastructure')
      AND name = 'IX_infra_timestamp_date'
)
    CREATE NONCLUSTERED INDEX IX_infra_timestamp_date
        ON Bronze.staging_infrastructure (Timestamp)
        INCLUDE (ServerName, CPU_Usage_Pct, RAM_Usage_Pct,
                 Disk_Usage_Pct, Uptime_Status, Is_Anomaly);
GO

-- ITSM : accès par date
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('Bronze.staging_itsm_tickets')
      AND name = 'IX_itsm_date'
)
    CREATE NONCLUSTERED INDEX IX_itsm_date
        ON Bronze.staging_itsm_tickets (Date)
        INCLUDE (Volume_Total, Tickets_P1_Critique, SLA_Respect_Pct, CSAT_Score);
GO

-- Cybersécurité : accès par date
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('Bronze.staging_cybersecurity')
      AND name = 'IX_cyber_date'
)
    CREATE NONCLUSTERED INDEX IX_cyber_date
        ON Bronze.staging_cybersecurity (Date)
        INCLUDE (Incidents_Critiques, Systemes_Patches_Pct, Conformite_RGPD_Pct);
GO

-- Applications : accès par date + application
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID('Bronze.staging_applications')
      AND name = 'IX_apps_date_appname'
)
    CREATE NONCLUSTERED INDEX IX_apps_date_appname
        ON Bronze.staging_applications (Date, Application_Name)
        INCLUDE (Disponibilite_App_Pct, Temps_Reponse_Moyen_ms, Bugs_Critiques_Prod);
GO

-- ============================================================
-- VÉRIFICATION RAPIDE (à exécuter après déploiement)
-- ============================================================
/*
SELECT TOP 5 * FROM Silver.vw_infrastructure_kpis  ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_itsm_kpis             ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_cyber_kpis            ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_applications_kpis     ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_itam_kpis             ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_parc_auto_kpis        ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_maintenance_kpis      ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_gouvernance_kpis      ORDER BY DateKey DESC;
SELECT TOP 5 * FROM Silver.vw_daily_risk_inputs     ORDER BY DateKey DESC;
*/