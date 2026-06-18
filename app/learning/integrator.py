"""
Integrador del Sistema de Aprendizaje Automático
Conecta el sistema de aprendizaje con el retriever existente
"""

import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import logging

from app.learning.learning_manager import learning_manager, Interaction
from app.rag.query_classifier import query_classifier
from app.utils.logger import get_logger

logger = get_logger(__name__)

class LearningIntegrator:
    """Integra el sistema de aprendizaje con el retriever"""
    
    def __init__(self):
        self.learning_manager = learning_manager
        logger.info("Integrador de aprendizaje inicializado")
    
    def enhance_response_with_learning(self, 
                                     question: str, 
                                     original_response: str, 
                                     category: str,
                                     user_id: str = "default",
                                     session_id: str = None,
                                     confidence: float = 0.0,
                                     response_time: float = 0.0,
                                     product_mentions: list = None) -> Tuple[str, bool]:
        """
        Mejora la respuesta usando el sistema de aprendizaje
        
        Returns:
            Tuple[str, bool]: (respuesta_mejorada, usa_aprendizaje)
        """
        try:
            # Intentar obtener respuesta aprendida
            learned_response = self.learning_manager.get_learned_response(question, category)
            
            if learned_response and learned_response != original_response:
                logger.info(f"Usando respuesta aprendida para: {question[:50]}...")
                return learned_response, True
            
            # Si no hay respuesta aprendida, usar la original
            return original_response, False
            
        except Exception as e:
            logger.error(f"Error al mejorar respuesta con aprendizaje: {str(e)}")
            return original_response, False
    
    def record_interaction_for_learning(self,
                                      question: str,
                                      response: str,
                                      category: str,
                                      success: bool,
                                      confidence: float,
                                      response_time: float,
                                      user_id: str = "default",
                                      session_id: str = None,
                                      product_mentions: list = None,
                                      user_feedback: Optional[int] = None,
                                      user_comment: Optional[str] = None):
        """Registra una interacción para el sistema de aprendizaje"""
        try:
            # Crear ID único para la interacción
            interaction_id = str(uuid.uuid4())
            
            # Crear objeto de interacción
            interaction = Interaction(
                id=interaction_id,
                user_id=user_id,
                session_id=session_id or f"session_{user_id}",
                question=question,
                answer=response,
                success=success,
                confidence=confidence,
                response_time=response_time,
                timestamp=datetime.now(),
                product_mentions=product_mentions or [],
                category=category,
                user_feedback=user_feedback,
                user_comment=user_comment
            )
            
            # Registrar en el sistema de aprendizaje
            self.learning_manager.record_interaction(interaction)
            
            logger.debug(f"Interacción registrada para aprendizaje: {interaction_id}")
            
        except Exception as e:
            logger.error(f"Error al registrar interacción para aprendizaje: {str(e)}")
    
    def get_learning_suggestions(self, category: str) -> list:
        """Obtiene sugerencias de mejora basadas en el aprendizaje"""
        try:
            insights = self.learning_manager.get_learning_insights()
            
            suggestions = []
            
            # Analizar patrones de mejora para la categoría
            improvement_pattern = self.learning_manager.learned_patterns.get(f"improvement_{category}")
            if improvement_pattern:
                suggestions.extend(improvement_pattern.pattern_data.get("improvement_suggestions", []))
            
            # Analizar estadísticas generales
            if insights.get("success_rate", 0) < 0.8:
                suggestions.append("La tasa de éxito general está por debajo del 80%. Revisar respuestas fallidas.")
            
            if insights.get("avg_confidence", 0) < 0.7:
                suggestions.append("La confianza promedio está baja. Considerar mejorar la clasificación de consultas.")
            
            if insights.get("avg_response_time", 0) > 3.0:
                suggestions.append("El tiempo de respuesta promedio es alto. Optimizar consultas y procesamiento.")
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error al obtener sugerencias de aprendizaje: {str(e)}")
            return []
    
    def get_faq_suggestions(self, question: str) -> list:
        """Obtiene sugerencias de FAQ basadas en la pregunta"""
        try:
            insights = self.learning_manager.get_learning_insights()
            top_questions = insights.get("top_questions", [])
            
            suggestions = []
            
            # Buscar preguntas similares en las más frecuentes
            for q_data in top_questions:
                question_text = q_data.get("question", "")
                count = q_data.get("count", 0)
                
                # Calcular similitud
                similarity = self.learning_manager._calculate_similarity(question, question_text)
                
                if similarity > 0.6 and count >= 3:
                    suggestions.append(f"Pregunta similar frecuente: '{question_text}' (aparece {count} veces)")
            
            return suggestions[:3]  # Máximo 3 sugerencias
            
        except Exception as e:
            logger.error(f"Error al obtener sugerencias FAQ: {str(e)}")
            return []
    
    def analyze_response_quality(self, question: str, response: str, category: str) -> Dict[str, Any]:
        """Analiza la calidad de una respuesta"""
        try:
            analysis = {
                "length_score": min(len(response) / 100, 1.0),  # Normalizar longitud
                "has_price_info": "precio" in response.lower() or "$" in response,
                "has_stock_info": "stock" in response.lower() or "unidades" in response.lower(),
                "has_availability_info": "disponible" in response.lower() or "hay" in response.lower(),
                "has_product_info": any(word in response.lower() for word in ["producto", "artículo", "item"]),
                "response_type": self._classify_response_type(response),
                "suggestions": []
            }
            
            # Calcular puntuación general
            score_components = [
                analysis["length_score"] * 0.2,
                1.0 if analysis["has_price_info"] else 0.0 * 0.2,
                1.0 if analysis["has_stock_info"] else 0.0 * 0.2,
                1.0 if analysis["has_availability_info"] else 0.0 * 0.2,
                1.0 if analysis["has_product_info"] else 0.0 * 0.2
            ]
            
            analysis["overall_score"] = sum(score_components)
            
            # Generar sugerencias de mejora
            if not analysis["has_price_info"]:
                analysis["suggestions"].append("Considerar incluir información de precios")
            if not analysis["has_stock_info"]:
                analysis["suggestions"].append("Considerar incluir información de stock")
            if not analysis["has_availability_info"]:
                analysis["suggestions"].append("Considerar incluir información de disponibilidad")
            if analysis["length_score"] < 0.3:
                analysis["suggestions"].append("La respuesta podría ser más detallada")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error al analizar calidad de respuesta: {str(e)}")
            return {"overall_score": 0.0, "suggestions": ["Error en análisis"]}
    
    def _classify_response_type(self, response: str) -> str:
        """Clasifica el tipo de respuesta"""
        response_lower = response.lower()
        
        if "precio" in response_lower and "stock" in response_lower:
            return "comprehensive"
        elif "precio" in response_lower:
            return "price_focused"
        elif "stock" in response_lower or "disponible" in response_lower:
            return "availability_focused"
        elif "horario" in response_lower or "ubicación" in response_lower:
            return "service_info"
        elif "no" in response_lower and ("encontré" in response_lower or "tengo" in response_lower):
            return "not_found"
        else:
            return "general"
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema de aprendizaje"""
        try:
            insights = self.learning_manager.get_learning_insights()
            
            stats = {
                "total_interactions": insights.get("total_interactions", 0),
                "success_rate": insights.get("success_rate", 0),
                "avg_confidence": insights.get("avg_confidence", 0),
                "avg_response_time": insights.get("avg_response_time", 0),
                "learned_patterns": len(self.learning_manager.learned_patterns),
                "faq_entries": insights.get("faq_entries_count", 0),
                "top_categories": insights.get("top_categories", []),
                "recent_activity": self._get_recent_activity()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error al obtener estadísticas de aprendizaje: {str(e)}")
            return {}
    
    def _get_recent_activity(self) -> Dict[str, Any]:
        """Obtiene actividad reciente del sistema de aprendizaje"""
        try:
            # Obtener interacciones de las últimas 24 horas
            recent_interactions = self.learning_manager._get_recent_interactions(100)
            
            # Filtrar por las últimas 24 horas
            cutoff_time = datetime.now() - timedelta(hours=24)
            recent_24h = [i for i in recent_interactions if i.timestamp > cutoff_time]
            
            return {
                "last_24h_interactions": len(recent_24h),
                "last_24h_success_rate": sum(1 for i in recent_24h if i.success) / len(recent_24h) if recent_24h else 0,
                "patterns_updated_today": len([p for p in self.learning_manager.learned_patterns.values() 
                                             if p.last_updated.date() == datetime.now().date()])
            }
            
        except Exception as e:
            logger.error(f"Error al obtener actividad reciente: {str(e)}")
            return {}

# Instancia global del integrador
learning_integrator = LearningIntegrator() 