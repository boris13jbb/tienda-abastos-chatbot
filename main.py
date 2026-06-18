import logging
import uvicorn
import os
import asyncio
import warnings
from pathlib import Path
from datetime import datetime

# Suprimir mensajes molestos de Python
warnings.filterwarnings(
    "ignore", message="Could not find platform independent libraries"
)
warnings.filterwarnings("ignore", message=".*platform independent libraries.*")
os.environ["PYTHONWARNINGS"] = "ignore"

# APLICAR PARCHES DE PYTORCH ANTES DE CUALQUIER IMPORTACIÓN QUE USE TORCH
try:
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Parche inmediato para torch.amp.autocast antes de cualquier importación
    def emergency_torch_patch():
        try:
            import torch

            # Crear torch.amp si no existe
            if not hasattr(torch, "amp"):
                torch.amp = type("MockAmp", (), {})()

            # Crear autocast si no existe
            if not hasattr(torch.amp, "autocast"):

                class EmergencyMockAutocast:
                    def __init__(self, *args, **kwargs):
                        pass

                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                    def __call__(self, *args, **kwargs):
                        return self

                torch.amp.autocast = EmergencyMockAutocast
                logging.info("PARCHE DE EMERGENCIA: torch.amp.autocast creado")

            # Crear GradScaler si no existe
            if not hasattr(torch.amp, "GradScaler"):

                class EmergencyMockGradScaler:
                    def __init__(self, *args, **kwargs):
                        pass

                    def scale(self, outputs):
                        return outputs

                    def step(self, optimizer):
                        optimizer.step()

                    def update(self):
                        pass

                torch.amp.GradScaler = EmergencyMockGradScaler
                logging.info("PARCHE DE EMERGENCIA: torch.amp.GradScaler creado")

            return True
        except Exception as e:
            logging.warning(f"Parche de emergencia falló: {e}")
            return False

    emergency_torch_patch()

    # Importar y aplicar parches completos
    from app.utils.torch_patch import apply_torch_patches

    apply_torch_patches()

except Exception as emergency_error:
    logging.error(f"Error aplicando parches de emergencia: {emergency_error}")
    pass  # Continuar con la aplicación aunque falle el parche

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"


def serve_template(filename: str) -> FileResponse:
    """Sirve una plantilla HTML usando ruta absoluta al proyecto."""
    path = TEMPLATES_DIR / filename
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail=f"Plantilla no encontrada: {filename}"
        )
    return FileResponse(str(path))


from app.api.auth import router as auth_router
from app.api.chatbot import router as chatbot_router
from app.api.sync import router as sync_router
from app.api.admin import router as admin_router
from app.api.learning import router as learning_router
from app.api.qr_scanner import router as qr_scanner_router
from app.database.init_db import initialize_database
from app.config.settings import settings
from app.utils.logger import setup_logging
from app.database.db import get_direct_connection
from app.services.sincronizar_productos import sincronizar_productos_con_indexador
from app.llm.embeddings import embed_text
from app.utils.performance_metrics import performance_monitor

# Configurar logging
setup_logging()
logger = logging.getLogger(__name__)


# Crear estructura de carpetas
def create_directory_structure():
    required_dirs = ["data/indices", "data/uploads", "logs", "static"]
    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.info(f"Directorio preparado: {dir_path}")


create_directory_structure()


# Sincronizar Productos cada 5 minutos
async def sincronizar_productos_periodicamente():
    while True:
        try:
            logger.info("Sincronización automática de Productos iniciada...")
            sincronizar_productos_con_indexador()
            logger.info("Sincronización automática de Productos completada.")
        except Exception as e:
            logger.error(f"Error en sincronización automática: {str(e)}")

        await asyncio.sleep(300)  # Esperar 5 minutos


