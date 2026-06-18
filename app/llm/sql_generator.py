# Archivo: app/llm/sql_generator.py

import re
import logging
import time
from functools import wraps
from typing import Optional, Dict, List, Any, Tuple

from app.llm.language_model import get_language_model
from app.database.db import execute_query
from app.utils.logger import get_logger, measure_performance
from app.rag.text_processor import text_processor

logger = get_logger(__name__)

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_time = time.time() - start_time
        logger.debug(f"Operación '{func.__name__}' completada en {elapsed_time:.4f} segundos")
        return result
    return wrapper

# ---------------------------
# PATRONES DIRECTOS
# ---------------------------
QUERY_PATTERNS = {
    
    
    
    # 🔵 Preguntas específicas corregidas:
    r"(?i).*productos están por acabarse.*":
        "SELECT Nombre, Stock FROM Productos WHERE Stock <= 10",

    r"(?i).*productos están agotados.*":
        "SELECT Nombre FROM Productos WHERE Stock = 0",

    r"(?i).*productos están por vencer.*":
        "SELECT Nombre, FechaVencimiento FROM Productos WHERE DATEDIFF(day, GETDATE(), FechaVencimiento) <= 30",

    r"(?i).*productos vencieron.*":
        "SELECT Nombre, FechaVencimiento FROM Productos WHERE FechaVencimiento < GETDATE()",
        
        
    # Productos generales
    r"(?i)(qué|cuáles) productos (tienen|hay|venden).*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Stock > 0 ORDER BY Nombre",

    r"(?i)(listar|mostrar|ver).*productos.*":
        "SELECT Nombre, Stock, Precio FROM Productos ORDER BY Nombre",

    # Productos específicos conocidos
    r"(?i).*cuadernos disponibles.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%cuaderno%' AND Stock > 0",

    r"(?i).*esferos disponibles.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%esfero%' AND Stock > 0",

    r"(?i).*leche disponible.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%leche%' AND Stock > 0",

    r"(?i).*arroz disponible.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%arroz%' AND Stock > 0",

    r"(?i).*azúcar disponible.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%azúcar%' AND Stock > 0",

    # Patrones para atún con y sin tilde
    r"(?i).*(atun|atún).*precio.*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%atún%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*(atun|atún).*disponible.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%atún%' AND Stock > 0",
        
    r"(?i).*precio.*(atun|atún).*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%atún%' AND Stock > 0 ORDER BY Precio ASC",

    # Categorías de productos
    r"(?i).*frutas.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%fruta%' ORDER BY Nombre",

    r"(?i).*verduras.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%verdura%' ORDER BY Nombre",

    r"(?i).*limpieza.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%limpieza%' ORDER BY Nombre",

    r"(?i).*panader[ií]a.*|.*pan.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%pan%' ORDER BY Nombre",

    r"(?i).*abarrotes.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%abarrote%' ORDER BY Nombre",

    r"(?i).*bebidas.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%bebida%' ORDER BY Nombre",

    r"(?i).*mascotas.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%mascota%' ORDER BY Nombre",

    r"(?i).*productos sin gluten.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%sin gluten%' ORDER BY Nombre",

    r"(?i).*productos veganos.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%vegano%' ORDER BY Nombre",

    r"(?i).*productos org[aá]nicos.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%orgánico%' ORDER BY Nombre",

    r"(?i).*productos para beb[eé]s.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%bebé%' ORDER BY Nombre",

    # Descuentos, ofertas
    r"(?i).*descuento.*|.*promoci[oó]n.*|.*oferta.*":
        "SELECT Nombre, Stock, Precio FROM Productos WHERE Descripcion LIKE '%descuento%' OR Descripcion LIKE '%promoción%' ORDER BY Nombre",

    # Productos por stock
    r"(?i).*productos por acabarse.*":
        "SELECT Nombre, Stock FROM Productos WHERE Stock <= 10 ORDER BY Stock ASC",

    r"(?i).*productos agotados.*":
        "SELECT Nombre FROM Productos WHERE Stock = 0",

    # Productos especiales
    r"(?i).*producto más vendido.*":
        "SELECT TOP 1 Nombre FROM Productos ORDER BY Stock DESC",

    r"(?i).*productos más vendidos.*":
        "SELECT TOP 10 Nombre, Stock, Precio FROM Productos ORDER BY Stock DESC",

    r"(?i).*productos nuevos.*|.*qué hay de nuevo.*":
        "SELECT TOP 10 Nombre, FechaCreacion FROM Productos ORDER BY FechaCreacion DESC",

    r"(?i).*productos por vencer.*":
        "SELECT TOP 10 Nombre, FechaVencimiento FROM Productos WHERE DATEDIFF(day, GETDATE(), FechaVencimiento) <= 30 ORDER BY FechaVencimiento ASC",

    r"(?i).*productos vencidos.*":
        "SELECT TOP 10 Nombre, FechaVencimiento FROM Productos WHERE FechaVencimiento < GETDATE()",

    # Precios
    r"(?i).*producto más caro.*":
        "SELECT TOP 1 Nombre, Precio FROM Productos ORDER BY Precio DESC",

    r"(?i).*producto más barato.*":
        "SELECT TOP 1 Nombre, Precio FROM Productos WHERE Stock > 0 ORDER BY Precio ASC",

    r"(?i).*cu[aá]nto.*cuesta.*leche.*":
        "SELECT TOP 5 Nombre, Precio FROM Productos WHERE Nombre LIKE '%leche%'",

    r"(?i).*cu[aá]nto.*cuesta.*arroz.*":
        "SELECT TOP 5 Nombre, Precio FROM Productos WHERE Nombre LIKE '%arroz%'",

    r"(?i).*cu[aá]nto.*cuesta.*aceite.*":
        "SELECT TOP 5 Nombre, Precio FROM Productos WHERE Nombre LIKE '%aceite%'",

    r"(?i).*cu[aá]nto.*cuesta.*az[uú]car.*":
        "SELECT TOP 5 Nombre, Precio FROM Productos WHERE Nombre LIKE '%azúcar%'",


# Productos generales
    r"(?i)(qué|cuáles) productos (tienen|hay|venden).*":
        "SELECT TOP 20 Nombre, Stock, Precio FROM Productos WHERE Stock > 0 ORDER BY Nombre",

    r"(?i)(listar|mostrar|ver).*productos.*":
        "SELECT TOP 20 Nombre, Stock, Precio FROM Productos ORDER BY Nombre",

    # Productos específicos
    r"(?i).*cuadernos disponibles.*":
        "SELECT TOP 10 Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%cuaderno%' AND Stock > 0",

    r"(?i).*esferos disponibles.*":
        "SELECT TOP 10 Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%esfero%' AND Stock > 0",

    # Productos por stock bajo o agotados
    r"(?i).*productos por acabarse.*":
        "SELECT TOP 10 Nombre, Stock FROM Productos WHERE Stock <= 10",

    r"(?i).*productos agotados.*":
        "SELECT TOP 10 Nombre FROM Productos WHERE Stock = 0",

    # Productos nuevos y vencimientos
    r"(?i).*productos nuevos.*|.*qué hay de nuevo.*":
        "SELECT TOP 10 Nombre, FechaCreacion FROM Productos ORDER BY FechaCreacion DESC",

    r"(?i).*productos por vencer.*":
        "SELECT TOP 10 Nombre, FechaVencimiento FROM Productos WHERE DATEDIFF(day, GETDATE(), FechaVencimiento) <= 30 ORDER BY FechaVencimiento ASC",

    r"(?i).*productos vencidos.*":
        "SELECT TOP 10 Nombre, FechaVencimiento FROM Productos WHERE FechaVencimiento < GETDATE()",

    # Precios
    r"(?i).*producto más caro.*":
        "SELECT TOP 1 Nombre, Precio FROM Productos ORDER BY Precio DESC",

    r"(?i).*producto más barato.*":
        "SELECT TOP 1 Nombre, Precio FROM Productos WHERE Stock > 0 ORDER BY Precio ASC",
        
    # Patrones para precios específicos
    r"(?i).*precio.*leche.*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%leche%' AND Stock > 0",
        
    r"(?i).*precio.*arroz.*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%arroz%' AND Stock > 0",
        
    r"(?i).*precio.*esfero.*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%esfero%' AND Stock > 0",
        
    r"(?i).*precio.*cuaderno.*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%cuaderno%' AND Stock > 0",
        
    # Patrón genérico para precios (debe ir al final)
    r"(?i).*precio.*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Stock > 0 ORDER BY Precio ASC",
        
    r"(?i)(qué|cuáles) productos (tienen|hay|venden) disponibles.*":
        "SELECT TOP 20 Nombre, Stock, Precio FROM Productos WHERE Stock > 0 ORDER BY Nombre",
                
    r"(?i)(qué|cuáles) productos (tienen|hay|venden) disponibles.*":
        "SELECT TOP 20 Nombre, Stock, Precio FROM Productos WHERE Stock > 0 ORDER BY Nombre",

    r"(?i)(qué|cuáles) productos (hay|tienen|venden) disponibles.*":
        "SELECT TOP 20 Nombre, Stock, Precio FROM Productos WHERE Stock > 0 ORDER BY Nombre",
        
    # Patrón específico para "stock disponible"
    r"(?i).*productos.*stock.*disponible.*":
        "SELECT TOP 20 Nombre, Stock, Precio FROM Productos WHERE Stock > 0 ORDER BY Nombre",
        
    r"(?i).*qué productos.*stock.*":
        "SELECT TOP 20 Nombre, Stock, Precio FROM Productos WHERE Stock > 0 ORDER BY Nombre",
                
    # Patrones más específicos para productos comunes
    r"(?i).*detergente.*líquido.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%detergente%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*leche.*deslactosada.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%leche%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*pila.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%pila%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*mouse.*inalámbrico.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%mouse%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*laptop.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%laptop%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*ssd.*500.*gb.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%ssd%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*rtx.*4090.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%tarjeta%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*mouse.*óptico.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%mouse%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*bebida.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%bebida%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*lácteo.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%leche%' OR Nombre COLLATE Latin1_General_CI_AI LIKE '%yogurt%' OR Nombre COLLATE Latin1_General_CI_AI LIKE '%queso%' AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*galleta.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%galleta%' AND Stock > 0 ORDER BY Precio ASC",
        
    # Patrones para consultas de rango de precios (MEJORADOS)
    r"(?i).*precio.*entre.*(\d+).*(\d+).*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*entre.*(\d+).*(\d+).*precio.*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*enséñame.*productos.*precio.*entre.*(\d+).*(\d+).*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*muéstrame.*productos.*precio.*entre.*(\d+).*(\d+).*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*productos.*precio.*entre.*(\d+).*(\d+).*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*cuyo.*precio.*esté.*entre.*(\d+).*(\d+).*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*precio.*de.*(\d+).*a.*(\d+).*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*desde.*(\d+).*hasta.*(\d+).*precio.*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Precio BETWEEN $1 AND $2 AND Stock > 0 ORDER BY Precio ASC",
        
    r"(?i).*menos.*(\d+).*caloría.*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Nombre COLLATE Latin1_General_CI_AI LIKE '%galleta%' AND Stock > 0 ORDER BY Precio ASC",
        
    # Patrones para consultas de disponibilidad general
    r"(?i).*productos.*disponibles.*":
        "SELECT TOP 10 Nombre, Precio, Stock FROM Productos WHERE Stock > 0 ORDER BY Stock DESC",
        
    r"(?i).*primeros.*cinco.*":
        "SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Stock > 0 ORDER BY Nombre ASC",
        
    r"(?i).*lista.*completa.*":
        "SELECT TOP 20 Nombre, Precio, Stock FROM Productos WHERE Stock > 0 ORDER BY Nombre ASC",
        
    # Patrones para consultas de stock bajo
    r"(?i).*agotarse.*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Stock <= 10 AND Stock > 0 ORDER BY Stock ASC",
        
    r"(?i).*stock.*bajo.*":
        "SELECT Nombre, Precio, Stock FROM Productos WHERE Stock <= 20 AND Stock > 0 ORDER BY Stock ASC",
        
}

