#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Configuración específica de logging para diferentes entornos.
Permite un control granular de los niveles de log para evitar spam.
"""

import os
import logging
from typing import Dict, Any

# Configuración de niveles de log por entorno
LOG_LEVELS = {
    "development": logging.INFO,
    "production": logging.WARNING,
    "debug": logging.DEBUG
}

# Loggers que deben ser silenciados o reducidos en verbosidad
QUIET_LOGGERS = {
    "sqlalchemy.engine": logging.WARNING,
    "sqlalchemy.engine.base.Engine": logging.WARNING,
    "sqlalchemy.pool": logging.WARNING,
    "sqlalchemy.dialects": logging.WARNING,
    "sqlalchemy.orm": logging.WARNING,
    "sqlalchemy": logging.WARNING,
    "watchfiles": logging.WARNING,
    "watchfiles.main": logging.WARNING,
    "uvicorn": logging.WARNING,
    "fastapi": logging.WARNING,
    "asyncio": logging.WARNING,
    "httpx": logging.WARNING,
    "urllib3": logging.WARNING,
    "requests": logging.WARNING,
    "tqdm": logging.WARNING,
    "PIL": logging.WARNING,
    "matplotlib": logging.WARNING,
    "numpy": logging.WARNING,
    "pandas": logging.WARNING,
    "sklearn": logging.WARNING,
    "transformers": logging.WARNING,
    "torch": logging.WARNING,
    "tensorflow": logging.WARNING,
    "chromadb": logging.WARNING,
    "sentence_transformers": logging.WARNING,
    "ollama": logging.WARNING,
    "openai": logging.WARNING,
    "anthropic": logging.WARNING,
}

def configure_quiet_logging():
    """
    Configura el logging para reducir la verbosidad de librerías externas.
    """
    # Configurar loggers silenciosos
    for logger_name, level in QUIET_LOGGERS.items():
        logging.getLogger(logger_name).setLevel(level)
    
    # Configuración adicional para SQLAlchemy
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.setLevel(logging.WARNING)
    
    # Deshabilitar completamente los logs de watchfiles si no estamos en debug
    if os.getenv("DEBUG", "False").lower() not in ("true", "1", "t"):
        watchfiles_logger = logging.getLogger("watchfiles")
        watchfiles_logger.setLevel(logging.ERROR)
        watchfiles_logger.disabled = True

def get_log_level() -> int:
    """
    Obtiene el nivel de log apropiado según el entorno.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    debug_mode = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    
    if debug_mode:
        return LOG_LEVELS["debug"]
    
    return LOG_LEVELS.get(env, LOG_LEVELS["development"])

def setup_environment_logging():
    """
    Configura el logging específico para el entorno actual.
    """
    # Configurar loggers silenciosos
    configure_quiet_logging()
    
    # Obtener nivel de log apropiado
    log_level = get_log_level()
    
    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    return log_level 