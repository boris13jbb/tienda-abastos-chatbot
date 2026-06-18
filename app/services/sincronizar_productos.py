# app/services/sincronizar_productos.py 

import logging
from sqlalchemy import text
from app.database.db import get_db
from app.rag.indexer import document_indexer
from app.models import Productos
from app.utils.logger import get_logger
from datetime import datetime
import sqlite3
import os

logger = get_logger(__name__)


def limpiar_registros_huérfanos_sqlite():
    """Limpia automáticamente registros huérfanos en SQLite que no están en el índice pickle"""
    try:
        sqlite_path = "data/indices/document_db.sqlite"
        if not os.path.exists(sqlite_path):
            return False
        
        # Obtener IDs del índice pickle
        ids_pickle = set(document_indexer.list_document_ids())
        
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        # Obtener IDs de SQLite
        cursor.execute("SELECT id FROM documents")
        ids_sqlite = {row[0] for row in cursor.fetchall()}
        
        # Encontrar registros huérfanos (en SQLite pero no en pickle)
        registros_huérfanos = ids_sqlite - ids_pickle
        
        if registros_huérfanos:
            logger.warning(f"Encontrados {len(registros_huérfanos)} registros huérfanos en SQLite")
            
            # Eliminar registros huérfanos
            for doc_id in registros_huérfanos:
                cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                logger.debug(f"Registro huérfano eliminado: {doc_id}")
            
            conn.commit()
            logger.info(f"Se eliminaron {len(registros_huérfanos)} registros huérfanos de SQLite")
            conn.close()
            return True
        
        conn.close()
        return False
        
    except Exception as e:
        logger.error(f"Error limpiando registros huérfanos: {str(e)}")
        return False


def verificar_y_corregir_sqlite():
    """Verifica y corrige automáticamente la base de datos SQLite"""
    try:
        sqlite_path = "data/indices/document_db.sqlite"
        if not os.path.exists(sqlite_path):
            logger.warning("Base de datos SQLite no encontrada")
            return False
        
        conn = sqlite3.connect(sqlite_path)
        cursor = conn.cursor()
        
        # Verificar si las columnas existen
        cursor.execute("PRAGMA table_info(documents)")
        columns = [column[1] for column in cursor.fetchall()]
        
        # Verificar si faltan columnas
        columnas_faltantes = []
        if 'created_at' not in columns:
            columnas_faltantes.append('created_at')
        if 'updated_at' not in columns:
            columnas_faltantes.append('updated_at')
        
        if columnas_faltantes:
            logger.warning(f"Columnas faltantes en SQLite: {columnas_faltantes}")
            
            # Agregar columnas faltantes
            for columna in columnas_faltantes:
                cursor.execute(f"ALTER TABLE documents ADD COLUMN {columna} TIMESTAMP")
                logger.info(f"Columna {columna} agregada a la tabla documents")
            
            # Actualizar registros existentes con timestamps
            now = datetime.now().isoformat()
            cursor.execute("UPDATE documents SET created_at = ?, updated_at = ? WHERE created_at IS NULL", (now, now))
            
            conn.commit()
            logger.info("Base de datos SQLite corregida automáticamente")
            conn.close()
            return True
        
        conn.close()
        return False
        
    except Exception as e:
        logger.error(f"Error verificando/corrigiendo SQLite: {str(e)}")
        return False


