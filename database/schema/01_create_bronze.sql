-- =========================================================================
-- SCRIPT DE CREATION : SCHEMA BRONZE - DASHBOARD 360 NOVEC (V2)
-- Description : Tables enrichies couvrant les 55 KPIs du référentiel
-- SGBD : SQL Server 2022
-- =========================================================================

-- 1. Création du Schéma métier si inexistant
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'Bronze')
BEGIN
    EXEC('CREATE SCHEMA Bronze');
END
GO

-- =========================================================================
-- 2. TABLES DE DIMENSIONS (Référentiels / Foreign Keys)
-- =========================================================================

-- Dimension Calendrier Universel
IF OBJECT_ID('Bronze.Dim_Date', 'U') IS NULL
CREATE TABLE Bronze.Dim_Date (
    DateKey DATE PRIMARY KEY,
    IS_Weekend BIT
);
GO

-- Dimension Serveurs
IF OBJECT_ID('Bronze.Dim_Server', 'U') IS NULL
CREATE TABLE Bronze.Dim_Server (
    ServerName VARCHAR(50) PRIMARY KEY,
    Notes VARCHAR(255) NULL
);
GO

-- Dimension Applications
IF OBJECT_ID('Bronze.Dim_Application', 'U') IS NULL
CREATE TABLE Bronze.Dim_Application (
    Application_Name VARCHAR(50) PRIMARY KEY,
    Notes VARCHAR(255) NULL
);
GO

-- Dimension Départements
IF OBJECT_ID('Bronze.Dim_Department', 'U') IS NULL
CREATE TABLE Bronze.Dim_Department (
    Departement VARCHAR(50) PRIMARY KEY
);
GO

-- =========================================================================
-- 3. TABLES DE FAITS (Domaines) — 55 KPIs
-- =========================================================================