# ---------------------------
# Funciones
# ---------------------------

def extract_product(question: str) -> Optional[str]:
    # Diccionario de productos comunes con sus variaciones (con y sin tildes) 
    # + corrección de errores ortográficos comunes
    PRODUCT_VARIATIONS = {
        'atun': ['atun', 'atún', 'adun', 'atum', 'adún'],  # Errores comunes: adun, atum, adún
        'azucar': ['azucar', 'azúcar', 'azukar'],
        'leche': ['leche', 'lece'],
        'arroz': ['arroz', 'aros', 'aroz', 'arozz'],
        'aceite': ['aceite', 'aceite', 'asseite', 'aseite'],  # Errores: asseite, aseite
        'queso': ['queso', 'keso'],
        'pan': ['pan'],
        'huevo': ['huevo', 'huevos', 'guevo', 'guevos'],
        'pollo': ['pollo', 'polo'],
        'carne': ['carne', 'karne'],
        'pescado': ['pescado', 'peskado'],
        'yogur': ['yogur', 'yogurt', 'iogur'],
        'mantequilla': ['mantequilla', 'mantekilla'],
        'sal': ['sal'],
        'harina': ['harina', 'arina'],
        'cafe': ['cafe', 'café', 'kafe'],
        'te': ['te', 'té'],
        'jugo': ['jugo', 'hugo'],
        'agua': ['agua', 'agwa'],
        'gaseosa': ['gaseosa', 'gaseoza'],
        'cerveza': ['cerveza', 'serbeza'],
        'vino': ['vino', 'bino'],
        'jabon': ['jabon', 'jabón', 'habon'],
        'detergente': ['detergente', 'deterjente'],
        'papel': ['papel', 'papel'],
        'servilleta': ['servilleta', 'servilletas', 'serbieta'],
        'toalla': ['toalla', 'toallas', 'toaja'],
        'shampoo': ['shampoo', 'champú', 'xampu'],
        'pasta': ['pasta', 'paza'],
        'galleta': ['galleta', 'galletas', 'gayeta'],
        'chocolate': ['chocolate', 'chokolate'],
        'dulce': ['dulce', 'dulces', 'dulse'],
        'caramelo': ['caramelo', 'caramelos', 'karamelo']
    }
    
    # Debug: log de la pregunta procesada
    logger.debug(f"🔍 DEBUG extract_product - Pregunta original: '{question}'")
    
    # Normalizar la pregunta (quitar tildes para comparación)
    normalized_question = text_processor.normalize_text(question.lower())
    logger.debug(f"🔍 DEBUG extract_product - Pregunta normalizada: '{normalized_question}'")
    
    # Buscar directamente productos conocidos en la pregunta con tolerancia a errores
    for base_product, variations in PRODUCT_VARIATIONS.items():
        for variation in variations:
            # Normalizar la variación para comparar sin tildes
            normalized_variation = text_processor.normalize_text(variation.lower())
            if normalized_variation in normalized_question:
                logger.debug(f"✅ DEBUG extract_product - ENCONTRADO: '{variation}' -> '{base_product}' en '{normalized_question}'")
                return base_product
    
    # Búsqueda por similitud para errores ortográficos no contemplados
    from difflib import SequenceMatcher
    words_in_question = normalized_question.split()
    
    for word in words_in_question:
        if len(word) > 3:  # Solo palabras de 4+ caracteres
            logger.debug(f"🔍 DEBUG extract_product - Probando palabra: '{word}'")
            for base_product, variations in PRODUCT_VARIATIONS.items():
                for variation in variations:
                    normalized_variation = text_processor.normalize_text(variation.lower())
                    # Calcular similitud (70% o más de similitud - bajado de 80%)
                    similarity = SequenceMatcher(None, word, normalized_variation).ratio()
                    logger.debug(f"🔍 DEBUG extract_product - '{word}' vs '{normalized_variation}': {similarity:.2f}")
                    if similarity >= 0.7:  # Bajado de 0.8 a 0.7
                        logger.debug(f"✅ DEBUG extract_product - SIMILITUD ENCONTRADA: '{word}' -> '{base_product}' (similitud: {similarity:.2f})")
                        return base_product
    
    # Fallback al método original si no encuentra productos específicos
    logger.debug(f"❌ DEBUG extract_product - No se encontraron productos específicos, usando fallback")
    keywords = text_processor.extract_keywords(normalized_question, 3)
    logger.debug(f"🔍 DEBUG extract_product - Keywords extraídas: {keywords}")
    
    non_product_words = {"quiero", "ver", "mostrar", "listar", "productos", "hay", "tienen", "disponible", "precio", "cuanto", "cuesta", "vale", "tiene", "tiele"}
    if keywords:
        for keyword in keywords:
            if len(keyword) > 3 and keyword.lower() not in non_product_words:
                logger.debug(f"✅ DEBUG extract_product - Keyword fallback encontrada: '{keyword}'")
                return keyword
    
    logger.debug(f"❌ DEBUG extract_product - NO se encontró ningún producto")
    return None