def sincronizar_productos_con_indexador():
    logger.info("[SYNC] Iniciando sincronización inteligente de productos...")
    
    # Verificar y corregir SQLite automáticamente
    if verificar_y_corregir_sqlite():
        logger.info("Base de datos SQLite verificada y corregida automáticamente")
    
    # Limpiar registros huérfanos automáticamente
    if limpiar_registros_huérfanos_sqlite():
        logger.info("Registros huérfanos eliminados automáticamente")
    
    try:
        db = next(get_db())  

        # Cargar productos de la base de datos
        productos = db.execute(text("""
            SELECT ID, Nombre, Descripcion, Precio, Stock
            FROM Productos
            WHERE Stock > 0
        """)).mappings().all()

        if not productos:
            logger.warning("No se encontraron productos disponibles para indexar.")
            return

        logger.info(f"Productos en base de datos: {len(productos)}")

        # Obtener productos ya indexados
        productos_indexados = document_indexer.list_document_ids()
        logger.info(f"Productos en índice actual: {len(productos_indexados)}")

        # Crear conjuntos para comparación eficiente
        ids_bd = {f"Productos_{prod['ID']}" for prod in productos}
        ids_indexados = set(productos_indexados)

        # Identificar productos a agregar (nuevos en BD)
        productos_a_agregar = ids_bd - ids_indexados
        
        # Identificar productos a eliminar (eliminados de BD)
        productos_a_eliminar = ids_indexados - ids_bd
        
        # Identificar productos a actualizar (cambios en BD)
        productos_a_actualizar = ids_bd & ids_indexados

        cambios_realizados = False

        # 1. Eliminar productos que ya no existen en BD
        if productos_a_eliminar:
            logger.info(f"Eliminando {len(productos_a_eliminar)} productos del índice...")
            for prod_id in productos_a_eliminar:
                try:
                    document_indexer.remove_document(prod_id)
                    logger.debug(f"Producto eliminado del índice: {prod_id}")
                except Exception as e:
                    logger.error(f"Error eliminando producto {prod_id}: {str(e)}")
            cambios_realizados = True

        # 2. Agregar productos nuevos
        nuevos_documentos = []
        for prod in productos:
            prod_id = f"Productos_{prod['ID']}"
            if prod_id in productos_a_agregar:
                nuevos_documentos.append({
                    "doc_id": prod_id,
                    "title": prod["Nombre"],
                    "content": prod["Descripcion"] or "",
                    "metadata": {
                        "precio": float(prod["Precio"]) if prod["Precio"] else 0.0,
                        "stock": int(prod["Stock"]),
                        "tabla": "Productos"
                    }
                })

        if nuevos_documentos:
            document_indexer.batch_add_documents(nuevos_documentos)
            logger.info(f"Se indexaron {len(nuevos_documentos)} productos nuevos.")
            cambios_realizados = True

        # 3. Actualizar productos existentes (verificar cambios)
        if productos_a_actualizar:
            productos_actualizados = []
            for prod in productos:
                prod_id = f"Productos_{prod['ID']}"
                if prod_id in productos_a_actualizar:
                    # Verificar si hay cambios en el producto
                    try:
                        # Obtener documento actual del índice
                        doc_actual = document_indexer.get_document(prod_id)
                        if doc_actual:
                            # Comparar con datos actuales de BD
                            if (doc_actual.get('title') != prod["Nombre"] or
                                doc_actual.get('content') != (prod["Descripcion"] or "") or
                                doc_actual.get('metadata', {}).get('precio') != float(prod["Precio"] or 0) or
                                doc_actual.get('metadata', {}).get('stock') != int(prod["Stock"])):
                                
                                productos_actualizados.append({
                                    "doc_id": prod_id,
                                    "title": prod["Nombre"],
                                    "content": prod["Descripcion"] or "",
                                    "metadata": {
                                        "precio": float(prod["Precio"]) if prod["Precio"] else 0.0,
                                        "stock": int(prod["Stock"]),
                                        "tabla": "Productos"
                                    }
                                })
                    except Exception as e:
                        logger.error(f"Error verificando cambios en producto {prod_id}: {str(e)}")

            if productos_actualizados:
                document_indexer.batch_add_documents(productos_actualizados)
                logger.info(f"Se actualizaron {len(productos_actualizados)} productos.")
                cambios_realizados = True

        if not cambios_realizados:
            logger.info("No hay cambios que sincronizar.")
        else:
            logger.info("Sincronización completada exitosamente.")

    except Exception as e:
        logger.error(f"Error durante la sincronización: {str(e)}")
        raise e


