"""
Script d'initialisation de la base de données SQL Server.
Exécute les fichiers SQL du dossier database/schema/ dans l'ordre numérique.
Puis insère les données de référence (seeds) dans les tables de dimensions.

Usage : python database/init_db.py
"""
import os
import sys
import pyodbc
from dotenv import load_dotenv

# Charge les variables d'environnement depuis le fichier .env (s'il existe)
# On remonte d'un dossier pour trouver le .env à la racine
# ou load_dotenv() le trouve s'il est lancé depuis la racine
load_dotenv()

# --- Configuration (identique à data_simulation/config.py) ---
DB_SERVER = os.getenv("DB_SERVER", r"HT-LOQ\MSSQLSERVER2022")
DB_DATABASE = os.getenv("DB_DATABASE", "Dashboard360_Bronze")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Admin1234")

CONN_STRING = f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_DATABASE};UID={DB_USER};PWD={DB_PASSWORD};TrustServerCertificate=yes"

# Chemins
SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "schema")
SEEDS_DIR = os.path.join(os.path.dirname(__file__), "seeds")

def execute_sql_file(cursor, filepath):
    """Lit un fichier .sql et exécute chaque bloc séparé par GO."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # SQL Server utilise 'GO' comme séparateur de batch
    # pyodbc ne comprend pas 'GO', il faut donc découper manuellement
    batches = content.split('\nGO')
    
    for i, batch in enumerate(batches):
        batch = batch.strip()
        if batch and not batch.startswith('--'):
            try:
                cursor.execute(batch)
                cursor.commit()
            except Exception as e:
                print(f"    [!] Erreur batch {i+1}: {e}")

def drop_all_staging_tables(cursor):
    """Supprime toutes les tables staging Bronze AVANT de recréer le schéma."""
    tables_to_drop = [
        'Bronze.staging_applications',
        'Bronze.staging_maintenance',
        'Bronze.staging_parc_auto',
        'Bronze.staging_itam',
        'Bronze.staging_gouvernance',
        'Bronze.staging_cybersecurity',
        'Bronze.staging_itsm_tickets',
        'Bronze.staging_infrastructure',
    ]
    for table in tables_to_drop:
        try:
            cursor.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL DROP TABLE {table}")
            cursor.commit()
            print(f"    DROP {table} OK")
        except Exception as e:
            print(f"    DROP {table} skip: {e}")

def run_schema_scripts(cursor):
    """Exécute tous les fichiers SQL du dossier schema/ dans l'ordre."""
    if not os.path.exists(SCHEMA_DIR):
        print(f"[!] Dossier introuvable : {SCHEMA_DIR}")
        return
    
    # Supprime les anciennes tables pour permettre la recréation V2
    print("  Nettoyage des anciennes tables...")
    drop_all_staging_tables(cursor)
    
    sql_files = sorted([f for f in os.listdir(SCHEMA_DIR) if f.endswith('.sql')])
    
    if not sql_files:
        print("  Aucun fichier SQL trouvé dans schema/")
        return
    
    for filename in sql_files:
        filepath = os.path.join(SCHEMA_DIR, filename)
        print(f"  Execution de {filename}...")
        execute_sql_file(cursor, filepath)
        print(f"  OK : {filename}")

def run_seeds(cursor):
    """Insère les données de référence dans les tables de dimensions."""
    print("\n[2/3] Insertion des Seeds (Dimensions)...")
    
    seeds = [
        # Dim_Server
        ("IF NOT EXISTS (SELECT 1 FROM Bronze.Dim_Server WHERE ServerName='SRV-ERP-01') "
         "INSERT INTO Bronze.Dim_Server (ServerName, Notes) VALUES "
         "('SRV-ERP-01', 'Serveur ERP Principal'), "
         "('SRV-DB-01', 'Base de données SQL'), "
         "('SRV-WEB-PME', 'Portail Web Novec')"),
        
        # Dim_Application
        ("IF NOT EXISTS (SELECT 1 FROM Bronze.Dim_Application WHERE Application_Name='App_SIRH') "
         "INSERT INTO Bronze.Dim_Application (Application_Name, Notes) VALUES "
         "('App_SIRH', 'Ressources Humaines'), "
         "('App_Compta', 'Logiciel Comptable'), "
         "('App_Core_Metier', 'Outil interne critique')"),
        
        # Dim_Department
        ("IF NOT EXISTS (SELECT 1 FROM Bronze.Dim_Department WHERE Departement='IT-Operations') "
         "INSERT INTO Bronze.Dim_Department (Departement) VALUES "
         "('IT-Operations'), ('Cybersecurité'), ('Data'), ('Projets')"),
        
        # Dim_Date (365 jours en arrière + 30 jours en avant)
        """
        DECLARE @d DATE = DATEADD(DAY, -400, GETDATE());
        DECLARE @end DATE = DATEADD(DAY, 30, GETDATE());
        WHILE @d <= @end
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM Bronze.Dim_Date WHERE DateKey = @d)
                INSERT INTO Bronze.Dim_Date (DateKey, IS_Weekend)
                VALUES (@d, CASE WHEN DATEPART(dw, @d) IN (1,7) THEN 1 ELSE 0 END);
            SET @d = DATEADD(DAY, 1, @d);
        END
        """
    ]
    
    for i, seed_sql in enumerate(seeds):
        try:
            cursor.execute(seed_sql.strip())
            cursor.commit()
            print(f"  OK : Seed {i+1}/4")
        except Exception as e:
            print(f"  [!] Seed {i+1} erreur : {e}")

def main():
    print("=" * 60)
    print("DATABASE INIT — Dashboard 360 Novec")
    print("=" * 60)
    print(f"Serveur : {DB_SERVER}")
    print(f"Base    : {DB_DATABASE}")
    print()
    
    # Connexion
    try:
        conn = pyodbc.connect(CONN_STRING, autocommit=False)
        cursor = conn.cursor()
        print("[OK] Connexion SQL Server etablie.\n")
    except Exception as e:
        print(f"[ERREUR] Connexion impossible : {e}")
        sys.exit(1)
    
    # Étape 1 : Schéma
    print("[1/3] Execution des scripts schema/...")
    run_schema_scripts(cursor)
    
    # Étape 2 : Seeds
    run_seeds(cursor)
    
    # Étape 3 : Vérification
    print("\n[3/3] Verification...")
    tables_check = [
        'Bronze.Dim_Date', 'Bronze.Dim_Server', 'Bronze.Dim_Application', 'Bronze.Dim_Department',
        'Bronze.staging_infrastructure', 'Bronze.staging_itsm_tickets',
        'Bronze.staging_cybersecurity', 'Bronze.staging_gouvernance',
        'Bronze.staging_itam', 'Bronze.staging_parc_auto',
        'Bronze.staging_maintenance', 'Bronze.staging_applications'
    ]
    for table in tables_check:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table:45s} | {count:>6} lignes")
        except Exception as e:
            print(f"  {table:45s} | ERREUR : {e}")
    
    cursor.close()
    conn.close()
    print("\n[OK] Initialisation terminee avec succes.")

if __name__ == '__main__':
    main()
