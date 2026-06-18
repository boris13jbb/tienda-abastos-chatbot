"""
API para el control manual de sincronización de productos.
Proporciona endpoints para gestión y monitoreo del servicio de sincronización.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.security.auth import verify_token, require_admin_auth
from app.services.sincronizar_productos import sincronizar_productos_con_indexador
from app.utils.logger import get_logger

# Configurar logging específico para este módulo
logger = get_logger(__name__)

# Crear router para las rutas de sincronización
router = APIRouter()

# Estado global de sincronización
sync_status = {
    "running": False,
    "last_sync": None,
    "last_error": None,
    "total_syncs": 0,
    "auto_sync_enabled": True
}

# Modelos de respuesta
class SyncStatusResponse(BaseModel):
    running: bool
    last_sync: str | None
    last_error: str | None
    total_syncs: int
    auto_sync_enabled: bool

class SyncResponse(BaseModel):
    message: str
    status: str
    timestamp: str

@router.get("/status", response_model=SyncStatusResponse, summary="Obtener estado de sincronización")
async def get_sync_status(token_data: dict = Depends(require_admin_auth)):
    """
    Obtiene el estado actual del servicio de sincronización.
    Solo administradores y dueños pueden acceder.
    
    Args:
        token_data: Datos del token de autenticación.
        
    Returns:
        Estado actual de la sincronización.
    """
    try:
        logger.info(f"Administrador {token_data.get('name', 'unknown')} consultó estado de sincronización")
        
        return SyncStatusResponse(
            running=sync_status["running"],
            last_sync=sync_status["last_sync"],
            last_error=sync_status["last_error"],
            total_syncs=sync_status["total_syncs"],
            auto_sync_enabled=sync_status["auto_sync_enabled"]
        )
    except Exception as e:
        logger.error(f"Error al obtener estado de sincronización: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener estado: {str(e)}"
        )

@router.post("/start", response_model=SyncResponse, summary="Iniciar sincronización automática")
async def start_auto_sync(token_data: dict = Depends(require_admin_auth)):
    """
    Inicia el servicio de sincronización automática.
    Solo administradores y dueños pueden acceder.
    
    Args:
        token_data: Datos del token de autenticación.
        
    Returns:
        Confirmación de inicio del servicio.
    """
    try:
        user_id = token_data.get("sub", "unknown")
        user_name = token_data.get("name", "Administrador")
        logger.info(f"Administrador {user_name} inició sincronización automática")
        
        if sync_status["auto_sync_enabled"]:
            return SyncResponse(
                message="La sincronización automática ya está activa",
                status="warning",
                timestamp=datetime.now().isoformat()
            )
        
        sync_status["auto_sync_enabled"] = True
        
        return SyncResponse(
            message="Sincronización automática iniciada correctamente",
            status="success",
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error al iniciar sincronización automática: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al iniciar sincronización: {str(e)}"
        )

@router.post("/stop", response_model=SyncResponse, summary="Detener sincronización automática")
async def stop_auto_sync(token_data: dict = Depends(require_admin_auth)):
    """
    Detiene el servicio de sincronización automática.
    Solo administradores y dueños pueden acceder.
    
    Args:
        token_data: Datos del token de autenticación.
        
    Returns:
        Confirmación de detención del servicio.
    """
    try:
        user_id = token_data.get("sub", "unknown")
        user_name = token_data.get("name", "Administrador")
        logger.info(f"Administrador {user_name} detuvo sincronización automática")
        
        if not sync_status["auto_sync_enabled"]:
            return SyncResponse(
                message="La sincronización automática ya está detenida",
                status="warning",
                timestamp=datetime.now().isoformat()
            )
        
        sync_status["auto_sync_enabled"] = False
        
        return SyncResponse(
            message="Sincronización automática detenida correctamente",
            status="success",
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        logger.error(f"Error al detener sincronización automática: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al detener sincronización: {str(e)}"
        )

@router.post("/sync-now", response_model=SyncResponse, summary="Ejecutar sincronización inmediata")
async def sync_now(token_data: dict = Depends(require_admin_auth)):
    """
    Ejecuta una sincronización inmediata de productos.
    Solo administradores y dueños pueden acceder.
    
    Args:
        token_data: Datos del token de autenticación.
        
    Returns:
        Resultado de la sincronización.
    """
    try:
        user_id = token_data.get("sub", "unknown")
        user_name = token_data.get("name", "Administrador")
        logger.info(f"Administrador {user_name} ejecutó sincronización manual")
        
        if sync_status["running"]:
            return SyncResponse(
                message="Ya hay una sincronización en progreso. Espere a que termine.",
                status="warning",
                timestamp=datetime.now().isoformat()
            )
        
        sync_status["running"] = True
        sync_status["last_error"] = None
        
        try:
            # Ejecutar sincronización
            await asyncio.get_event_loop().run_in_executor(
                None, sincronizar_productos_con_indexador
            )
            
            sync_status["last_sync"] = datetime.now().isoformat()
            sync_status["total_syncs"] += 1
            
            logger.info(f"Sincronización manual completada por administrador {user_name}")
            
            return SyncResponse(
                message="Sincronización ejecutada correctamente",
                status="success",
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as sync_error:
            sync_status["last_error"] = str(sync_error)
            logger.error(f"Error en sincronización manual: {str(sync_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en sincronización: {str(sync_error)}"
            )
        finally:
            sync_status["running"] = False
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error al ejecutar sincronización: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ejecutar sincronización: {str(e)}"
        )

@router.get("/logs", summary="Obtener logs de sincronización")
async def get_sync_logs(
    lines: int = 50,
    token_data: dict = Depends(require_admin_auth)
):
    """
    Obtiene las últimas líneas de logs de sincronización.
    Solo administradores y dueños pueden acceder.
    
    Args:
        lines: Número de líneas a obtener (máximo 200).
        token_data: Datos del token de autenticación.
        
    Returns:
        Logs de sincronización.
    """
    try:
        user_name = token_data.get("name", "Administrador")
        logger.info(f"Administrador {user_name} solicitó logs de sincronización")
        
        # Limitar el número de líneas
        lines = min(lines, 200)
        
        try:
            import os
            log_file = "logs/chatbot.log"
            
            if not os.path.exists(log_file):
                return {"logs": [], "message": "Archivo de logs no encontrado"}
            
            # Leer las últimas líneas del archivo
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                last_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                
                # Filtrar líneas relacionadas con sincronización
                sync_lines = [
                    line.strip() for line in last_lines 
                    if any(keyword in line.lower() for keyword in 
                          ['sync', 'sincronización', 'sincronizar', 'productos'])
                ]
                
                return {
                    "logs": sync_lines,
                    "total_lines": len(sync_lines),
                    "message": f"Últimas {len(sync_lines)} líneas de sincronización"
                }
                
        except Exception as file_error:
            logger.error(f"Error al leer archivo de logs: {str(file_error)}")
            return {
                "logs": [],
                "message": f"Error al leer logs: {str(file_error)}"
            }
    except Exception as e:
        logger.error(f"Error al obtener logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al obtener logs: {str(e)}"
        ) 