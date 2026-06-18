"""
Módulo para clasificar tipos de consulta y mejorar el contexto conversacional
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class QueryClassification:
    """Resultado de la clasificación de una consulta"""
    query_type: str  # "product", "service", "information", "general"
    confidence: float  # 0.0 a 1.0
    extracted_entities: List[str]
    context_hints: List[str]
    suggested_improvements: List[str]

class QueryClassifier:
    """Clasifica consultas y sugiere mejoras contextuales"""
    
    def __init__(self):
        # Patrones para productos
        self.product_patterns = {
            "alimentos": ["arroz", "leche", "aceite", "pan", "huevos", "carne", "pescado", "frutas", "verduras", "cereales", "pasta", "salsas", "condimentos", "bebidas", "jugos", "refrescos", "agua", "café", "té", "chocolate", "dulces", "galletas", "snacks", "atún", "tuna", "queso", "mantequilla", "azúcar", "azucar", "sal", "harina", "frijoles", "lentejas", "tomate", "cebolla", "papa", "zanahoria", "manzana", "plátano", "naranja", "limón", "limon", "ajo", "pimienta", "comino", "orégano", "oregano", "canela", "vainilla", "cocoa", "avena", "maíz", "maiz", "trigo", "soya", "soja"],
            "limpieza": ["detergente", "jabón", "jabon", "shampoo", "papel higiénico", "papel higienico", "toallas", "desinfectante", "limpiador", "escoba", "trapeador", "bolsas", "pañales", "pañal", "servilletas", "toallas de papel", "cloro", "suavizante", "lavavajillas", "lavavajilla", "limpiavidrios", "limpia pisos", "limpiapisos", "desodorante ambiental", "ambientador", "insecticida", "repelente"],
            "cuidado_personal": ["desodorante", "crema", "pasta dental", "pasta de dientes", "cepillo", "cepillo de dientes", "peine", "maquillaje", "perfume", "protector solar", "papel de baño", "papel sanitario", "shampoo", "acondicionador", "gel", "cera", "pomada", "talco", "toallas sanitarias", "tampones", "pañitos húmedos", "pañitos humedos", "algodón", "algodon", "hisopos", "espejo", "tijeras de uñas"],
            "hogar": ["baterías", "baterias", "bombillos", "cables", "herramientas", "pintura", "pegamento", "cinta", "papel", "lápices", "lapices", "lápiz", "lapiz", "cuadernos", "libretas", "plumas", "bolígrafos", "boligrafos", "marcadores", "tijeras", "grapas", "clips", "resaltador", "resaltadores", "goma", "borrador", "regla", "compás", "compas", "calculadora", "mochila", "lonchera", "termo", "vaso", "plato", "cuchara", "tenedor", "cuchillo", "olla", "sartén", "sarten", "refrigerador", "microondas", "licuadora", "batidora", "cafetera", "tostadora", "plancha", "aspiradora", "ventilador", "calentador", "manta", "almohada", "sábana", "sabana", "cortina", "alfombra", "maceta", "planta", "flor", "semilla", "fertilizante", "pesticida"],
            "tecnologia": ["monitor", "monitores", "teclado", "teclados", "mouse", "ratón", "ratones", "laptop", "computadora", "pc", "tablet", "celular", "teléfono", "telefono", "cámara", "camara", "auriculares", "altavoces", "bocinas", "cable", "cables", "cargador", "cargadores", "adaptador", "adaptadores", "usb", "hdmi", "vga", "impresora", "escáner", "escaner", "router", "modem", "antena", "control remoto", "control", "batería", "bateria", "memoria", "disco duro", "pendrive", "cd", "dvd", "bluray", "consola", "videojuego", "video juego"],
            "papeleria": ["esfero", "esferos", "bolígrafo", "boligrafo", "bolígrafos", "boligrafos", "lápiz", "lapiz", "lápices", "lapices", "cuaderno", "cuadernos", "libreta", "libretas", "marcador", "marcadores", "resaltador", "resaltadores", "tijera", "tijeras", "grapa", "grapas", "clip", "clips", "pegamento", "cinta", "papel", "hojas", "carpeta", "archivador", "sobre", "sobres", "etiqueta", "etiquetas", "póster", "poster", "pizarra", "borrador", "tiza", "marcador de pizarra", "pizarrón", "pizarron"],
            "mascotas": ["perro", "gato", "mascota", "mascotas", "alimento para perro", "alimento para gato", "croquetas", "galletas para perro", "galletas para gato", "juguete para perro", "juguete para gato", "collar", "correa", "plato", "cama para mascota", "arena para gato", "shampoo para mascota", "cepillo para mascota", "vacuna", "medicamento", "vitamina", "suplemento"],
            "bebes": ["bebé", "bebe", "bebés", "bebes", "pañal", "pañales", "leche en polvo", "fórmula", "formula", "biberón", "biberon", "chupón", "chupon", "juguete para bebé", "juguete para bebe", "ropa para bebé", "ropa para bebe", "crema para bebé", "crema para bebe", "toallitas húmedas", "toallitas humedas", "papilla", "cereal para bebé", "cereal para bebe"],
            "deportes": ["pelota", "balón", "balon", "raqueta", "red", "portería", "porteria", "guante", "guantes", "casco", "cascos", "rodillera", "rodilleras", "botella de agua", "termo", "mochila deportiva", "tenis", "zapatillas", "calcetines", "calcetas", "short", "shorts", "camiseta", "camisetas", "sudadera", "sudadera", "pantalón deportivo", "pantalon deportivo"],
            "productos_genericos": ["producto", "productos", "artículo", "articulo", "artículos", "articulos", "mercancía", "mercancia", "mercancías", "mercancias", "item", "items", "cosa", "cosas", "objeto", "objetos"]
        }
        
        # Patrones para servicios
        self.service_patterns = {
            "entrega": ["entrega", "envío", "domicilio", "reparto", "delivery", "llevar", "traer", "mandar"],
            "horarios": ["horario", "abren", "cerrado", "atención", "abierto", "cerrar", "domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"],
            "ubicación": ["ubicado", "dirección", "dónde", "donde", "estacionamiento", "parqueo", "lugar", "zona", "barrio", "calle", "avenida"],
            "fidelización": ["puntos", "programa", "fidelidad", "beneficios", "inscribir", "acumular", "descuentos", "promociones", "cupones"],
            "ayuda": ["ayudar", "ayuda", "buscar", "encontrar", "recomendar", "sugerir", "orientar", "guiar", "explicar", "informar"]
        }
        
        # Patrones para información general
        self.info_patterns = {
            "precios": ["precio", "costo", "cuánto", "cuanto", "vale", "cuesta", "económico", "barato", "caro", "oferta", "descuento"],
            "stock": ["stock", "disponible", "tienen", "hay", "unidades", "cantidad", "cuántos", "cuanto", "cuántas", "cuantas"],
            "marcas": ["marca", "marcas", "específica", "específico", "recomendar", "recomendación"],
            "promociones": ["promoción", "oferta", "descuento", "especial", "rebaja", "liquidación", "evento"]
        }
        
        # Pronombres y referencias contextuales
        self.context_pronouns = {
            "producto": ["él", "ella", "este", "esta", "ese", "esa", "lo", "la", "su", "sus"],
            "precio": ["cuánto", "cuanto", "vale", "cuesta", "precio"],
            "stock": ["cuántos", "cuanto", "cuántas", "cuantas", "unidades", "hay", "tienen"],
            "marca": ["cuál", "cual", "marca", "marcas", "recomiendas", "recomiendan"]
        }
    
    def classify_query(self, question: str, context: Dict = None) -> QueryClassification:
        """Clasifica una consulta y sugiere mejoras"""
        question_lower = question.lower().strip()
        
        # Detectar tipo de consulta
        query_type, confidence = self._detect_query_type(question_lower)
        
        # Extraer entidades
        extracted_entities = self._extract_entities(question_lower)
        
        # Obtener pistas contextuales
        context_hints = self._get_context_hints(question_lower, context)
        
        # Sugerir mejoras
        suggested_improvements = self._suggest_improvements(question_lower, query_type, context)
        
        return QueryClassification(
            query_type=query_type,
            confidence=confidence,
            extracted_entities=extracted_entities,
            context_hints=context_hints,
            suggested_improvements=suggested_improvements
        )
    
    def _detect_query_type(self, question: str) -> Tuple[str, float]:
        """Detecta el tipo de consulta con nivel de confianza"""
        scores = {
            "product": 0.0,
            "service": 0.0,
            "information": 0.0,
            "general": 0.0
        }
        
        # Calcular puntuación para productos
        for category, words in self.product_patterns.items():
            for word in words:
                if word in question:
                    scores["product"] += 1.0
        
        # Calcular puntuación para servicios
        for category, words in self.service_patterns.items():
            for word in words:
                if word in question:
                    scores["service"] += 1.0
        
        # Calcular puntuación para información
        for category, words in self.info_patterns.items():
            for word in words:
                if word in question:
                    scores["information"] += 1.0
        
        # Normalizar puntuaciones
        total_words = len(question.split())
        for query_type in scores:
            scores[query_type] = min(scores[query_type] / max(total_words, 1), 1.0)
        
        # Determinar tipo dominante
        max_score = max(scores.values())
        if max_score == 0:
            return "general", 0.5
        
        # 🚀 LÓGICA MEJORADA: Distinguir entre consultas de información específica y productos generales
        
        # Detectar consultas de información específica sobre productos
        info_indicators = ["cuánto cuesta", "cuanto cuesta", "qué precio", "que precio", "qué marcas", "que marcas", "cuál es el precio", "cual es el precio"]
        has_info_indicator = any(indicator in question.lower() for indicator in info_indicators)
        
        # Si hay indicadores de información específica, priorizar información
        if has_info_indicator and scores["information"] > 0:
            return "information", scores["information"]
        
        # Si hay productos específicos mencionados y no es consulta de información específica
        if scores["product"] > 0 and not has_info_indicator:
            return "product", scores["product"]
        
        # Lógica de priorización estándar
        if scores["information"] == max_score:
            return "information", max_score
        elif scores["service"] == max_score:
            return "service", max_score
        elif scores["product"] == max_score:
            return "product", max_score
        else:
            return "general", max_score
    
    def _extract_entities(self, question: str) -> List[str]:
        """Extrae entidades mencionadas en la pregunta"""
        entities = []
        
        # Buscar productos específicos
        for category, words in self.product_patterns.items():
            for word in words:
                if word in question:
                    entities.append(word)
        
        # Buscar servicios específicos
        for category, words in self.service_patterns.items():
            for word in words:
                if word in question:
                    entities.append(word)
        
        # Buscar información específica
        for category, words in self.info_patterns.items():
            for word in words:
                if word in question:
                    entities.append(word)
        
        return list(set(entities))  # Eliminar duplicados
    
    def _get_context_hints(self, question: str, context: Dict = None) -> List[str]:
        """Obtiene pistas contextuales de la pregunta"""
        hints = []
        
        # Detectar pronombres y referencias
        for reference_type, pronouns in self.context_pronouns.items():
            for pronoun in pronouns:
                if pronoun in question:
                    hints.append(f"referencia_{reference_type}")
                    break
        
        # Detectar preguntas incompletas
        if len(question.split()) <= 3:
            hints.append("pregunta_incompleta")
        
        # Detectar preguntas de seguimiento
        follow_up_indicators = ["también", "además", "otro", "otra", "más", "cuál", "cual", "qué", "que"]
        for indicator in follow_up_indicators:
            if indicator in question:
                hints.append("pregunta_seguimiento")
                break
        
        return hints
    
    def _suggest_improvements(self, question: str, query_type: str, context: Dict = None) -> List[str]:
        """Sugiere mejoras para la pregunta"""
        improvements = []
        
        # Si es pregunta incompleta y hay contexto
        if "pregunta_incompleta" in self._get_context_hints(question) and context:
            last_product = context.get("last_product")
            if last_product and query_type == "product":
                improvements.append(f"Completar con producto anterior: '{last_product}'")
        
        # Si hay referencias contextuales
        context_hints = self._get_context_hints(question)
        if "referencia_producto" in context_hints and context:
            last_product = context.get("last_product")
            if last_product:
                improvements.append(f"Reemplazar referencia con: '{last_product}'")
        
        # Si es consulta de servicio pero se clasifica como producto
        if query_type == "product" and any(word in question for word in self.service_patterns["entrega"] + self.service_patterns["horarios"] + self.service_patterns["ubicación"]):
            improvements.append("Clasificar como consulta de servicio")
        
        return improvements
    
    def enhance_question_with_context(self, question: str, context: Dict = None) -> str:
        """Mejora la pregunta usando el contexto"""
        classification = self.classify_query(question, context)
        enhanced_question = question
        
        # Si es pregunta incompleta y hay contexto
        if "pregunta_incompleta" in classification.context_hints and context:
            last_product = context.get("last_product")
            if last_product and classification.query_type == "product":
                # Mejorar preguntas específicas
                if "precio" in question.lower():
                    enhanced_question = f"¿Cuál es el precio de {last_product}?"
                elif "stock" in question.lower() or "unidades" in question.lower():
                    enhanced_question = f"¿Cuántas unidades de {last_product} tienen en stock?"
                elif "marca" in question.lower():
                    enhanced_question = f"¿Qué marcas de {last_product} tienen?"
                elif "disponible" in question.lower():
                    enhanced_question = f"¿Tienen {last_product} disponible?"
        
        # Si hay referencias contextuales
        if "referencia_producto" in classification.context_hints and context:
            last_product = context.get("last_product")
            if last_product:
                # Reemplazar pronombres con el producto específico
                enhanced_question = re.sub(r'\b(él|ella|este|esta|ese|esa|lo|la)\b', last_product, enhanced_question, flags=re.IGNORECASE)
        
        return enhanced_question
    
    def should_use_service_response(self, question: str) -> bool:
        """Determina si debe usar respuesta de servicio en lugar de producto"""
        classification = self.classify_query(question)
        
        # Si es claramente un servicio
        if classification.query_type == "service":
            return True
        
        # Si contiene palabras de servicio específicas
        service_words = []
        for category, words in self.service_patterns.items():
            service_words.extend(words)
        
        return any(word in question.lower() for word in service_words)

# Instancia global del clasificador
query_classifier = QueryClassifier() 