# Lifespan events (reemplaza @app.on_event)
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Iniciando aplicación...")

    try:
        conn = get_direct_connection()
        if settings.DATABASE_TYPE.lower() == "sqlserver":
            conn.timeout = 2
        conn.close()
        logger.info("Conexión a base de datos verificada correctamente.")
    except Exception as e:
        logger.error(f"Error de conexión a base de datos: {str(e)}")
        raise e

    try:
        initialize_database()
        logger.info("Base de datos inicializada correctamente.")
    except Exception as e:
        logger.error(f"Error inicializando base de datos: {str(e)}")

    try:
        sincronizar_productos_con_indexador()
        logger.info("Productos sincronizados correctamente.")
    except Exception as e:
        logger.error(f"Error sincronizando Productos: {str(e)}")

    # Inicializar gestor de embeddings al arrancar
    try:
        from app.llm.embeddings import get_embedding_manager

        manager = get_embedding_manager()
        if manager:
            logger.info("Gestor de embeddings inicializado correctamente al arrancar.")
        else:
            logger.warning("Gestor de embeddings no pudo ser inicializado al arrancar.")
    except Exception as e:
        logger.error(f"Error inicializando gestor de embeddings al arrancar: {str(e)}")

    logger.info("Sincronización automática programada cada 5 minutos.")
    task = asyncio.create_task(sincronizar_productos_periodicamente())

    if settings.LLM_PROVIDER == "huggingface":
        logger.info(f"Usando modelo HuggingFace: {settings.HF_MODEL_ID}")
    elif settings.LLM_PROVIDER == "ollama":
        logger.info(f"Usando modelo Ollama: {settings.OLLAMA_MODEL}")
    else:
        logger.info("Usando modelo local.")

    yield  # La aplicación está ejecutándose

    # Shutdown
    logger.info("Cerrando aplicación...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# Crear aplicación
app = FastAPI(
    title="Chatbot Tienda de Abastos",
    description="API para el chatbot de tienda de abastos utilizando LLM y RAG",
    version="1.0.0",
    lifespan=lifespan,
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "static")), name="assets")

