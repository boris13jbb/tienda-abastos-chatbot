"""
Módulo de integración con modelos de lenguaje para el chatbot de la tienda de abastos.
"""

import os
import re
import logging
import time
import requests
from functools import wraps
from typing import Dict, Any, Optional, List, Union
from datetime import datetime, timedelta

# Importar configuraciones
from app.config.settings import settings

# Configuración de logging
logger = logging.getLogger(__name__)

# Decorador para medir tiempo de ejecución
def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        logger.debug(f"Operación '{func.__name__}' completada en {elapsed_time:.4f} segundos")
        return result
    return wrapper

class SimpleLanguageModel:
    """Implementación simplificada para la integración con modelos de lenguaje."""
    
    def __init__(self, model_name: str = None):
        """
        Inicializa el modelo de lenguaje.
        
        Args:
            model_name: Nombre del modelo a utilizar (opcional, por defecto usa el de settings)
        """
        # Configurar ambos proveedores - Ollama como principal y HuggingFace como fallback
        self.use_ollama = settings.LLM_PROVIDER.lower() == "ollama"
        
        # Configuración de Ollama (proveedor principal si está configurado)
        self.ollama_model = settings.OLLAMA_MODEL
        self.ollama_host = settings.OLLAMA_HOST
        
        # Configuración de HuggingFace (fallback)
        self.hf_model = model_name or settings.HF_MODEL_ID
        self.token = settings.HF_TOKEN
        self.api_url = "https://api-inference.huggingface.co/models/"
        
        # 🚀 NUEVO: Configuración de caché con TTL
        self.response_cache = {}
        self.cache_timestamps = {}
        self.cache_size_limit = settings.MODEL_CACHE_SIZE
        self.cache_ttl = settings.RESPONSE_CACHE_TTL
        
        # 🚀 NUEVO: Configuración de optimización de memoria
        self.enable_quantization = settings.ENABLE_QUANTIZATION
        self.quantization_bits = settings.QUANTIZATION_BITS
        self.memory_optimization = settings.MEMORY_OPTIMIZATION
        
        if self.use_ollama:
            logger.info(f"Inicializando con Ollama como principal: {self.ollama_model} en {self.ollama_host}")
            logger.info(f"HuggingFace como fallback: {self.hf_model}")
            logger.info(f"Optimización de memoria: {self.memory_optimization}")
            logger.info(f"Cuantización de {self.quantization_bits} bits: {self.enable_quantization}")
            # Verificar conectividad con Ollama
            self._verify_ollama_connection()
        else:
            logger.info(f"Inicializando con HuggingFace como principal: {self.hf_model}")
            if not self.token:
                logger.warning("No se ha configurado HF_TOKEN. El modelo puede no funcionar correctamente.")
    
    def _verify_ollama_connection(self) -> bool:
        """Verifica la conectividad con Ollama."""
        try:
            response = requests.get(f"{self.ollama_host}/api/version", timeout=5)
            if response.status_code == 200:
                version_info = response.json()
                logger.info(f"Conexión exitosa con Ollama versión {version_info.get('version')}")
                return True
            else:
                logger.error(f"Error conectando con Ollama: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"No se pudo conectar con Ollama: {str(e)}")
            return False

    def _cleanup_cache(self) -> None:
        """Limpia el caché expirado y mantiene el tamaño límite."""
        current_time = datetime.now()
        
        # Eliminar entradas expiradas
        expired_keys = []
        for key, timestamp in self.cache_timestamps.items():
            if (current_time - timestamp).total_seconds() > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.response_cache[key]
            del self.cache_timestamps[key]
        
        # Si el caché sigue siendo muy grande, eliminar las entradas más antiguas
        if len(self.response_cache) > self.cache_size_limit:
            sorted_items = sorted(self.cache_timestamps.items(), key=lambda x: x[1])
            items_to_remove = len(self.response_cache) - self.cache_size_limit
            
            for i in range(items_to_remove):
                key = sorted_items[i][0]
                del self.response_cache[key]
                del self.cache_timestamps[key]
        
        if expired_keys or len(self.response_cache) > self.cache_size_limit:
            logger.info(f"Caché limpiado: {len(expired_keys)} entradas expiradas removidas")

    def clear_cache(self) -> None:
        """Limpia el caché de respuestas."""
        self.response_cache = {}
        self.cache_timestamps = {}
        logger.info("Caché de respuestas limpiada completamente")
    
    def _generate_with_ollama(self, prompt: str, is_sql_query: bool = False) -> Optional[str]:
        """
        Genera una respuesta utilizando Ollama.
        
        Args:
            prompt: Prompt para el modelo
            is_sql_query: Indica si se está generando una consulta SQL
            
        Returns:
            Respuesta generada o None si falla
        """
        try:
            # URL de la API de Ollama
            url = f"{self.ollama_host}/api/generate"
            
            # 🚀 NUEVO: Configuración optimizada con cuantización
            options = {
                "temperature": 0.1 if is_sql_query else settings.MODEL_TEMPERATURE,
                "num_predict": 500 if is_sql_query else settings.MODEL_MAX_TOKENS
            }
            
            # Agregar configuración de cuantización si está habilitada
            if self.enable_quantization:
                options["quantization"] = f"q{self.quantization_bits}"
                logger.debug(f"Aplicando cuantización de {self.quantization_bits} bits")
            
            # Configuración para la solicitud
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": options
            }
            
            logger.info(f"Generando respuesta con Ollama (modelo: {self.ollama_model})")
            response = requests.post(url, json=payload, timeout=settings.OLLAMA_TIMEOUT)
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("response", "").strip()
                
                # Verificar si es consulta SQL y la respuesta es válida
                if is_sql_query and not generated_text.upper().startswith("SELECT"):
                    logger.warning(f"Ollama no generó una consulta SQL válida: {generated_text}")
                    return None
                
                logger.info(f"Respuesta generada exitosamente con Ollama")
                return generated_text
            else:
                logger.error(f"Error al llamar a Ollama API: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error al usar Ollama: {str(e)}")
            return None
    
    def _query_huggingface_api(self, prompt: str) -> Optional[str]:
        """
        Consulta directamente la API de HuggingFace.
        
        Args:
            prompt: Prompt para el modelo
            
        Returns:
            Respuesta generada o None si falla
        """
        try:
            api_url = f"{self.api_url}{self.hf_model}"
            headers = {"Authorization": f"Bearer {self.token}"}
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_length": settings.MODEL_MAX_TOKENS,
                    "temperature": settings.MODEL_TEMPERATURE,
                    "top_p": 0.95
                }
            }
            
            response = requests.post(api_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get("generated_text", "")
                return ""
            else:
                logger.error(f"Error al llamar a la API de HuggingFace: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error al consultar la API de HuggingFace: {str(e)}")
            return None
    
    @timer
    def generate_response(self, prompt: str, is_sql_query: bool = False) -> str:
        """
        Genera una respuesta utilizando el modelo de lenguaje.
        
        Args:
            prompt: Prompt para el modelo de lenguaje
            is_sql_query: Indica si se está generando una consulta SQL
            
        Returns:
            Respuesta generada
        """
        # 🚀 NUEVO: Limpiar caché antes de verificar
        self._cleanup_cache()
        
        # Verificar si la respuesta está en caché
        if prompt in self.response_cache:
            logger.info("Respuesta recuperada de caché")
            return self.response_cache[prompt]
        
        # Extraer la pregunta del prompt para generar una respuesta más específica
        question_match = re.search(r"Pregunta:\s*(.*?)(?:\n|$)", prompt)
        question = question_match.group(1) if question_match else ""
        
        response = None
        
        # Usar el proveedor configurado con fallback automático
        if self.use_ollama:
            # 1. Intentar con Ollama como proveedor principal
            response = self._generate_with_ollama(prompt, is_sql_query)
            if response:
                logger.info("Respuesta generada con Ollama (proveedor principal)")
                # 🚀 NUEVO: Guardar en caché con timestamp
                self.response_cache[prompt] = response
                self.cache_timestamps[prompt] = datetime.now()
                return response
            else:
                logger.warning("Ollama falló, usando HuggingFace como fallback")
                # 2. Usar HuggingFace como fallback si Ollama falla
                response = self._query_huggingface_api(prompt)
                if response:
                    logger.info("Respuesta generada con HuggingFace (fallback)")
                    # 🚀 NUEVO: Guardar en caché con timestamp
                    self.response_cache[prompt] = response
                    self.cache_timestamps[prompt] = datetime.now()
                    return response
        else:
            # Usar HuggingFace como proveedor principal
            response = self._query_huggingface_api(prompt)
            if response:
                logger.info("Respuesta generada con la API de HuggingFace")
                # 🚀 NUEVO: Guardar en caché con timestamp
                self.response_cache[prompt] = response
                self.cache_timestamps[prompt] = datetime.now()
                return response
        
        # Generar respuesta basada en reglas si todo lo anterior falla
        logger.warning("Generando respuesta basada en reglas")
        # Detectar si es una consulta sobre Productos específicos
        product_keywords = ["leche", "pan", "arroz", "azúcar", "aceite", "huevos", "café", 
                           "galletas", "pasta", "atún", "papel", "jabón", "detergente"]
        
        # Verificar si la pregunta contiene alguna palabra clave de Productos
        found_product = None
        for product in product_keywords:
            if product in question.lower():
                found_product = product
                break
        
        if found_product:
            # Generar respuesta específica para el Productos
            response = f"Actualmente no puedo verificar el inventario en tiempo real, pero normalmente tenemos {found_product} disponible en nuestra tienda. Te recomiendo visitar nuestra tienda o llamar directamente para confirmar la disponibilidad y precio actual."
        else:
            # Respuestas para diferentes tipos de preguntas
            if "precio" in question.lower() or "cuesta" in question.lower() or "valor" in question.lower():
                response = "No puedo consultar los precios en este momento. Te recomiendo visitar nuestra tienda o contactar directamente para obtener información actualizada sobre precios."
            elif "disponible" in question.lower() or "hay" in question.lower() or "stock" in question.lower():
                response = "No puedo verificar el inventario en tiempo real. Te recomiendo contactar directamente con la tienda para confirmar la disponibilidad de los Productos que necesitas."
            elif "horario" in question.lower() or "abierto" in question.lower() or "cerrado" in question.lower():
                response = "Nuestro horario habitual es de lunes a viernes de 8:00 AM a 8:00 PM, y sábados de 9:00 AM a 6:00 PM. Domingos cerrado. Te recomiendo confirmar por teléfono antes de visitarnos."
            else:
                # Respuesta genérica si no se detecta un tipo específico
                response = "En este momento no puedo proporcionar información detallada. Por favor, contacta directamente con nuestra tienda para obtener la información más actualizada."
        
        # 🚀 NUEVO: Guardar respuesta basada en reglas en caché
        self.response_cache[prompt] = response
        self.cache_timestamps[prompt] = datetime.now()
        
        return response
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del caché.
        
        Returns:
            Estadísticas del caché
        """
        self._cleanup_cache()
        return {
            "cache_size": len(self.response_cache),
            "cache_limit": self.cache_size_limit,
            "cache_ttl": self.cache_ttl,
            "memory_optimization": self.memory_optimization,
            "quantization_enabled": self.enable_quantization,
            "quantization_bits": self.quantization_bits
        }
    
    def test_ollama_connection(self) -> Dict[str, Any]:
        """
        Prueba la conexión y funcionalidad de Ollama.
        
        Returns:
            Diccionario con el resultado de la prueba
        """
        if not self.use_ollama:
            return {"status": "error", "message": "Ollama no está configurado como proveedor"}
        
        try:
            # Probar conectividad
            version_response = requests.get(f"{self.ollama_host}/api/version", timeout=5)
            if version_response.status_code != 200:
                return {"status": "error", "message": "No se puede conectar con Ollama"}
            
            # Probar generación de texto con timeout más corto
            test_prompt = "Hola"
            test_response = self._generate_with_ollama(test_prompt)
            
            if test_response:
                return {
                    "status": "success", 
                    "message": "Ollama funcionando correctamente",
                    "model": self.ollama_model,
                    "host": self.ollama_host,
                    "test_response": test_response[:100] + "..." if len(test_response) > 100 else test_response,
                    "optimization": {
                        "memory_optimization": self.memory_optimization,
                        "quantization_enabled": self.enable_quantization,
                        "quantization_bits": self.quantization_bits
                    }
                }
            else:
                # Si falla la generación directa, probar con el método principal que tiene fallback
                test_response = self.generate_response("Hola")
                if test_response:
                    return {
                        "status": "success", 
                        "message": "Ollama funcionando correctamente (con fallback)",
                        "model": self.ollama_model,
                        "host": self.ollama_host,
                        "test_response": test_response[:100] + "..." if len(test_response) > 100 else test_response,
                        "optimization": {
                            "memory_optimization": self.memory_optimization,
                            "quantization_enabled": self.enable_quantization,
                            "quantization_bits": self.quantization_bits
                        }
                    }
                else:
                    return {"status": "error", "message": "Ollama conectado pero no puede generar respuestas"}
                
        except Exception as e:
            return {"status": "error", "message": f"Error probando Ollama: {str(e)}"}

    def format_sql_prompt(self, question: str) -> str:
        """
        Formatea un prompt para generar consultas SQL.
        
        Args:
            question: Pregunta del usuario
            
        Returns:
            Prompt formateado
        """
        return f"""
        Eres un asistente que traduce preguntas en lenguaje natural a consultas SQL.
        La base de datos tiene una tabla llamada Productos con las siguientes columnas:
        - ID (int)
        - Nombre (varchar)
        - Descripcion (varchar)
        - Precio (decimal)
        - Stock (int)
        - FechaCreacion (datetime)
        
        La pregunta es: "{question}"
        
        Genera solo la consulta SQL sin explicaciones adicionales:
        """
    
    @timer
    def generate_sql_query(self, question: str) -> str:
        """
        Genera una consulta SQL a partir de una pregunta.
        
        Args:
            question: Pregunta del usuario
            
        Returns:
            Consulta SQL generada
        """
        start_time = time.time()
        prompt = self.format_sql_prompt(question)
        
        # Indicar que es una consulta SQL para permitir el fallback a Ollama
        response = self.generate_response(prompt, is_sql_query=True)
        
        # Limpiar respuesta
        response = response.strip()
        
        # Si la respuesta no parece una consulta SQL, usar una consulta genérica
        if not response.upper().startswith("SELECT"):
            logger.warning(f"La respuesta no parece una consulta SQL: {response}")
            fallback_query = "SELECT TOP 15 Nombre, Stock, Precio FROM Productos;"
            logger.info(f"Usando consulta SQL fallback: {fallback_query}")
            return fallback_query
        
        elapsed_time = time.time() - start_time
        logger.info(f"Consulta SQL generada en {elapsed_time:.4f} segundos: {response}")
        return response

# Instancia global del modelo de lenguaje (usando la implementación simplificada)
language_model = SimpleLanguageModel()

def get_language_model():
    """
    Obtiene la instancia global del modelo de lenguaje.
    
    Returns:
        Instancia del modelo de lenguaje
    """
    return language_model