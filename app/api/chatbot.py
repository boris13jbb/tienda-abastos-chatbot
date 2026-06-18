"""
API para el Chatbot de la Tienda de Abastos.
Define los endpoints para interactuar con el chatbot.
"""

import logging
import time
from fastapi import APIRouter, Depends, Header, Request, status, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from datetime import datetime

from app.rag.retriever import retriever
from app.security.auth import verify_token
from app.utils.logger import get_logger
from app.utils.logger_chatbot import guardar_interaccion
from app.utils.performance_metrics import performance_monitor

# Configurar logging específico para este módulo
logger = get_logger(__name__)

# Crear router para las rutas del chatbot
router = APIRouter()

# Modelos de datos para la API
class QueryRequest(BaseModel):
    """Modelo para las solicitudes de consulta al chatbot."""
    pregunta: str
    estilo: str = "largo"  # Valores posibles: "corto" o "largo"
    session_id: Optional[str] = None  # ID de sesión para contexto conversacional

class QueryResponse(BaseModel):
    """Modelo para las respuestas del chatbot."""
    respuesta: str

class ChatStatistics(BaseModel):
    """Modelo para estadísticas del chat."""
    total_consultas: int
    usuarios_activos: int
    Productos_populares: List[str]
    tasa_respuesta_exitosa: float

