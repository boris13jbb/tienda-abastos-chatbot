import json
import os
import time
import re

# Definir la carpeta donde se guardarán los registros
LOG_FOLDER = "logs"

# Asegurar que el directorio exista
os.makedirs(LOG_FOLDER, exist_ok=True)

def slugify(text):
    """
    Convierte el texto en un "slug" para usar en nombres de archivo.
    Elimina caracteres especiales y espacios, reemplazándolos con guiones bajos.
    """
    text = re.sub(r'[^\w\s-]', '_', text)  # Reemplaza caracteres no alfanuméricos con guiones bajos
    text = re.sub(r'[\s_-]+', '_', text)   # Reemplaza espacios y guiones con un solo guion bajo
    return text.strip('_')

def guardar_interaccion(pregunta: str, respuesta: str, prompt_tokens: int = 0, completion_tokens: int = 0):
    """
    Guarda una interacción en un archivo JSON individual.

    Args:
        pregunta: La pregunta que hizo el usuario
        respuesta: La respuesta generada por el chatbot
        prompt_tokens: (opcional) cantidad de tokens del prompt
        completion_tokens: (opcional) cantidad de tokens de la respuesta
    """
    try:
        registro = {
            "timestamp": time.time(),
            "query": pregunta,
            "result": {
                "success": True,
                "content": respuesta,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                },
                "elapsed_time": 0  # lo puedes rellenar si deseas medirlo
            }
        }

        # Crear un nombre de archivo único basado en la pregunta
        nombre_archivo = f"chatbot_interaction_{slugify(pregunta)}.json"
        LOG_FILE = os.path.join(LOG_FOLDER, nombre_archivo)

        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=4)
        
    except Exception as e:
        print(f"Error al guardar interacción: {e}")
