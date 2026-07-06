"""
connection.py
SQL Server connection using pymssql.
Unicode/NVARCHAR handled natively by SQL Server.
"""
import pymssql
import os
from dotenv import load_dotenv
from app.logger import get_logger

# Load standard .env file
load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "1433")),
    "user": os.getenv("DB_USER", "SA"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "qatar_boe"),
}


logger = get_logger("db.connection")


def create_raw_connection():
    return pymssql.connect(
        server=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset="UTF-8",
    )

def get_connection():
    try:
        conn = create_raw_connection()
        logger.debug("DB connection established")
        return conn
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        raise