# Middleware para verificar autenticación (requerida para empleados)
async def verify_employee_token(authorization: Optional[str] = Header(None)):
    """
    Middleware que verifica el token de autenticación de empleados.
    Requiere autenticación para todas las operaciones.
    
    Args:
        authorization: Header de autorización con el token.
        
    Returns:
        Información del token o error.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido"
        )
    
    try:
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        
        # Verificar que sea un empleado autorizado
        if not token_data.get("rol") or token_data.get("rol") not in ["dueño", "empleado", "administrador", "admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado. Solo empleados autorizados."
            )
        
        return token_data
    except Exception as e:
        logger.warning(f"Token inválido: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )

# Diccionario para almacenar historial de conversaciones (solo empleados)
conversation_history = {}

# Ruta para preguntar al chatbot - Solo empleados autorizados
@router.post("/preguntar", response_model=QueryResponse, summary="Realizar una consulta al chatbot")
async def hacer_pregunta_post(
    req: QueryRequest,
    request: Request,
    token_data: dict = Depends(verify_employee_token)
):
    """
    Endpoint para realizar preguntas al chatbot (método POST).
    Solo empleados autorizados pueden acceder.
    
    Args:
        req: Datos de la pregunta.
        request: Información de la solicitud HTTP.
        token_data: Datos del token de autenticación.
        
    Returns:
        Respuesta del chatbot.
    """
    start_time = time.time()
    success = True
    error_message = None
    
    try:
        # Obtener identificador del empleado
        employee_id = token_data.get("sub")
        employee_name = token_data.get("name", "Empleado")
        employee_role = token_data.get("rol", "empleado")
        
        # Registrar información sobre la consulta
        logger.info(f"Empleado {employee_name} ({employee_role}) pregunta: {req.pregunta}")

        # Procesar la pregunta con el chatbot, considerando el historial
        respuesta = retriever(req.pregunta, req.estilo, employee_id, req.session_id)
        logger.debug(f"Respuesta generada: {respuesta}")

        # Guardar el log
        guardar_interaccion(
            pregunta=req.pregunta,
            respuesta=respuesta,
            prompt_tokens=len(req.pregunta.split()),  # Aproximación sencilla
            completion_tokens=len(respuesta.split())  # Aproximación sencilla
        )

        
        # Guardar en historial (últimas 5 interacciones por empleado)
        if employee_id not in conversation_history:
            conversation_history[employee_id] = []
        
        conversation_history[employee_id].append({
            "pregunta": req.pregunta,
            "respuesta": respuesta,
            "empleado": employee_name,
            "rol": employee_role,
            "timestamp": datetime.now().isoformat()
        })
        
        # Mantener solo las últimas 5 conversaciones
        if len(conversation_history[employee_id]) > 5:
            conversation_history[employee_id] = conversation_history[employee_id][-5:]
        
        # Asegurar que la respuesta no esté vacía
        if not respuesta or len(respuesta.strip()) == 0:
            respuesta = "No pude encontrar información sobre eso. ¿Puedo ayudarte con algo más?"
            
        return {"respuesta": respuesta}
    except Exception as e:
        success = False
        error_message = str(e)
        logger.error(f"Error al procesar pregunta: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"respuesta": "Ocurrió un error inesperado. Por favor intenta nuevamente."}
    finally:
        # 🚀 NUEVO: Registrar métrica de rendimiento
        response_time = time.time() - start_time
        performance_monitor.add_metric(
            response_time=response_time,
            operation_type="chatbot_query",
            success=success,
            error_message=error_message
        )

@router.get("/preguntar", response_model=QueryResponse, summary="Realizar una consulta al chatbot (GET)")
async def hacer_pregunta_get(
    pregunta: str,
    request: Request,
    estilo: str = "largo",
    token_data: dict = Depends(verify_employee_token)
):
    """
    Endpoint para realizar preguntas al chatbot (método GET).
    Solo empleados autorizados pueden acceder.
    
    Args:
        pregunta: Texto de la pregunta.
        request: Información de la solicitud HTTP.
        estilo: Estilo de respuesta.
        token_data: Datos del token de autenticación.
        
    Returns:
        Respuesta del chatbot.
    """
    start_time = time.time()
    success = True
    error_message = None
    
    try:
        # Obtener identificador del empleado
        employee_id = token_data.get("sub")
        employee_name = token_data.get("name", "Empleado")
        employee_role = token_data.get("rol", "empleado")
        
        # Registrar información sobre la consulta
        logger.info(f"Empleado {employee_name} ({employee_role}) pregunta: {pregunta}")

        # Procesar la pregunta con el chatbot
        respuesta = retriever(pregunta, estilo, employee_id)
        logger.debug(f"Respuesta generada: {respuesta}")

        # Guardar el log
        guardar_interaccion(
            pregunta=pregunta,
            respuesta=respuesta,
            prompt_tokens=len(pregunta.split()),  # Aproximación sencilla
            completion_tokens=len(respuesta.split())  # Aproximación sencilla
        )

        
        # Guardar en historial (últimas 5 interacciones por empleado)
        if employee_id not in conversation_history:
            conversation_history[employee_id] = []
        
        conversation_history[employee_id].append({
            "pregunta": pregunta,
            "respuesta": respuesta,
            "empleado": employee_name,
            "rol": employee_role,
            "timestamp": datetime.now().isoformat()
        })
        
        # Mantener solo las últimas 5 conversaciones
        if len(conversation_history[employee_id]) > 5:
            conversation_history[employee_id] = conversation_history[employee_id][-5:]
        
        # Asegurar que la respuesta no esté vacía
        if not respuesta or len(respuesta.strip()) == 0:
            respuesta = "No pude encontrar información sobre eso. ¿Puedo ayudarte con algo más?"
        
        return {"respuesta": respuesta}

    except Exception as e:
        success = False
        error_message = str(e)
        logger.error(f"Error al procesar pregunta: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"respuesta": "Ocurrió un error inesperado. Por favor intenta nuevamente."}
    finally:
        # 🚀 NUEVO: Registrar métrica de rendimiento
        response_time = time.time() - start_time
        performance_monitor.add_metric(
            response_time=response_time,
            operation_type="chatbot_query_get",
            success=success,
            error_message=error_message
        )

@router.get("/sugerencias", summary="Obtener sugerencias de preguntas")
async def obtener_sugerencias():
    """
    Endpoint para obtener sugerencias de preguntas comunes.
    
    Returns:
        Lista de sugerencias de preguntas.
    """
    sugerencias = [
        "¿Qué productos tienen stock disponible?",
        "¿Cuál es el precio del arroz?",
        "¿Tienen leche disponible?",
        "¿Cuáles son los productos más baratos?",
        "¿Qué productos están por acabarse?",
        "¿Tienen productos de limpieza?",
        "¿Cuál es el horario de la tienda?",
        "¿Qué productos nuevos llegaron?",
        "¿Tienen productos para mascotas?",
        "¿Cuáles son los productos más vendidos?"
    ]
    
    return {"sugerencias": sugerencias}

@router.post("/preguntar-publico", response_model=QueryResponse, summary="Realizar una consulta al chatbot (público)")
async def hacer_pregunta_publico(
    req: QueryRequest,
    request: Request
):
    """
    Endpoint público para realizar preguntas al chatbot.
    No requiere autenticación.
    
    Args:
        req: Datos de la pregunta.
        request: Información de la solicitud HTTP.
        
    Returns:
        Respuesta del chatbot.
    """
    start_time = time.time()
    success = True
    error_message = None
    
    try:
        # Registrar información sobre la consulta
        logger.info(f"Usuario público pregunta: {req.pregunta}")

        # Procesar la pregunta con el chatbot
        respuesta = retriever(req.pregunta, req.estilo, "usuario_publico", req.session_id)
        logger.debug(f"Respuesta generada: {respuesta}")

        # Guardar el log (sin información de empleado)
        guardar_interaccion(
            pregunta=req.pregunta,
            respuesta=respuesta,
            prompt_tokens=len(req.pregunta.split()),
            completion_tokens=len(respuesta.split())
        )
        
        # Asegurar que la respuesta no esté vacía
        if not respuesta or len(respuesta.strip()) == 0:
            respuesta = "No pude encontrar información sobre eso. ¿Puedo ayudarte con algo más?"
            
        return {"respuesta": respuesta}
    except Exception as e:
        success = False
        error_message = str(e)
        logger.error(f"Error al procesar pregunta pública: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {"respuesta": "Ocurrió un error inesperado. Por favor intenta nuevamente."}
    finally:
        # Registrar métrica de rendimiento
        response_time = time.time() - start_time
        performance_monitor.add_metric(
            response_time=response_time,
            operation_type="chatbot_query_public",
            success=success,
            error_message=error_message
        )

@router.get("/historial", summary="Obtener historial de conversación")
async def obtener_historial(
    request: Request,
    token_data: dict = Depends(verify_employee_token)
):
    """
    Endpoint para obtener el historial de conversación del usuario actual.
    
    Args:
        request: Información de la solicitud HTTP.
        token_data: Datos del token de autenticación.
        
    Returns:
        Historial de conversación.
    """
    # Obtener identificador del empleado
    employee_id = token_data.get("sub")
    
    # Devolver historial si existe
    if employee_id in conversation_history and conversation_history[employee_id]:
        return {"historial": conversation_history[employee_id]}
    else:
        return {"historial": []}

@router.get("/estadisticas", response_model=ChatStatistics, summary="Obtener estadísticas de uso")
async def obtener_estadisticas(token_data: dict = Depends(verify_employee_token)):
    """
    Endpoint protegido para obtener estadísticas de uso del chatbot.
    Solo empleados autorizados pueden acceder.
    
    Args:
        token_data: Datos del token de autenticación.
        
    Returns:
        Estadísticas de uso.
    """
    # Verificar que el usuario tenga permisos administrativos
    if token_data.get("rol") not in ["administrador", "dueño"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado. Solo administradores y dueños pueden ver estadísticas."
        )
    
    # Contar total de consultas realizadas (suma de todas las conversaciones)
    total_consultas = sum(len(conv) for conv in conversation_history.values())
    
    # Contar empleados activos (empleados con al menos una consulta)
    empleados_activos = len(conversation_history)
    
    # Extraer productos más consultados (análisis simple)
    productos_consultados = []
    for empleado in conversation_history.values():
        for interaccion in empleado:
            pregunta = interaccion["pregunta"].lower()
            # Productos comunes a buscar
            common_products = ["monitor", "teclado", "mouse", "cuaderno", "esfero", "memoria"]
            for producto in common_products:
                if producto in pregunta:
                    productos_consultados.append(producto)
    
    # Contar frecuencia de productos
    from collections import Counter
    productos_counter = Counter(productos_consultados)
    productos_populares = [item[0] for item in productos_counter.most_common(3)] if productos_counter else []
    
    # Calcular tasa de respuesta exitosa (aproximación)
    tasa_respuesta_exitosa = 95.0  # Valor de ejemplo, en un sistema real se calcularía
    
    return {
        "total_consultas": total_consultas,
        "empleados_activos": empleados_activos,
        "productos_populares": productos_populares,
        "tasa_respuesta_exitosa": tasa_respuesta_exitosa
    }
