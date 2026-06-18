"""
API endpoints para el sistema de aprendizaje automático
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
import logging

from app.learning.integrator import learning_integrator
from app.api.auth import get_current_active_user as get_current_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["learning"])

@router.get("/insights")
async def get_learning_insights(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Obtiene insights del sistema de aprendizaje automático
    """
    try:
        insights = learning_integrator.get_learning_stats()
        return {
            "success": True,
            "data": insights,
            "message": "Insights del sistema de aprendizaje obtenidos correctamente"
        }
    except Exception as e:
        logger.error(f"Error al obtener insights de aprendizaje: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener insights de aprendizaje")

@router.get("/suggestions/{category}")
async def get_learning_suggestions(category: str, current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Obtiene sugerencias de mejora para una categoría específica
    """
    try:
        suggestions = learning_integrator.get_learning_suggestions(category)
        return {
            "success": True,
            "data": {
                "category": category,
                "suggestions": suggestions
            },
            "message": f"Sugerencias de mejora para categoría '{category}' obtenidas correctamente"
        }
    except Exception as e:
        logger.error(f"Error al obtener sugerencias de aprendizaje: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener sugerencias de aprendizaje")

@router.get("/faq-suggestions")
async def get_faq_suggestions(question: str, current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Obtiene sugerencias de FAQ basadas en una pregunta
    """
    try:
        suggestions = learning_integrator.get_faq_suggestions(question)
        return {
            "success": True,
            "data": {
                "question": question,
                "suggestions": suggestions
            },
            "message": "Sugerencias de FAQ obtenidas correctamente"
        }
    except Exception as e:
        logger.error(f"Error al obtener sugerencias FAQ: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener sugerencias FAQ")

@router.post("/analyze-response")
async def analyze_response_quality(
    question: str,
    response: str,
    category: str,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Analiza la calidad de una respuesta
    """
    try:
        analysis = learning_integrator.analyze_response_quality(question, response, category)
        return {
            "success": True,
            "data": analysis,
            "message": "Análisis de calidad de respuesta completado"
        }
    except Exception as e:
        logger.error(f"Error al analizar calidad de respuesta: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al analizar calidad de respuesta")

@router.get("/patterns")
async def get_learned_patterns(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Obtiene los patrones aprendidos por el sistema
    """
    try:
        patterns = learning_integrator.learning_manager.learned_patterns
        pattern_summary = []

        for pattern_id, pattern in patterns.items():
            pattern_summary.append({
                "id": pattern_id,
                "type": pattern.pattern_type,
                "confidence": pattern.confidence,
                "frequency": pattern.frequency,
                "success_rate": pattern.success_rate,
                "last_updated": pattern.last_updated.isoformat()
            })

        return {
            "success": True,
            "data": {
                "total_patterns": len(patterns),
                "patterns": pattern_summary
            },
            "message": "Patrones aprendidos obtenidos correctamente"
        }
    except Exception as e:
        logger.error(f"Error al obtener patrones aprendidos: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener patrones aprendidos")

@router.get("/faq-database")
async def get_faq_database(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Obtiene la base de datos FAQ dinámica
    """
    try:
        faq_data = learning_integrator.learning_manager.faq_database
        return {
            "success": True,
            "data": {
                "total_entries": len(faq_data),
                "faq_entries": faq_data
            },
            "message": "Base de datos FAQ obtenida correctamente"
        }
    except Exception as e:
        logger.error(f"Error al obtener base de datos FAQ: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al obtener base de datos FAQ")

@router.post("/feedback")
async def record_user_feedback(
    question: str,
    response: str,
    rating: int,  # 1-5
    comment: str = None,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Registra feedback del usuario sobre una respuesta
    """
    try:
        if not 1 <= rating <= 5:
            raise HTTPException(status_code=400, detail="El rating debe estar entre 1 y 5")

        # Crear interacción con feedback
        from app.learning.learning_manager import Interaction
        from datetime import datetime
        import uuid

        interaction = Interaction(
            id=str(uuid.uuid4()),
            user_id=current_user.get("email", "unknown"),
            session_id=f"feedback_{datetime.now().isoformat()}",
            question=question,
            answer=response,
            success=rating >= 4,  # Considerar exitoso si rating >= 4
            confidence=rating / 5.0,  # Normalizar rating a confianza
            response_time=0.0,  # No disponible en feedback
            timestamp=datetime.now(),
            product_mentions=[],
            category="feedback",
            user_feedback=rating,
            user_comment=comment
        )

        # Registrar en el sistema de aprendizaje
        learning_integrator.learning_manager.record_interaction(interaction)

        return {
            "success": True,
            "message": "Feedback registrado correctamente",
            "data": {
                "interaction_id": interaction.id,
                "rating": rating,
                "success": interaction.success
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al registrar feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al registrar feedback")