def sincronizacion_completa():
    """Realiza una sincronización completa recreando el índice"""
    logger.info("[SYNC] Iniciando sincronización completa...")
    
    try:
        db = next(get_db())

        # Cargar todos los productos de la BD
        productos = db.execute(text("""
            SELECT ID, Nombre, Descripcion, Precio, Stock
            FROM Productos
            WHERE Stock > 0
        """)).mappings().all()

        logger.info(f"Productos en base de datos: {len(productos)}")

        # Crear respaldo del índice actual
        try:
            import os
            import shutil
            from datetime import datetime
            
            index_path = "data/indices"
            backup_dir = f"{index_path}/backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{backup_dir}/Productos_index_backup_{timestamp}.pkl"
            
            index_file = f"{index_path}/Productos_index.pkl"
            if os.path.exists(index_file):
                shutil.copy2(index_file, backup_file)
                logger.info(f"Respaldo creado: {backup_file}")
        except Exception as e:
            logger.warning(f"No se pudo crear respaldo: {str(e)}")

        # Limpiar índice actual
        document_indexer.vectors = []
        document_indexer.document_ids = []

        # Recrear índice con productos actuales
        nuevos_documentos = []
        for prod in productos:
            prod_id = f"Productos_{prod['ID']}"
            nuevos_documentos.append({
                "doc_id": prod_id,
                "title": prod["Nombre"],
                "content": prod["Descripcion"] or "",
                "metadata": {
                    "precio": float(prod["Precio"]) if prod["Precio"] else 0.0,
                    "stock": int(prod["Stock"]),
                    "tabla": "Productos"
                }
            })

        if nuevos_documentos:
            document_indexer.batch_add_documents(nuevos_documentos)
            logger.info(f"Sincronización completa exitosa: {len(nuevos_documentos)} productos indexados.")
        else:
            logger.warning("No hay productos para indexar.")

    except Exception as e:
        logger.error(f"Error durante la sincronización completa: {str(e)}")


def get_sync_status():
    """Obtiene el estado actual de la sincronización"""
    try:
        db = next(get_db())
        
        # Contar productos en la base de datos
        productos_db = db.execute(text("""
            SELECT COUNT(*) as total
            FROM Productos
            WHERE Stock > 0
        """)).scalar()
        
        # Contar productos indexados - usar el indexador actualizado
        try:
            from app.rag.indexer import DocumentIndexer
            indexador_actual = DocumentIndexer()
            productos_indexados = len(indexador_actual.list_document_ids())
        except Exception as e:
            logger.error(f"Error obteniendo productos indexados: {str(e)}")
            productos_indexados = 0
        
        # Verificar sincronización detallada
        try:
            # Obtener IDs de productos en BD
            productos_bd_ids = db.execute(text("""
                SELECT ID
                FROM Productos
                WHERE Stock > 0
            """)).fetchall()
            
            ids_bd = {f"Productos_{row[0]}" for row in productos_bd_ids}
            ids_indexados = set(indexador_actual.list_document_ids())
            
            productos_faltantes = ids_bd - ids_indexados
            productos_extra = ids_indexados - ids_bd
            
            sincronizacion_detallada = {
                "productos_faltantes": len(productos_faltantes),
                "productos_extra": len(productos_extra),
                "productos_actualizados": len(ids_bd & ids_indexados)
            }
        except Exception as e:
            logger.error(f"Error en verificación detallada: {str(e)}")
            sincronizacion_detallada = {
                "productos_faltantes": 0,
                "productos_extra": 0,
                "productos_actualizados": 0
            }
        
        return {
            "productos_db": productos_db,
            "productos_indexados": productos_indexados,
            "sincronizados": productos_db == productos_indexados and sincronizacion_detallada["productos_faltantes"] == 0 and sincronizacion_detallada["productos_extra"] == 0,
            "ultima_sincronizacion": "Hace 5 minutos",  # Valor simulado
            "detalles": sincronizacion_detallada
        }
    except Exception as e:
        logger.error(f"Error obteniendo estado de sincronización: {str(e)}")
        return {
            "error": str(e),
            "productos_db": 0,
            "productos_indexados": 0,
            "sincronizados": False,
            "detalles": {
                "productos_faltantes": 0,
                "productos_extra": 0,
                "productos_actualizados": 0
            }
        }


def detectar_cambios_base_datos():
    """Detecta cambios en la base de datos y actualiza el índice automáticamente"""
    logger.info("[SYNC] Detectando cambios en la base de datos...")
    
    try:
        estado_actual = get_sync_status()
        
        if not estado_actual["sincronizados"]:
            logger.warning("Desincronización detectada. Iniciando sincronización completa...")
            sincronizacion_completa()
            return True
        else:
            logger.info("Base de datos sincronizada. No se requieren cambios.")
            return False
            
    except Exception as e:
        logger.error(f"Error detectando cambios: {str(e)}")
        return False
