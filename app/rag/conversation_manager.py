"""
Módulo para gestionar el contexto conversacional del chatbot
Mantiene el historial de conversaciones y referencias contextuales
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class ConversationTurn:
    """Representa un turno en la conversación"""
    question: str
    answer: str
    timestamp: datetime = field(default_factory=datetime.now)
    product_mentions: List[str] = field(default_factory=list)
    price_mentions: List[float] = field(default_factory=list)
    category_mentions: List[str] = field(default_factory=list)

@dataclass
class ConversationContext:
    """Representa el contexto de una conversación"""
    session_id: str
    user_id: str
    turns: List[ConversationTurn] = field(default_factory=list)
    last_activity: datetime = field(default_factory=datetime.now)
    current_topic: Optional[str] = None
    mentioned_products: List[str] = field(default_factory=list)
    mentioned_prices: List[float] = field(default_factory=list)
    conversation_flow: List[str] = field(default_factory=list)
    
    def add_turn(self, question: str, answer: str, product_mentions: List[str] = None, 
                 price_mentions: List[float] = None, category_mentions: List[str] = None):
        """Agrega un nuevo turno a la conversación"""
        turn = ConversationTurn(
            question=question,
            answer=answer,
            product_mentions=product_mentions or [],
            price_mentions=price_mentions or [],
            category_mentions=category_mentions or []
        )
        self.turns.append(turn)
        self.last_activity = datetime.now()
        
        # Actualizar contexto
        if product_mentions:
            self.mentioned_products.extend(product_mentions)
        if price_mentions:
            self.mentioned_prices.extend(price_mentions)
        if category_mentions:
            self.conversation_flow.extend(category_mentions)
    
    def get_recent_context(self, turns_back: int = 3) -> List[ConversationTurn]:
        """Obtiene los últimos turnos de la conversación"""
        return self.turns[-turns_back:] if len(self.turns) >= turns_back else self.turns
    
    def get_last_product_mentioned(self) -> Optional[str]:
        """Obtiene el último producto mencionado"""
        for turn in reversed(self.turns):
            if turn.product_mentions:
                return turn.product_mentions[-1]
        return None
    
    def get_last_price_mentioned(self) -> Optional[float]:
        """Obtiene el último precio mencionado"""
        for turn in reversed(self.turns):
            if turn.price_mentions:
                return turn.price_mentions[-1]
        return None
    
    def is_same_topic(self, question: str) -> bool:
        """Determina si la pregunta es sobre el mismo tema"""
        if not self.current_topic:
            return False
        
        topic_keywords = {
            "productos": ["producto", "disponible", "tienen", "hay", "stock", "unidades"],
            "precios": ["precio", "costo", "cuánto", "cuanto", "vale", "cuesta"],
            "entrega": ["entrega", "envío", "domicilio", "tiempo", "costo envío"],
            "horarios": ["horario", "abren", "cerrado", "atención", "domingo"],
            "ubicación": ["ubicado", "dirección", "dónde", "donde", "estacionamiento"],
            "fidelización": ["puntos", "programa", "fidelidad", "beneficios", "inscribir"],
            "promociones": ["promoción", "descuento", "oferta", "cupón", "especial"]
        }
        
        question_lower = question.lower()
        current_keywords = topic_keywords.get(self.current_topic, [])
        
        return any(keyword in question_lower for keyword in current_keywords)
    
    def update_topic(self, question: str):
        """Actualiza el tema actual de la conversación"""
        topic_keywords = {
            "productos": ["producto", "disponible", "tienen", "hay", "stock", "unidades"],
            "precios": ["precio", "costo", "cuánto", "cuanto", "vale", "cuesta"],
            "entrega": ["entrega", "envío", "domicilio", "tiempo", "costo envío"],
            "horarios": ["horario", "abren", "cerrado", "atención", "domingo"],
            "ubicación": ["ubicado", "dirección", "dónde", "donde", "estacionamiento"],
            "fidelización": ["puntos", "programa", "fidelidad", "beneficios", "inscribir"],
            "promociones": ["promoción", "descuento", "oferta", "cupón", "especial"]
        }
        
        question_lower = question.lower()
        for topic, keywords in topic_keywords.items():
            if any(keyword in question_lower for keyword in keywords):
                self.current_topic = topic
                break
    
    def is_expired(self, max_age_minutes: int = 30) -> bool:
        """Verifica si la conversación ha expirado"""
        return datetime.now() - self.last_activity > timedelta(minutes=max_age_minutes)

class ConversationManager:
    """Gestiona múltiples conversaciones y su contexto"""
    
    def __init__(self):
        self.conversations: Dict[str, ConversationContext] = {}
        self.max_conversations = 1000  # Límite de conversaciones activas
    
    def get_or_create_conversation(self, session_id: str, user_id: str = "default") -> ConversationContext:
        """Obtiene o crea una nueva conversación"""
        if session_id not in self.conversations:
            if len(self.conversations) >= self.max_conversations:
                self._cleanup_expired_conversations()
            
            self.conversations[session_id] = ConversationContext(
                session_id=session_id,
                user_id=user_id
            )
            logger.info(f"Nueva conversación creada: {session_id}")
        
        return self.conversations[session_id]
    
    def add_turn(self, session_id: str, question: str, answer: str, 
                 product_mentions: List[str] = None, price_mentions: List[float] = None,
                 category_mentions: List[str] = None, user_id: str = "default"):
        """Agrega un turno a la conversación"""
        conversation = self.get_or_create_conversation(session_id, user_id)
        conversation.update_topic(question)
        conversation.add_turn(question, answer, product_mentions, price_mentions, category_mentions)
        
        logger.debug(f"Turno agregado a conversación {session_id}: {len(conversation.turns)} turnos")
    
    def get_context_for_question(self, session_id: str, question: str, 
                                user_id: str = "default") -> Dict[str, Any]:
        """Obtiene el contexto relevante para una pregunta"""
        conversation = self.get_or_create_conversation(session_id, user_id)
        
        # Solo usar contexto si la pregunta actual menciona el mismo producto
        last_product = conversation.get_last_product_mentioned()
        question_lower = question.lower()
        
        # Verificar si la pregunta actual menciona el último producto
        should_use_context = False
        if last_product and last_product.lower() in question_lower:
            should_use_context = True
        
        context = {
            "session_id": session_id,
            "user_id": user_id,
            "recent_turns": conversation.get_recent_context(),
            "last_product": last_product if should_use_context else None,
            "last_price": conversation.get_last_price_mentioned() if should_use_context else None,
            "current_topic": conversation.current_topic,
            "is_same_topic": conversation.is_same_topic(question) and should_use_context,
            "mentioned_products": conversation.mentioned_products[-5:] if should_use_context else [],
            "conversation_flow": conversation.conversation_flow[-3:] if should_use_context else []
        }
        
        return context
    
    def generate_contextual_response(self, base_response: str, context: Dict[str, Any]) -> str:
        """Genera una respuesta contextual basada en el historial"""
        if not context.get("recent_turns"):
            return base_response
        
        # Solo agregar contexto si es realmente la misma pregunta sobre el mismo producto
        if context.get("is_same_topic") and context.get("last_product"):
            last_product = context["last_product"]
            
            # Verificar si la respuesta actual menciona el mismo producto que el contexto
            base_response_lower = base_response.lower()
            if last_product.lower() in base_response_lower:
                # Solo entonces agregar contexto si es realmente la misma consulta
                if "sí! tenemos" in base_response_lower or "encontré" in base_response_lower:
                    # Verificar que la pregunta actual sea realmente sobre el mismo producto
                    question_lower = context.get("recent_turns", [{}])[-1].question.lower() if context.get("recent_turns") else ""
                    if last_product.lower() in question_lower:
                        contextual_phrases = [
                            f"Como te mencioné anteriormente sobre {last_product},",
                            f"Continuando con {last_product},",
                            f"Respecto a {last_product},",
                            f"En cuanto a {last_product},",
                            f"Para {last_product},"
                        ]
                        return f"{contextual_phrases[0]} {base_response}"
            
            # Evitar respuestas genéricas de "no tenemos" para servicios
            if "lamentablemente, no tenemos" in base_response_lower:
                # Verificar si es una consulta de servicio
                if self._is_service_query(context.get("current_topic", "")):
                    return self._generate_service_response(context)
                else:
                    # Para productos, mantener la respuesta pero hacerla más natural
                    return f"Respecto a {last_product}, {base_response}"
        
        return base_response
    
    def _is_service_query(self, topic: str) -> bool:
        """Determina si el tema es un servicio"""
        service_topics = ["entrega", "horarios", "ubicación", "fidelización", "ayuda"]
        return topic in service_topics
    
    def _generate_service_response(self, context: Dict[str, Any]) -> str:
        """Genera respuestas apropiadas para consultas de servicios"""
        topic = context.get("current_topic", "")
        
        service_responses = {
            "entrega": "Sí, ofrecemos entrega a domicilio en un radio de 10 km. El costo de envío es de $2.50 y el tiempo de entrega es de 2-4 horas. Para pedidos mayores a $50, el envío es gratuito.",
            "horarios": "Nuestro horario de atención es de lunes a sábado de 8:00 AM a 8:00 PM, y domingos de 9:00 AM a 6:00 PM. Estamos cerrados en días festivos oficiales.",
            "ubicación": "Nos encontramos en la Av. Principal #123, Centro Comercial Plaza Mayor, Local 45. Estamos a 2 cuadras del parque central, con estacionamiento gratuito disponible.",
            "fidelización": "Tenemos un programa de fidelización con puntos acumulables. Por cada $10 de compra obtienes 1 punto. Los puntos se pueden canjear por descuentos en futuras compras.",
            "ayuda": "Estoy aquí para ayudarte con cualquier consulta sobre nuestros productos, precios, horarios, entrega o servicios. ¿En qué puedo asistirte específicamente?"
        }
        
        return service_responses.get(topic, "Te puedo ayudar con información sobre nuestros productos, servicios y horarios. ¿Qué necesitas saber específicamente?")
    
    def enhance_question_with_context(self, question: str, context: Dict[str, Any]) -> str:
        """Mejora la pregunta con información del contexto"""
        enhanced_question = question
        question_lower = question.lower()
        
        # Obtener el último producto mencionado del contexto
        last_product = context.get("last_product")
        recent_turns = context.get("recent_turns", [])
        
        # Manejar preguntas de seguimiento específicas
        if "muéstrame el resto" in question_lower or "muestrame el resto" in question_lower or "muestra más" in question_lower:
            if last_product:
                enhanced_question = f"¿Qué otros {last_product} tienen disponibles?"
            elif recent_turns:
                # Buscar en los últimos turnos qué producto se estaba consultando
                for turn in reversed(recent_turns):
                    if turn.product_mentions:
                        product = turn.product_mentions[-1]
                        enhanced_question = f"¿Qué otros {product} tienen disponibles?"
                        break
        
        elif "más" in question_lower and ("productos" in question_lower or "opciones" in question_lower):
            if last_product:
                enhanced_question = f"¿Qué otros {last_product} tienen disponibles?"
        
        elif "también" in question_lower or "además" in question_lower:
            if last_product:
                enhanced_question = f"¿Tienen {last_product} en otras variedades?"
        
        # Si es la misma pregunta sobre el mismo tema, agregar contexto
        elif context.get("is_same_topic") and last_product:
            if "precio" in question_lower and context.get("last_price"):
                enhanced_question = f"¿Cuál es el precio de {last_product}?"
            elif "stock" in question_lower or "unidades" in question_lower:
                enhanced_question = f"¿Cuántas unidades de {last_product} tienen en stock?"
            elif "marca" in question_lower:
                enhanced_question = f"¿Qué marcas de {last_product} tienen?"
            elif "disponible" in question_lower:
                enhanced_question = f"¿Tienen {last_product} disponible?"
            elif "recomendar" in question_lower or "recomiendas" in question_lower:
                enhanced_question = f"¿Pueden recomendarme una marca específica de {last_product}?"
            elif "integral" in question_lower or "especial" in question_lower:
                enhanced_question = f"¿Tienen {last_product} integral también?"
        
        return enhanced_question
    
    def _cleanup_expired_conversations(self):
        """Limpia conversaciones expiradas"""
        expired_sessions = [
            session_id for session_id, conversation in self.conversations.items()
            if conversation.is_expired()
        ]
        
        for session_id in expired_sessions:
            del self.conversations[session_id]
            logger.info(f"Conversación expirada eliminada: {session_id}")
    
    def get_conversation_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de las conversaciones"""
        active_conversations = len(self.conversations)
        total_turns = sum(len(conv.turns) for conv in self.conversations.values())
        avg_turns = total_turns / active_conversations if active_conversations > 0 else 0
        
        return {
            "active_conversations": active_conversations,
            "total_turns": total_turns,
            "average_turns_per_conversation": round(avg_turns, 2),
            "max_conversations": self.max_conversations
        }

# Instancia global del gestor de conversaciones
conversation_manager = ConversationManager() 