import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION SQL SERVER 2022 ---
# Remplacez les valeurs par celles de votre base SQL Server locale
DB_SERVER = os.getenv("DB_SERVER", r"HT-LOQ\MSSQLSERVER2022") # Utilisation du 'r' pour lire le '\' correctement
DB_DATABASE = os.getenv("DB_DATABASE", "Dashboard360_Bronze")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server") # Assurez-vous d'avoir ce driver installé
DB_USER = os.getenv("DB_USER", "sa") # Authentification SQL
DB_PASSWORD = os.getenv("DB_PASSWORD", "Admin1234")

# Option 1: Authentification Windows (Integrated Security=True)
# (COMMENTÉE PAR DÉFAUT)
# CONNECTION_STRING = f"mssql+pyodbc://@{DB_SERVER}/{DB_DATABASE}?driver={DB_DRIVER.replace(' ', '+')}&Trusted_Connection=yes"

# Option 2: Authentification SQL Server (Identifiant / Mot de passe)
# (ACTIVÉE MAINTENANT avec TrustServerCertificate)
CONNECTION_STRING = f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_DATABASE}?driver={DB_DRIVER.replace(' ', '+')}&TrustServerCertificate=yes"

# Dossier de fallback en cas d'export CSV
OUTPUT_DIR = "datasets_v1"

def get_db_engine():
    """Crée et retourne le moteur de connexion SQLAlchemy pour SQL Server"""
    try:
        engine = create_engine(CONNECTION_STRING, echo=False)
        return engine
    except Exception as e:
        print(f"Erreur lors de la création du moteur SQL Server : {e}")
        return None
