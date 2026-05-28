import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)

DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_PORT = os.getenv("DB_PORT", "1433")
DB_NAME = os.getenv("DB_NAME", "Dashboard360_Bronze")
DB_USER = os.getenv("DB_USER", "sa")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Admin1234")

# FIX: Validation au démarrage — évite un crash non-descriptif plus tard
if not DB_USER or not DB_PASSWORD:
    logger.warning(
        "⚠️  DB_USER ou DB_PASSWORD non définis dans .env. "
        "La connexion SQL Server échouera."
    )

# FIX: Singleton engine — ne pas recréer à chaque appel (fuite de connexions)
_engine = None


def get_db_engine():
    global _engine
    if _engine is not None:
        return _engine

    connection_string = (
        f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER},{DB_PORT}/"
        f"{DB_NAME}?driver={DB_DRIVER.replace(' ', '+')}"
    )

    try:
        _engine = create_engine(
            connection_string,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # FIX: détecte les connexions mortes automatiquement
            echo=False,
        )
        logger.info(f"✅ SQL Server engine créé: {DB_SERVER}/{DB_NAME}")
        return _engine
    except Exception as e:
        logger.error(f"❌ Impossible de créer l'engine SQL Server: {e}")
        raise