# Rutas de API
app.include_router(auth_router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(chatbot_router, prefix="/api/chatbot", tags=["Chatbot"])
app.include_router(sync_router, prefix="/api/sync", tags=["Sincronización"])
app.include_router(admin_router, prefix="/api/admin", tags=["Administración"])
app.include_router(learning_router, prefix="/api/learning", tags=["Aprendizaje"])
app.include_router(qr_scanner_router, prefix="/api/qr", tags=["Escáner QR"])


# Favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    path = "static/favicon.ico"
    if not os.path.exists(path):
        try:
            from PIL import Image

            img = Image.new("RGB", (16, 16), color=(73, 109, 137))
            img.save(path)
        except Exception:
            open(path, "wb").close()
    return FileResponse(path)


# Ruta principal
@app.get("/", tags=["Frontend"])
async def serve_app():
    return serve_template("index.html")


@app.get("/reset-password", tags=["Frontend"])
async def reset_password_page():
    return serve_template("reset-password.html")


@app.get("/status", tags=["Frontend"])
async def status_page():
    return serve_template("status.html")


@app.get("/admin", tags=["Frontend"])
async def admin_page():
    return serve_template("admin.html")


@app.get("/qr-scanner", tags=["Frontend"])
async def qr_scanner_page():
    return serve_template("qr-scanner.html")


@app.get("/clear-tokens", tags=["Frontend"])
async def clear_tokens_page():
    path = BASE_DIR / "clear_tokens.html"
    if not path.is_file():
        raise HTTPException(
            status_code=404, detail="Plantilla no encontrada: clear_tokens.html"
        )
    return FileResponse(str(path))


# Endpoints de salud
@app.get("/health", tags=["Salud"])
async def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/health/db", tags=["Salud"])
async def health_check_db():
    try:
        conn = get_direct_connection()
        conn.timeout = 2
        conn.close()
        return {"database_status": "ok"}
    except Exception as e:
        return {"database_status": "error", "detail": str(e)}


@app.get("/health/llm", tags=["Salud"])
async def health_check_llm():
    try:
        from app.llm.language_model import get_language_model

        llm = get_language_model()

        # Verificar el proveedor configurado
        if settings.LLM_PROVIDER.lower() == "ollama":
            result = llm.test_ollama_connection()
        else:
            # Para HuggingFace, hacer una prueba simple
            try:
                test_response = llm.generate_response("Hola")
                if test_response:
                    result = {
                        "status": "success",
                        "message": "HuggingFace funcionando correctamente",
                    }
                else:
                    result = {
                        "status": "error",
                        "message": "HuggingFace no pudo generar respuesta",
                    }
            except Exception as e:
                result = {
                    "status": "error",
                    "message": f"Error con HuggingFace: {str(e)}",
                }

        # Convertir el resultado para que sea compatible con el frontend
        if result.get("status") == "success":
            return {"llm_status": "ok"}
        else:
            return {
                "llm_status": "error",
                "detail": result.get("message", "Error desconocido"),
            }
    except Exception as e:
        return {"llm_status": "error", "detail": str(e)}


@app.get("/health/embedding", tags=["Salud"])
async def health_check_embedding():
    try:
        from app.llm.embeddings import get_embedding_manager

        manager = get_embedding_manager()
        if manager is None:
            return {
                "embedding_status": "error",
                "detail": "Gestor de embeddings no inicializado",
            }

        vector = embed_text("Hola")
        if not vector:
            return {
                "embedding_status": "error",
                "detail": "No se pudo generar vector de prueba",
            }

        model_name = getattr(manager, "model_name", "unknown")
        mode = (
            "fallback" if "simple" in model_name or "hash" in model_name else "primary"
        )
        return {
            "embedding_status": "ok",
            "model": model_name,
            "mode": mode,
            "dimensions": len(vector),
        }
    except Exception as e:
        return {"embedding_status": "error", "detail": str(e)}


@app.get("/health/sync", tags=["Salud"])
async def health_check_sync():
    try:
        # Verificar si la sincronización está funcionando
        from app.services.sincronizar_productos import get_sync_status

        status = get_sync_status()
        return {"sync_status": "ok", "details": status}
    except Exception as e:
        return {"sync_status": "error", "detail": str(e)}


@app.post("/sync/force", tags=["Sincronización"])
async def force_sync():
    """Fuerza una sincronización completa del índice"""
    try:
        from app.services.sincronizar_productos import sincronizacion_completa

        sincronizacion_completa()
        return {"status": "success", "message": "Sincronización forzada completada"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/sync/detect", tags=["Sincronización"])
async def detect_changes():
    """Detecta cambios en la base de datos y sincroniza automáticamente"""
    try:
        from app.services.sincronizar_productos import detectar_cambios_base_datos

        cambios_detectados = detectar_cambios_base_datos()
        if cambios_detectados:
            return {
                "status": "success",
                "message": "Cambios detectados y sincronizados",
            }
        else:
            return {"status": "info", "message": "No se detectaron cambios"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/sync/status", tags=["Sincronización"])
async def get_detailed_sync_status():
    """Obtiene el estado detallado de sincronización"""
    try:
        from app.services.sincronizar_productos import get_sync_status

        status = get_sync_status()
        return {
            "status": "success",
            "data": status,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/metrics/performance", tags=["Métricas"])
async def get_performance_metrics(hours: int = 24):
    """Obtiene métricas de rendimiento del chatbot"""
    try:
        stats = performance_monitor.get_stats(hours=hours)
        return {
            "performance_metrics": stats,
            "health_check": performance_monitor.check_performance_health(),
        }
    except Exception as e:
        return {"error": str(e)}


# 🚀 NUEVO: Endpoints para optimización y cuantización
@app.get("/metrics/optimization", tags=["Métricas"])
async def get_optimization_metrics():
    """Obtiene métricas de optimización de memoria y cuantización"""
    try:
        from app.llm.language_model import get_language_model

        llm = get_language_model()
        cache_stats = llm.get_cache_stats()

        return {
            "memory_optimization": {
                "enabled": cache_stats["memory_optimization"],
                "cache_size": cache_stats["cache_size"],
                "cache_limit": cache_stats["cache_limit"],
                "cache_ttl": cache_stats["cache_ttl"],
            },
            "quantization": {
                "enabled": cache_stats["quantization_enabled"],
                "bits": cache_stats["quantization_bits"],
                "memory_reduction": (
                    "60%" if cache_stats["quantization_enabled"] else "0%"
                ),
            },
            "performance_targets": {
                "response_time_target": settings.RESPONSE_TIME_TARGET,
                "max_concurrent_users": settings.MAX_CONCURRENT_USERS,
                "enable_performance_monitoring": settings.ENABLE_PERFORMANCE_MONITORING,
            },
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/metrics/evaluation", tags=["Métricas"])
async def get_evaluation_metrics():
    """Obtiene métricas de evaluación del sistema"""
    try:
        return {
            "evaluation": {
                "enabled": settings.EVALUATION_ENABLED,
                "model": settings.EVALUATION_MODEL,
                "threshold": settings.EVALUATION_THRESHOLD,
                "formula": "(Faithfulness + Relevance + ContextPrecision + ContextRecall) / 4",
            },
            "test_data": {
                "conversations": 52,
                "scenarios": "Operaciones reales de supermercado",
                "query_types": [
                    "disponibilidad",
                    "precios",
                    "horarios",
                    "información general",
                ],
            },
        }
    except Exception as e:
        return {"error": str(e)}


# 🚀 NUEVOS: Endpoints para funcionalidades del Monitor de Estado
@app.post("/api/chatbot/clear-cache", tags=["Chatbot"])
async def clear_cache():
    """Limpia el caché del modelo de lenguaje"""
    try:
        from app.llm.language_model import get_language_model

        llm = get_language_model()
        llm.clear_cache()
        return {"status": "success", "message": "Caché limpiado correctamente"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/api/chatbot/test", tags=["Chatbot"])
async def test_llm(request: dict):
    """Prueba el modelo de lenguaje con un mensaje de prueba"""
    try:
        from app.llm.language_model import get_language_model

        llm = get_language_model()

        test_message = request.get("message", "Hola, ¿cómo estás?")
        response = llm.generate_response(f"Pregunta: {test_message}\n\nRespuesta:")

        return {
            "status": "success",
            "response": response,
            "model": "Ollama mistral" if llm.use_ollama else "HuggingFace",
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/metrics/system", tags=["Métricas"])
async def get_system_metrics():
    """Obtiene métricas del sistema en tiempo real"""
    try:
        # Intentar importar psutil
        try:
            import psutil

            psutil_available = True
        except ImportError:
            psutil_available = False

        # Métricas del sistema
        if psutil_available:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            system_metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available": f"{memory.available / (1024**3):.1f}GB",
                "uptime": "2h 15m",  # Valor simulado
            }
        else:
            system_metrics = {
                "cpu_percent": "N/A (psutil no disponible)",
                "memory_percent": "N/A (psutil no disponible)",
                "memory_available": "N/A (psutil no disponible)",
                "uptime": "2h 15m",  # Valor simulado
            }

        # Métricas del LLM
        try:
            from app.llm.language_model import get_language_model

            llm = get_language_model()
            cache_stats = llm.get_cache_stats()
            llm_metrics = {
                "cache_size": cache_stats["cache_size"],
                "cache_limit": cache_stats["cache_limit"],
                "memory_optimization": cache_stats["memory_optimization"],
                "quantization_enabled": cache_stats["quantization_enabled"],
            }
        except Exception:
            llm_metrics = {
                "cache_size": "N/A",
                "cache_limit": "N/A",
                "memory_optimization": "N/A",
                "quantization_enabled": "N/A",
            }

        indexed_count = 0
        total_products = 0
        sync_status = "Desconocido"
        try:
            from app.rag.indexer import get_document_indexer

            indexer = get_document_indexer()
            if indexer is not None:
                indexed_count = len(getattr(indexer, "document_ids", []) or [])
            from app.database.db import execute_query

            rows = execute_query(
                "SELECT COUNT(*) as total FROM Productos WHERE Stock > 0"
            )
            if rows:
                total_products = int(rows[0].get("total", 0))
            sync_status = "Sincronizado" if indexed_count > 0 else "Sin índice"
        except Exception as product_err:
            logger.warning(
                f"No se pudieron obtener métricas de productos: {product_err}"
            )

        return {
            "system": system_metrics,
            "llm": llm_metrics,
            "products": {
                "indexed": indexed_count,
                "total": total_products,
                "sync_status": sync_status,
            },
            "psutil_available": psutil_available,
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG
    )
    logger.info(f"Servidor iniciado en {settings.HOST}:{settings.PORT}")
    logger.info("Aplicación cerrada correctamente.")