-- A. INFRASTRUCTURE IT (6 KPIs + métriques de support)
IF OBJECT_ID('Bronze.staging_infrastructure', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_infrastructure;
GO
CREATE TABLE Bronze.staging_infrastructure (
    LogID INT IDENTITY(1,1) PRIMARY KEY,
    Timestamp DATETIME2 NOT NULL,
    ServerName VARCHAR(50) NOT NULL,
    CPU_Usage_Pct FLOAT,
    RAM_Usage_Pct FLOAT,
    Disk_Usage_Pct FLOAT,
    Network_Latency_ms FLOAT,
    Backup_Success INT,
    Backup_Coverage_Pct FLOAT,
    Uptime_Status INT,
    MTBF_Hours FLOAT,
    MTTR_Infra_Hours FLOAT,
    Is_Anomaly INT DEFAULT 0,
    CONSTRAINT FK_Infra_Server FOREIGN KEY (ServerName) REFERENCES Bronze.Dim_Server(ServerName)
);
GO

-- B. ITSM / Service Desk (5 KPIs)
IF OBJECT_ID('Bronze.staging_itsm_tickets', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_itsm_tickets;
GO
CREATE TABLE Bronze.staging_itsm_tickets (
    TicketLogID INT IDENTITY(1,1) PRIMARY KEY,
    Date DATE NOT NULL,
    Tickets_P1_Critique INT,
    Tickets_P2_Majeur INT,
    Tickets_P3_Mineur INT,
    Volume_Total INT,
    SLA_Respect_Pct FLOAT,
    MTTR_Hours FLOAT,
    FCR_Pct FLOAT,
    Backlog_Non_Resolus INT,
    CSAT_Score FLOAT,
    CONSTRAINT FK_ITSM_Date FOREIGN KEY (Date) REFERENCES Bronze.Dim_Date(DateKey)
);
GO

-- C. CYBERSÉCURITÉ & CONFORMITÉ (6 KPIs)
IF OBJECT_ID('Bronze.staging_cybersecurity', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_cybersecurity;
GO
CREATE TABLE Bronze.staging_cybersecurity (
    CyberLogID INT IDENTITY(1,1) PRIMARY KEY,
    Date DATE NOT NULL,
    Incidents_Critiques INT,
    MTTD_Hours FLOAT,
    Vulnerabilites_Non_Patchees INT,
    Systemes_Patches_Pct FLOAT,
    Taux_Adoption_MFA_Pct FLOAT,
    Taux_Clic_Phishing_Pct FLOAT,
    Conformite_RGPD_Pct FLOAT,
    CONSTRAINT FK_Cyber_Date FOREIGN KEY (Date) REFERENCES Bronze.Dim_Date(DateKey)
);
GO

-- D. GOUVERNANCE & STRATÉGIE IT (6 KPIs)
IF OBJECT_ID('Bronze.staging_gouvernance', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_gouvernance;
GO
CREATE TABLE Bronze.staging_gouvernance (
    GouvLogID INT IDENTITY(1,1) PRIMARY KEY,
    Mois DATE NOT NULL,
    Departement VARCHAR(50) NOT NULL,
    Budget_Alloue_MAD FLOAT,
    Budget_Consomme_MAD FLOAT,
    Ecart_Budget_Pct FLOAT,
    ROI_Projets_Pct FLOAT,
    Projets_Livres_A_Temps_Pct FLOAT,
    Taux_Adoption_Digital_Pct FLOAT,
    Satisfaction_Globale_IT FLOAT,
    Cout_IT_Par_Employe_MAD FLOAT,
    CONSTRAINT FK_Gouv_Date FOREIGN KEY (Mois) REFERENCES Bronze.Dim_Date(DateKey),
    CONSTRAINT FK_Gouv_Dept FOREIGN KEY (Departement) REFERENCES Bronze.Dim_Department(Departement)
);
GO

-- E. ITAM / GESTION DES ACTIFS (5 KPIs)
IF OBJECT_ID('Bronze.staging_itam', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_itam;
GO
CREATE TABLE Bronze.staging_itam (
    ItamLogID INT IDENTITY(1,1) PRIMARY KEY,
    Mois DATE NOT NULL,
    Total_Postes_Actifs INT,
    Vetuste_Plus_4ans_Pct FLOAT,
    TCO_Annuel_Par_Poste_MAD FLOAT,
    Conformite_Licences_Pct FLOAT,
    Delai_Mise_Dispo_Jours FLOAT,
    Taux_Inventaire_CMDB_Pct FLOAT,
    Licences_Inutilisees INT,
    CONSTRAINT FK_ITAM_Date FOREIGN KEY (Mois) REFERENCES Bronze.Dim_Date(DateKey)
);
GO

-- F. PARC AUTOMOBILE (4 KPIs)
IF OBJECT_ID('Bronze.staging_parc_auto', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_parc_auto;
GO
CREATE TABLE Bronze.staging_parc_auto (
    FleetLogID INT IDENTITY(1,1) PRIMARY KEY,
    Date DATE NOT NULL,
    Flotte_Totale INT,
    Vehicules_Disponibles INT,
    Disponibilite_Vehicules_Pct FLOAT,
    Nbre_Sinistres_Jour INT,
    Taux_Sinistralite_Pct FLOAT,
    Consommation_Carburant_Total_L FLOAT,
    Conso_L_100km FLOAT,
    TCO_Par_Vehicule_MAD FLOAT,
    CONSTRAINT FK_Fleet_Date FOREIGN KEY (Date) REFERENCES Bronze.Dim_Date(DateKey)
);
GO

-- G. MAINTENANCE (KPIs partagés avec Parc Auto)
IF OBJECT_ID('Bronze.staging_maintenance', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_maintenance;
GO
CREATE TABLE Bronze.staging_maintenance (
    MaintLogID INT IDENTITY(1,1) PRIMARY KEY,
    Mois DATE NOT NULL,
    Total_Ordres_Travail INT,
    Interventions_Preventives INT,
    Interventions_Correctives INT,
    Ratio_Preventif_Pct FLOAT,
    Taux_Realisation_Preventif_Pct FLOAT,
    Ruptures_Stock_Pieces INT,
    CONSTRAINT FK_Maintenance_Date FOREIGN KEY (Mois) REFERENCES Bronze.Dim_Date(DateKey)
);
GO

-- H. APPLICATIONS & BI/DATA (4 KPIs)
IF OBJECT_ID('Bronze.staging_applications', 'U') IS NOT NULL
    DROP TABLE Bronze.staging_applications;
GO
CREATE TABLE Bronze.staging_applications (
    AppLogID INT IDENTITY(1,1) PRIMARY KEY,
    Date DATE NOT NULL,
    Application_Name VARCHAR(50) NOT NULL,
    Temps_Reponse_Moyen_ms FLOAT,
    Disponibilite_App_Pct FLOAT,
    Bugs_Critiques_Prod INT,
    Qualite_Donnees_Score_Pct FLOAT,
    Adoption_PowerBI_Pct FLOAT,
    CONSTRAINT FK_App_Date FOREIGN KEY (Date) REFERENCES Bronze.Dim_Date(DateKey),
    CONSTRAINT FK_App_Name FOREIGN KEY (Application_Name) REFERENCES Bronze.Dim_Application(Application_Name)
);
GO

-- =========================================================================
-- 4. INDEXES POUR LA PERFORMANCE DES REQUETES ANALYTIQUES
-- =========================================================================
CREATE NONCLUSTERED INDEX IX_Infra_Timestamp ON Bronze.staging_infrastructure(Timestamp);
CREATE NONCLUSTERED INDEX IX_Infra_Server ON Bronze.staging_infrastructure(ServerName);
CREATE NONCLUSTERED INDEX IX_Infra_Anomaly ON Bronze.staging_infrastructure(Is_Anomaly) WHERE Is_Anomaly = 1;
CREATE NONCLUSTERED INDEX IX_ITSM_Date ON Bronze.staging_itsm_tickets(Date);
CREATE NONCLUSTERED INDEX IX_Cyber_Date ON Bronze.staging_cybersecurity(Date);
CREATE NONCLUSTERED INDEX IX_Apps_Date ON Bronze.staging_applications(Date);
CREATE NONCLUSTERED INDEX IX_Fleet_Date ON Bronze.staging_parc_auto(Date);
GO

PRINT '✅ Schéma Bronze V2 créé avec succès — 55 KPIs couverts.';
GO
