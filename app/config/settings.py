# -*- coding: utf-8 -*-
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env si existe
# Buscar el archivo .env en el directorio raíz del proyecto
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
env_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path=env_path)


def _safe_int(value: str, default: int) -> int:
    """Convierte a int de forma segura; si falla retorna default."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: str, default: float) -> float:
    """Convierte a float de forma segura; si falla retorna default."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _resolve_database_type() -> str:
    """Resuelve DATABASE_TYPE respetando USE_SQL_SERVER del .env legacy."""
    explicit = os.getenv("DATABASE_TYPE")
    if explicit and explicit.strip():
        return explicit.strip()
    use_sql_server = os.getenv("USE_SQL_SERVER", "False").lower() in ("true", "1", "t")
    return "sqlserver" if use_sql_server else "sqlite"


class Settings(BaseSettings):
    """Configuraciones de la aplicación."""

    # Configuración general
    APP_NAME: str = "Chatbot Tienda de Abastos"
    APP_VERSION: str = "1.0.0"
    APP_URL: str = os.getenv("APP_URL", "http://localhost:8000")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")

    # Configuración del servidor
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = _safe_int(os.getenv("PORT"), 8000)

    # Configuración de CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    # ==============================
    # CONFIGURACIÓN DE BASE DE DATOS
    # ==============================
    # Tipo de base de datos (sqlserver, postgresql, mysql, sqlite)
    DATABASE_TYPE: str = _resolve_database_type()

    # Configuraciones comunes para todas las bases de datos
    DB_SERVER: str = os.getenv("DB_SERVER", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "1433")
    DB_NAME: str = os.getenv("DB_NAME", "vmm")
    DB_USER: str = os.getenv("DB_USER", "sa")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "Admin24")

    # Configuraciones específicas por tipo de base de datos
    # SQL Server
    SQL_SERVER_CONN: str = os.getenv(
        "SQL_SERVER_CONN",
        f"mssql+pyodbc://{os.getenv('DB_USER', 'sa')}:{os.getenv('DB_PASSWORD', 'Admin24')}"
        f"@{os.getenv('DB_SERVER', 'localhost')}:{os.getenv('DB_PORT', '1433')}/{os.getenv('DB_NAME', 'vmm')}"
        "?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes",
    )

    # PostgreSQL
    POSTGRES_CONN: str = os.getenv(
        "POSTGRES_CONN",
        f"postgresql://{os.getenv('DB_USER', 'postgres')}:{os.getenv('DB_PASSWORD', 'password')}"
        f"@{os.getenv('DB_SERVER', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'chatbot')}",
    )

    # MySQL
    MYSQL_CONN: str = os.getenv(
        "MYSQL_CONN",
        f"mysql+pymysql://{os.getenv('DB_USER', 'root')}:{os.getenv('DB_PASSWORD', 'password')}"
        f"@{os.getenv('DB_SERVER', 'localhost')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME', 'chatbot')}",
    )

    # SQLite
    SQLITE_URL: str = os.getenv("SQLITE_URL", "sqlite:///chatbot.db")
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "chatbot.db")

    # Configuración de autenticación
    JWT_SECRET: str = os.getenv(
        "JWT_SECRET", "your_secret_key_for_jwt_tokens_should_be_very_long_and_secure"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = int(
        os.getenv("JWT_EXPIRATION_MINUTES", 60 * 24)
    )  # 24 horas

    # Configuración LLM (Modelos de lenguaje)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "huggingface")
    HF_TOKEN: str = os.getenv("HUGGINGFACE_TOKEN", "")
    HF_MODEL_ID: str = os.getenv("HUGGINGFACE_MODEL", "microsoft/DialoGPT-medium")
    SUPPRESS_HF_WARNINGS: bool = os.getenv("SUPPRESS_HF_WARNINGS", "True").lower() in (
        "true",
        "1",
        "t",
    )
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral:v0.2")
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    LOCAL_MODEL_PATH: str = os.getenv("LOCAL_MODEL_PATH", "models/llama2-7b-chat.gguf")

    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Parámetros de modelo
    MODEL_TEMPERATURE: float = float(os.getenv("MODEL_TEMPERATURE", "0.5"))
    MODEL_MAX_TOKENS: int = int(os.getenv("MODEL_MAX_TOKENS", "100"))

    # 🚀 configuraciones para optimización de memoria y cuantización
    ENABLE_QUANTIZATION: bool = os.getenv("ENABLE_QUANTIZATION", "True").lower() in (
        "true",
        "1",
        "t",
    )
    QUANTIZATION_BITS: int = int(
        os.getenv("QUANTIZATION_BITS", "4")
    )  # Cuantización de 4 bits
    MEMORY_OPTIMIZATION: bool = os.getenv("MEMORY_OPTIMIZATION", "True").lower() in (
        "true",
        "1",
        "t",
    )
    MODEL_CACHE_SIZE: int = int(
        os.getenv("MODEL_CACHE_SIZE", "1000")
    )  # Tamaño del caché del modelo
    RESPONSE_CACHE_TTL: int = int(
        os.getenv("RESPONSE_CACHE_TTL", "3600")
    )  # TTL del caché en segundos

    # Configuración de directorios
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")

    # Configuración ChromaDB
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "Productos")
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR", os.path.join(DATA_DIR, "chroma_db")
    )

    # Configuración SMTP
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "no-reply@example.com")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "Tienda de Abastos")

    # 🚀  configuraciones para stock
    LOW_STOCK_THRESHOLD: int = int(
        os.getenv("LOW_STOCK_THRESHOLD", 4)
    )  # Productos por acabarse
    MINIMUM_AVAILABLE_STOCK: int = int(
        os.getenv("MINIMUM_AVAILABLE_STOCK", 1)
    )  # Stock mínimo para considerar disponible

    # 🚀  configuraciones para rendimiento y escalabilidad
    MAX_CONCURRENT_USERS: int = int(
        os.getenv("MAX_CONCURRENT_USERS", "100")
    )  # Usuarios concurrentes máximos
    RESPONSE_TIME_TARGET: float = float(
        os.getenv("RESPONSE_TIME_TARGET", "1.73")
    )  # Tiempo de respuesta objetivo en segundos
    ENABLE_PERFORMANCE_MONITORING: bool = os.getenv(
        "ENABLE_PERFORMANCE_MONITORING", "True"
    ).lower() in ("true", "1", "t")

    # 🚀  configuraciones para evaluación
    EVALUATION_ENABLED: bool = os.getenv("EVALUATION_ENABLED", "True").lower() in (
        "true",
        "1",
        "t",
    )
    EVALUATION_MODEL: str = os.getenv("EVALUATION_MODEL", "llama-3.2-3b-instruct")
    EVALUATION_THRESHOLD: float = float(
        os.getenv("EVALUATION_THRESHOLD", "0.7")
    )  # Umbral mínimo de evaluación

    # 🚀  configuraciones para días de productos
    DAYS_FOR_NEW_PRODUCTS: int = int(
        os.getenv("DAYS_FOR_NEW_PRODUCTS", "30")
    )  # Días para considerar producto nuevo
    DAYS_FOR_EXPIRING_PRODUCTS: int = int(
        os.getenv("DAYS_FOR_EXPIRING_PRODUCTS", "15")
    )  # Días para considerar producto por vencer

    # 🚀  configuraciones para seguridad de empleados
    EMPLOYEE_ONLY_SYSTEM: bool = os.getenv("EMPLOYEE_ONLY_SYSTEM", "True").lower() in (
        "true",
        "1",
        "t",
    )
    ALLOW_ANONYMOUS_ACCESS: bool = os.getenv(
        "ALLOW_ANONYMOUS_ACCESS", "False"
    ).lower() in ("true", "1", "t")
    DEFAULT_EMPLOYEE_ROLE: str = os.getenv("DEFAULT_EMPLOYEE_ROLE", "empleado")
    # No hay credenciales por defecto - el primer administrador debe crearse manualmente
    ADMIN_EMAILS: str = os.getenv("ADMIN_EMAILS", "")
    OWNER_EMAILS: str = os.getenv("OWNER_EMAILS", "")

    # 🚀  configuraciones para seguridad de empleados
    EMPLOYEE_SESSION_TIMEOUT: int = int(
        os.getenv("EMPLOYEE_SESSION_TIMEOUT", "480")
    )  # 8 horas en minutos
    MAX_LOGIN_ATTEMPTS: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "3"))
    ACCOUNT_LOCKOUT_DURATION: int = int(
        os.getenv("ACCOUNT_LOCKOUT_DURATION", "30")
    )  # minutos
    REQUIRE_STRONG_PASSWORDS: bool = os.getenv(
        "REQUIRE_STRONG_PASSWORDS", "True"
    ).lower() in ("true", "1", "t")

    # 🚀  configuraciones para logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/chatbot.log")
    LOG_FORMAT: str = os.getenv(
        "LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # 🚀  configuraciones para métricas
    ENABLE_METRICS: bool = os.getenv("ENABLE_METRICS", "True").lower() in (
        "true",
        "1",
        "t",
    )
    METRICS_PORT: int = int(os.getenv("METRICS_PORT", "9090"))

    # 🚀  configuraciones para sincronización
    AUTO_SYNC_ENABLED: bool = os.getenv("AUTO_SYNC_ENABLED", "True").lower() in (
        "true",
        "1",
        "t",
    )
    SYNC_INTERVAL_HOURS: int = int(os.getenv("SYNC_INTERVAL_HOURS", "24"))
    SYNC_BATCH_SIZE: int = int(os.getenv("SYNC_BATCH_SIZE", "100"))

    # 🚀  configuraciones para rate limiting
    RATE_LIMIT_REQUESTS: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "3600"))

    # 🚀  configuraciones para seguridad avanzada
    SECURITY_HEADERS: bool = os.getenv("SECURITY_HEADERS", "True").lower() in (
        "true",
        "1",
        "t",
    )
    CONTENT_SECURITY_POLICY: str = os.getenv(
        "CONTENT_SECURITY_POLICY", "default-src 'self'"
    )

    # 🚀  configuraciones para desarrollo
    RELOAD_ON_CHANGE: bool = os.getenv("RELOAD_ON_CHANGE", "True").lower() in (
        "true",
        "1",
        "t",
    )

    # 🚀  configuraciones para embeddings
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))

    # 🚀  configuraciones para caché
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))
    ENABLE_CACHE: bool = os.getenv("ENABLE_CACHE", "True").lower() in ("true", "1", "t")

    # 🚀  configuraciones para límites
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "2048"))
    TOP_P: float = float(os.getenv("TOP_P", "0.9"))

    # 🚀  configuraciones para Ollama
    OLLAMA_TIMEOUT: int = int(
        os.getenv("OLLAMA_TIMEOUT", "30")
    )  # Reducido de 60 a 30 segundos
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # 🚀  configuraciones para rendimiento para Ollama
    OLLAMA_OPTIONS: dict = {
        "num_ctx": 4096,  # Contexto reducido para mayor velocidad
        "num_predict": 512,  # Respuestas más cortas
        "temperature": 0.7,  # Menos aleatoriedad
        "top_p": 0.9,  # Más determinístico
        "repeat_penalty": 1.1,  # Evitar repeticiones
        "num_thread": 4,  # Usar múltiples threads
        "num_gpu": 1,  # Usar GPU si está disponible
        "stop": [
            "\n\n",
            "Pregunta:",
            "Respuesta:",
            "SQL:",
            "```",
        ],  # Parar en puntos lógicos
    }

    # 🚀  configuraciones para HuggingFace
    HUGGINGFACE_MODEL: str = os.getenv("HUGGINGFACE_MODEL", "microsoft/DialoGPT-medium")

    # 🚀  configuraciones para correo
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "True").lower() in ("true", "1", "t")

    # 🚀  configuraciones para CORS avanzadas
    CORS_ALLOW_CREDENTIALS: bool = os.getenv(
        "CORS_ALLOW_CREDENTIALS", "True"
    ).lower() in ("true", "1", "t")

    @property
    def DATABASE_URL(self) -> str:
        """Retorna la URL de conexión según el tipo de base de datos configurado."""
        if self.DATABASE_TYPE.lower() == "postgresql":
            return self.POSTGRES_CONN
        elif self.DATABASE_TYPE.lower() == "mysql":
            return self.MYSQL_CONN
        elif self.DATABASE_TYPE.lower() == "sqlite":
            return self.SQLITE_URL
        else:  # sqlserver por defecto
            return self.SQL_SERVER_CONN


# Instancia global de configuración
settings = Settings()
