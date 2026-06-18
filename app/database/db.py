# db.py (completo corregido)

import logging
import os

import pyodbc
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings
from app.models import Base

logger = logging.getLogger(__name__)

os.environ['SQLALCHEMY_ECHO'] = 'False'
os.environ['SQLALCHEMY_VERBOSE'] = 'False'

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.orm").setLevel(logging.WARNING)

engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_direct_connection():
    try:
        if settings.DATABASE_TYPE.lower() == "sqlserver":
            conn = pyodbc.connect(
                f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={settings.DB_SERVER};DATABASE={settings.DB_NAME};UID={settings.DB_USER};PWD={settings.DB_PASSWORD};TrustServerCertificate=yes'
            )
            return conn
        elif settings.DATABASE_TYPE.lower() == "postgresql":
            import psycopg2
            conn = psycopg2.connect(
                host=settings.DB_SERVER,
                port=settings.DB_PORT,
                database=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD
            )
            return conn
        elif settings.DATABASE_TYPE.lower() == "mysql":
            import pymysql
            conn = pymysql.connect(
                host=settings.DB_SERVER,
                port=int(settings.DB_PORT),
                database=settings.DB_NAME,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD
            )
            return conn
        else:  # sqlite
            import sqlite3
            conn = sqlite3.connect(settings.SQLITE_DB_PATH)
            return conn
    except Exception as e:
        logger.error(f"Error obteniendo conexión directa: {str(e)}")
        raise e


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def execute_query(sql: str) -> list[dict]:
    """
    Ejecuta una consulta SQL y devuelve los resultados como una lista de diccionarios.
    """
    db: Session | None = None
    try:
        db = SessionLocal()
        result = db.execute(text(sql))
        rows = result.fetchall()
        columns = result.keys()
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        logger.error(f"Error ejecutando query: {e}")
        return []
    finally:
        if db is not None:
            db.close()