@timer
@measure_performance(operation_name="generate_sql_query")
def generate_sql_query(question: str, product_name: Optional[str] = None) -> str:
    logger.info(f"Generando consulta SQL para: '{question}'")
    
    # Debug: verificar extracción de producto
    extracted_product = extract_product(question)
    logger.debug(f"Producto extraído: '{extracted_product}'")

    for pattern, query in QUERY_PATTERNS.items():
        match = re.match(pattern, question, re.IGNORECASE)
        if match:
            return query

    if product_name:
        return f"SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%{product_name}%'"

    producto = extract_product(question)

    # Nueva validación estricta - incluye productos comunes con y sin tildes:
    palabras_clave_validas = [
        'fruta', 'limpieza', 'queso', 'arroz', 'esfero',
        'verdura', 'sin gluten', 'vegano', 'orgánico', 'descuento',
        'promoción', 'snack', 'papel', 'cuaderno', 'leche', 'azúcar', 'aceite', 'abarrote', 'bebida', 'mascota', 'bebé',
        # Productos comunes (normalizados sin tildes)
        'atun', 'azucar', 'pan', 'huevo', 'pollo', 'carne', 'pescado', 'yogur', 'mantequilla', 'sal', 'harina',
        'cafe', 'te', 'jugo', 'agua', 'gaseosa', 'cerveza', 'vino', 'jabon', 'detergente', 'servilleta', 'toalla',
        'shampoo', 'pasta', 'galleta', 'chocolate', 'dulce', 'caramelo'
    ]

    if producto and any(palabra in producto.lower() for palabra in palabras_clave_validas):
        # Para consultas de precio, usar ORDER BY Precio ASC
        if any(keyword in question.lower() for keyword in ['precio', 'cuesta', 'vale', 'costo', 'valor']):
            return f"SELECT TOP 5 Nombre, Precio, Stock FROM Productos WHERE Nombre LIKE '%{producto}%' AND Stock > 0 ORDER BY Precio ASC"
        else:
            return f"SELECT Nombre, Stock, Precio FROM Productos WHERE Nombre LIKE '%{producto}%'"

    # Si no pasa la validación, no genera nada
    return None


@timer
def execute_sql_with_fallback(question: str) -> Tuple[str, List[Dict[str, Any]], Dict[str, Any]]:
    sql_query = generate_sql_query(question)
    result = execute_query(sql_query)
    metadata = {
        "query": sql_query,
        "result_count": len(result) if result else 0
    }
    return sql_query, result, metadata
