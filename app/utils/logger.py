#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo para la configuración de logging.
Proporciona funciones y configuraciones para el registro de eventos en la aplicación.
"""

import os
import logging
import logging.handlers
import time
import threading
from pathlib import Path
from functools import lru_cache

# Crear directorio de logs si no existe
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Configuración de formatos de log
CONSOLE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
FILE_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"

# Niveles de log según entorno
DEBUG_MODE = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
LOG_LEVEL = logging.DEBUG if DEBUG_MODE else logging.INFO

class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    Handler de archivo rotativo seguro para multiproceso.
    Maneja correctamente el acceso concurrente al archivo de log.
    """
    
    def __init__(self, filename, maxBytes=0, backupCount=0, encoding=None, delay=False):
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding, delay=delay)
        self.lock = threading.RLock()
    
    def emit(self, record):
        """
        Emite un registro de log de manera thread-safe.
        """
        try:
            with self.lock:
                super().emit(record)
        except (OSError, IOError) as e:
            # Si hay un error de permisos, intentar escribir a un archivo alternativo
            if "PermissionError" in str(e) or "WinError 32" in str(e):
                self._handle_permission_error(record)
            else:
                raise
    
    def _handle_permission_error(self, record):
        """
        Maneja errores de permisos escribiendo a un archivo alternativo.
        """
        try:
            # Crear un archivo de log alternativo con timestamp
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            alt_filename = f"{self.baseFilename}.{timestamp}.tmp"
            
            with open(alt_filename, 'a', encoding=self.encoding or 'utf-8') as f:
                msg = self.format(record)
                f.write(msg + '\n')
                f.flush()
        except Exception:
            # Si todo falla, escribir a stderr
            import sys
            print(f"Error de logging: {record.getMessage()}", file=sys.stderr)
    
    def doRollover(self):
        """
        Realiza la rotación del archivo de manera thread-safe.
        """
        try:
            with self.lock:
                super().doRollover()
        except (OSError, IOError) as e:
            # Si hay un error de permisos durante la rotación, continuar sin rotar
            if "PermissionError" in str(e) or "WinError 32" in str(e):
                pass
            else:
                raise

def setup_logging():
    """
    Configura el sistema de logging global de la aplicación.
    Configura handlers para consola y archivo de manera segura para multiproceso.
    """
    # Importar configuración específica de logging
    from app.config.logging_config import setup_environment_logging
    
    # Configurar logging del entorno (incluye supresión de loggers verbosos)
    log_level = setup_environment_logging()
    
    # Obtener logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Forzar DEBUG para ver logs de debug
    
    # Limpiar handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Forzar DEBUG para ver logs de debug
    console_formatter = logging.Formatter(CONSOLE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Handler para archivo rotativo seguro para multiproceso
    log_file = LOG_DIR / "chatbot.log"
    file_handler = SafeRotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8',
        delay=True  # Retrasar la apertura del archivo hasta el primer write
    )
    file_handler.setLevel(logging.DEBUG)  # Forzar DEBUG para ver logs de debug
    file_formatter = logging.Formatter(FILE_FORMAT)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Handler para errores específicos
    error_log_file = LOG_DIR / "errors.log"
    error_handler = SafeRotatingFileHandler(
        error_log_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8',
        delay=True
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_handler)
    
    # Configurar mensajes iniciales
    root_logger.info("Logging configurado correctamente")
    root_logger.debug(f"Modo depuración: {'Activado' if DEBUG_MODE else 'Desactivado'}")
    root_logger.info(f"Nivel de log configurado: {logging.getLevelName(log_level)}")

@lru_cache(maxsize=128)
def get_logger(name):
    """
    Obtiene un logger configurado para un módulo específico.
    Utiliza caché para evitar crear múltiples instancias del mismo logger.
    
    Args:
        name: Nombre del logger, generalmente __name__.
        
    Returns:
        Logger configurado.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        log_dir = os.getenv("LOG_DIR", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "chatbot.log")
        handler = SafeRotatingFileHandler(
            filename=log_file, 
            maxBytes=5*1024*1024, 
            backupCount=2, 
            encoding='utf-8',
            delay=True
        )
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger

class PerformanceTimer:
    """
    Clase para medir y registrar el rendimiento de operaciones.
    Útil para identificar cuellos de botella en la aplicación.
    """
    
    def __init__(self, operation_name, logger=None):
        """
        Inicializa un temporizador de rendimiento.
        
        Args:
            operation_name: Nombre de la operación a medir.
            logger: Logger a utilizar. Si es None, se utiliza el logger raíz.
        """
        self.operation_name = operation_name
        self.logger = logger or logging.getLogger()
        self.start_time = None
        
    def __enter__(self):
        """Inicia el temporizador al entrar en un contexto."""
        self.start_time = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Finaliza el temporizador al salir del contexto y registra el tiempo transcurrido.
        
        Args:
            exc_type: Tipo de excepción si ocurrió alguna.
            exc_val: Valor de la excepción si ocurrió alguna.
            exc_tb: Traceback de la excepción si ocurrió alguna.
        """
        elapsed_time = time.time() - self.start_time
        if exc_type:
            self.logger.warning(
                f"Operación '{self.operation_name}' falló después de {elapsed_time:.4f} segundos: {exc_val}"
            )
        else:
            self.logger.debug(f"Operación '{self.operation_name}' completada en {elapsed_time:.4f} segundos")
            
        # No suprimimos excepciones
        return False

# Función para medir rendimiento como decorador
def measure_performance(operation_name=None, logger=None):
    """
    Decorador para medir el rendimiento de funciones y métodos.
    
    Args:
        operation_name: Nombre de la operación. Si es None, se utiliza el nombre de la función.
        logger: Logger a utilizar. Si es None, se utiliza el logger raíz.
        
    Returns:
        Decorador configurado.
    """
    def decorator(func):
        nonlocal operation_name
        if operation_name is None:
            operation_name = func.__name__
            
        func_logger = logger or logging.getLogger(func.__module__)
        
        def wrapper(*args, **kwargs):
            with PerformanceTimer(operation_name, func_logger):
                return func(*args, **kwargs)
        return wrapper
    return decorator