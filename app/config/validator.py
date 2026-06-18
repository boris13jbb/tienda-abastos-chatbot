#!/usr/bin/env python3
"""
Validador de configuración centralizada para el chatbot de tienda de abastos.
Verifica que todas las configuraciones necesarias estén presentes y sean válidas.
"""

import os
import sys
from typing import Dict, List, Any, Tuple
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class ConfigurationValidator:
    """Validador de configuración centralizada."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.validated_configs = {}
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """Valida todas las configuraciones del sistema."""
        logger.info("🔍 Iniciando validación de configuración...")
        
        # Validar configuraciones básicas
        self._validate_basic_configs()
        
        # Validar configuración de base de datos
        self._validate_database_configs()
        
        # Validar configuración de LLM
        self._validate_llm_configs()
        
        # Validar configuración de embeddings
        self._validate_embedding_configs()
        
        # Validar configuración de ChromaDB
        self._validate_chromadb_configs()
        
        # Validar configuración de seguridad
        self._validate_security_configs()
        
        # Validar configuración de directorios
        self._validate_directory_configs()
        
        # Validar configuración de rendimiento
        self._validate_performance_configs()
        
        is_valid = len(self.errors) == 0
        
        if is_valid:
            logger.info("✅ Validación de configuración completada exitosamente")
        else:
            logger.error(f"❌ Validación de configuración falló con {len(self.errors)} errores")
        
        return is_valid, self.errors, self.warnings
    
    def _validate_basic_configs(self):
        """Valida configuraciones básicas de la aplicación."""
        logger.debug("Validando configuraciones básicas...")
        
        # Validar APP_NAME
        if not settings.APP_NAME or settings.APP_NAME.strip() == "":
            self.errors.append("APP_NAME no puede estar vacío")
        
        # Validar APP_VERSION
        if not settings.APP_VERSION or settings.APP_VERSION.strip() == "":
            self.errors.append("APP_VERSION no puede estar vacío")
        
        # Validar HOST
        if not settings.HOST or settings.HOST.strip() == "":
            self.errors.append("HOST no puede estar vacío")
        
        # Validar PORT
        if not isinstance(settings.PORT, int) or settings.PORT <= 0 or settings.PORT > 65535:
            self.errors.append("PORT debe ser un número entero entre 1 y 65535")
    
    def _validate_database_configs(self):
        """Valida configuración de base de datos."""
        logger.debug("Validando configuración de base de datos...")
        
        # Validar tipo de base de datos
        valid_db_types = ["sqlserver", "postgresql", "mysql", "sqlite"]
        if settings.DATABASE_TYPE.lower() not in valid_db_types:
            self.errors.append(f"DATABASE_TYPE debe ser uno de: {', '.join(valid_db_types)}")
        
        # Validar configuración específica por tipo
        if settings.DATABASE_TYPE.lower() == "sqlserver":
            if not settings.DB_SERVER or settings.DB_SERVER.strip() == "":
                self.errors.append("DB_SERVER es requerido para SQL Server")
            if not settings.DB_NAME or settings.DB_NAME.strip() == "":
                self.errors.append("DB_NAME es requerido para SQL Server")
            if not settings.DB_USER or settings.DB_USER.strip() == "":
                self.errors.append("DB_USER es requerido para SQL Server")
            if not settings.DB_PASSWORD or settings.DB_PASSWORD.strip() == "":
                self.errors.append("DB_PASSWORD es requerido para SQL Server")
        
        elif settings.DATABASE_TYPE.lower() == "sqlite":
            if not settings.SQLITE_DB_PATH or settings.SQLITE_DB_PATH.strip() == "":
                self.errors.append("SQLITE_DB_PATH es requerido para SQLite")
    
    def _validate_llm_configs(self):
        """Valida configuración de modelos de lenguaje."""
        logger.debug("Validando configuración de LLM...")
        
        # Validar proveedor de LLM
        valid_llm_providers = ["ollama", "huggingface", "local"]
        if settings.LLM_PROVIDER.lower() not in valid_llm_providers:
            self.errors.append(f"LLM_PROVIDER debe ser uno de: {', '.join(valid_llm_providers)}")
        
        # Validar configuración específica por proveedor
        if settings.LLM_PROVIDER.lower() == "ollama":
            if not settings.OLLAMA_HOST or settings.OLLAMA_HOST.strip() == "":
                self.errors.append("OLLAMA_HOST es requerido para Ollama")
            if not settings.OLLAMA_MODEL or settings.OLLAMA_MODEL.strip() == "":
                self.errors.append("OLLAMA_MODEL es requerido para Ollama")
        
        elif settings.LLM_PROVIDER.lower() == "huggingface":
            if not settings.HF_MODEL_ID or settings.HF_MODEL_ID.strip() == "":
                self.errors.append("HF_MODEL_ID es requerido para HuggingFace")
            if not settings.HF_TOKEN or settings.HF_TOKEN.strip() == "":
                self.warnings.append("HF_TOKEN no está configurado para HuggingFace")
        
        # Validar parámetros de modelo
        if not isinstance(settings.MODEL_TEMPERATURE, (int, float)) or settings.MODEL_TEMPERATURE < 0 or settings.MODEL_TEMPERATURE > 2:
            self.errors.append("MODEL_TEMPERATURE debe ser un número entre 0 y 2")
        
        if not isinstance(settings.MODEL_MAX_TOKENS, int) or settings.MODEL_MAX_TOKENS <= 0:
            self.errors.append("MODEL_MAX_TOKENS debe ser un número entero positivo")
    
    def _validate_embedding_configs(self):
        """Valida configuración de embeddings."""
        logger.debug("Validando configuración de embeddings...")
        
        if not settings.EMBEDDING_MODEL or settings.EMBEDDING_MODEL.strip() == "":
            self.errors.append("EMBEDDING_MODEL es requerido")
        
        if not isinstance(settings.CHUNK_SIZE, int) or settings.CHUNK_SIZE <= 0:
            self.errors.append("CHUNK_SIZE debe ser un número entero positivo")
        
        if not isinstance(settings.CHUNK_OVERLAP, int) or settings.CHUNK_OVERLAP < 0:
            self.errors.append("CHUNK_OVERLAP debe ser un número entero no negativo")
    
    def _validate_chromadb_configs(self):
        """Valida configuración de ChromaDB."""
        logger.debug("Validando configuración de ChromaDB...")
        
        if not settings.CHROMA_COLLECTION or settings.CHROMA_COLLECTION.strip() == "":
            self.errors.append("CHROMA_COLLECTION es requerido")
        
        if not settings.CHROMA_PERSIST_DIR or settings.CHROMA_PERSIST_DIR.strip() == "":
            self.errors.append("CHROMA_PERSIST_DIR es requerido")
        
        # Verificar que el directorio de ChromaDB sea accesible
        try:
            chroma_dir = Path(settings.CHROMA_PERSIST_DIR)
            chroma_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.errors.append(f"No se puede crear/acceder al directorio de ChromaDB: {str(e)}")
    
    def _validate_security_configs(self):
        """Valida configuración de seguridad."""
        logger.debug("Validando configuración de seguridad...")
        
        if not settings.JWT_SECRET or settings.JWT_SECRET.strip() == "":
            self.errors.append("JWT_SECRET es requerido")
        elif len(settings.JWT_SECRET) < 32:
            self.warnings.append("JWT_SECRET debería tener al menos 32 caracteres para mayor seguridad")
        
        if not isinstance(settings.JWT_EXPIRATION_MINUTES, int) or settings.JWT_EXPIRATION_MINUTES <= 0:
            self.errors.append("JWT_EXPIRATION_MINUTES debe ser un número entero positivo")
        
        if not isinstance(settings.MAX_LOGIN_ATTEMPTS, int) or settings.MAX_LOGIN_ATTEMPTS <= 0:
            self.errors.append("MAX_LOGIN_ATTEMPTS debe ser un número entero positivo")
    
    def _validate_directory_configs(self):
        """Valida configuración de directorios."""
        logger.debug("Validando configuración de directorios...")
        
        required_dirs = [
            ("DATA_DIR", settings.DATA_DIR),
            ("LOG_DIR", settings.LOG_DIR),
        ]
        
        for dir_name, dir_path in required_dirs:
            if not dir_path or dir_path.strip() == "":
                self.errors.append(f"{dir_name} es requerido")
            else:
                try:
                    Path(dir_path).mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self.errors.append(f"No se puede crear/acceder al directorio {dir_name}: {str(e)}")
    
    def _validate_performance_configs(self):
        """Valida configuración de rendimiento."""
        logger.debug("Validando configuración de rendimiento...")
        
        if not isinstance(settings.MAX_CONCURRENT_USERS, int) or settings.MAX_CONCURRENT_USERS <= 0:
            self.errors.append("MAX_CONCURRENT_USERS debe ser un número entero positivo")
        
        if not isinstance(settings.RESPONSE_TIME_TARGET, (int, float)) or settings.RESPONSE_TIME_TARGET <= 0:
            self.errors.append("RESPONSE_TIME_TARGET debe ser un número positivo")
        
        if not isinstance(settings.MODEL_CACHE_SIZE, int) or settings.MODEL_CACHE_SIZE <= 0:
            self.errors.append("MODEL_CACHE_SIZE debe ser un número entero positivo")
        
        if not isinstance(settings.RESPONSE_CACHE_TTL, int) or settings.RESPONSE_CACHE_TTL <= 0:
            self.errors.append("RESPONSE_CACHE_TTL debe ser un número entero positivo")
    
    def print_validation_report(self):
        """Imprime un reporte detallado de la validación."""
        print("\n" + "="*60)
        print("📋 REPORTE DE VALIDACIÓN DE CONFIGURACIÓN")
        print("="*60)
        
        if not self.errors and not self.warnings:
            print("✅ Todas las configuraciones son válidas")
            return
        
        if self.errors:
            print(f"\n❌ ERRORES ENCONTRADOS ({len(self.errors)}):")
            for i, error in enumerate(self.errors, 1):
                print(f"  {i}. {error}")
        
        if self.warnings:
            print(f"\n⚠️  ADVERTENCIAS ({len(self.warnings)}):")
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
        
        print("\n" + "="*60)

def validate_configuration() -> bool:
    """Función principal para validar la configuración."""
    validator = ConfigurationValidator()
    is_valid, errors, warnings = validator.validate_all()
    validator.print_validation_report()
    return is_valid

if __name__ == "__main__":
    validate_configuration() 