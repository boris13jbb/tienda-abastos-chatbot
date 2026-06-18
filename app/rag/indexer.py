# indexer.py (corregido y optimizado)

import os
import pickle
import json
import logging
import sqlite3
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np
from datetime import datetime
import decimal

from app.config.settings import settings
from app.utils.logger import get_logger
from app.llm.embeddings import get_embedding_manager

logger = get_logger(__name__)

def json_serializable(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

class DocumentIndexer:
    def __init__(self, index_path: str = "data/indices", use_faiss: bool = True):
        self.index_path = Path(index_path)
        self.use_faiss = use_faiss
        self.index_name = "Productos_index"
        self.db_path = self.index_path / "document_db.sqlite"

        self.index_path.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.index = self._load_index()
        if self.index is None:
            self.vectors = []
            self.document_ids = []
        else:
            self.vectors = self.index.get("vectors", [])
            self.document_ids = self.index.get("document_ids", [])

        logger.info(f"Indexador inicializado. Documentos en índice: {len(self.document_ids)}")

    def _init_db(self):
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                metadata TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
            ''')
            conn.commit()
            conn.close()
            logger.info(f"Base de datos de documentos inicializada en {self.db_path}")
        except Exception as e:
            logger.error(f"Error al inicializar base de datos: {str(e)}")

    def _load_index(self):
        index_file = self.index_path / f"{self.index_name}.pkl"
        if not index_file.exists():
            return None
        try:
            with open(index_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Error al cargar índice: {str(e)}")
            return None

    def _save_index(self):
        index_file = self.index_path / f"{self.index_name}.pkl"
        try:
            # Crear respaldo automático antes de guardar
            self._create_backup()
            
            index_data = {
                "vectors": self.vectors,
                "document_ids": self.document_ids,
                "last_updated": datetime.now().isoformat()
            }
            with open(index_file, 'wb') as f:
                pickle.dump(index_data, f)
            logger.info(f"Índice guardado de forma segura en {index_file}")
        except Exception as e:
            logger.error(f"Error al guardar índice: {str(e)}")
            
    def _create_backup(self):
        """Crea una copia de seguridad del índice antes de actualizar"""
        try:
            index_file = self.index_path / f"{self.index_name}.pkl"
            if index_file.exists():
                # Crear directorio de respaldos si no existe
                backup_dir = self.index_path / "backups"
                backup_dir.mkdir(exist_ok=True)
                
                # Crear nombre de respaldo con timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"{self.index_name}_backup_{timestamp}.pkl"
                
                # Copiar archivo actual como respaldo
                import shutil
                shutil.copy2(index_file, backup_file)
                
                # Mantener solo los últimos 5 respaldos
                self._cleanup_old_backups(backup_dir)
                
                logger.info(f"Respaldo creado: {backup_file}")
        except Exception as e:
            logger.error(f"Error al crear respaldo: {str(e)}")
            
    def _cleanup_old_backups(self, backup_dir):
        """Limpia respaldos antiguos, manteniendo solo los últimos 5"""
        try:
            backup_files = list(backup_dir.glob(f"{self.index_name}_backup_*.pkl"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Eliminar respaldos antiguos (mantener solo los últimos 5)
            for old_backup in backup_files[5:]:
                old_backup.unlink()
                logger.info(f"Respaldo antiguo eliminado: {old_backup}")
        except Exception as e:
            logger.error(f"Error al limpiar respaldos: {str(e)}")

    def batch_add_documents(self, documents: List[Dict[str, Any]]):
        if not documents:
            return
        try:
            embedding_manager = get_embedding_manager()
            if embedding_manager is None:
                logger.error("No hay gestor de embeddings disponible")
                return
            
            texts = [f"{d['title']}\n\n{d['content']}" for d in documents]
            embeddings = embedding_manager.get_embeddings(texts)

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            now = datetime.now().isoformat()
            for doc, emb in zip(documents, embeddings):
                cursor.execute('''
                    INSERT OR REPLACE INTO documents (id, title, content, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    doc['doc_id'],
                    doc['title'],
                    doc['content'],
                    json.dumps(doc.get('metadata', {}), default=json_serializable),
                    now,
                    now
                ))

                if doc['doc_id'] in self.document_ids:
                    idx = self.document_ids.index(doc['doc_id'])
                    self.vectors[idx] = emb
                else:
                    self.document_ids.append(doc['doc_id'])
                    self.vectors.append(emb)

            conn.commit()
            conn.close()
            self._save_index()

            logger.info(f"Añadidos {len(documents)} documentos al índice de manera eficiente.")
        except Exception as e:
            logger.error(f"Error en batch_add_documents: {str(e)}")

    def update_document(self, doc_id: str, title: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        try:
            embedding_manager = get_embedding_manager()
            if embedding_manager is None:
                logger.error("No hay gestor de embeddings disponible")
                return False

            from app.rag.text_processor import text_processor

            normalized_title = text_processor.normalize_text(title)
            normalized_content = text_processor.normalize_text(content)
            doc_text = f"{normalized_title}\n\n{normalized_content}"
            embedding = embedding_manager.get_embeddings(doc_text)[0]

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                UPDATE documents SET title=?, content=?, metadata=?, updated_at=? WHERE id=?
            ''', (title, content, json.dumps(metadata or {}, default=json_serializable), now, doc_id))
            conn.commit()
            conn.close()

            if doc_id in self.document_ids:
                idx = self.document_ids.index(doc_id)
                self.vectors[idx] = embedding
            else:
                self.document_ids.append(doc_id)
                self.vectors.append(embedding)

            self._save_index()

            logger.debug(f"Documento actualizado en el índice: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"Error al actualizar documento: {str(e)}")
            return False

    def list_document_ids(self) -> List[str]:
        return self.document_ids if self.document_ids else []

    def remove_document(self, doc_id: str) -> bool:
        """Elimina un documento del índice"""
        try:
            if doc_id in self.document_ids:
                idx = self.document_ids.index(doc_id)
                self.document_ids.pop(idx)
                self.vectors.pop(idx)
                
                # Eliminar de la base de datos SQLite
                conn = sqlite3.connect(str(self.db_path))
                cursor = conn.cursor()
                cursor.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
                conn.commit()
                conn.close()
                
                self._save_index()
                logger.debug(f"Documento eliminado: {doc_id}")
                return True
            else:
                logger.warning(f"Documento no encontrado para eliminar: {doc_id}")
                return False
        except Exception as e:
            logger.error(f"Error eliminando documento {doc_id}: {str(e)}")
            return False

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un documento del índice"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            cursor.execute('SELECT title, content, metadata FROM documents WHERE id = ?', (doc_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "title": result[0],
                    "content": result[1],
                    "metadata": json.loads(result[2]) if result[2] else {}
                }
            else:
                return None
        except Exception as e:
            logger.error(f"Error obteniendo documento {doc_id}: {str(e)}")
            return None

# Instanciar el indexador globalmente con patrón Singleton
class IndexerSingleton:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IndexerSingleton, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            try:
                self._indexer = DocumentIndexer()
                self._initialized = True
                logger.info("Indexador Singleton inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al crear indexador Singleton: {str(e)}")
                self._indexer = None
    
    def get_indexer(self):
        return self._indexer

# Variable global para el singleton
_indexer_singleton = None

def get_document_indexer():
    """Función para obtener la instancia del indexador de manera lazy"""
    global _indexer_singleton
    if _indexer_singleton is None:
        _indexer_singleton = IndexerSingleton()
    return _indexer_singleton.get_indexer()

# Mantener compatibilidad con código existente
try:
    document_indexer = get_document_indexer()
except Exception as e:
    logger.error(f"Error al obtener indexador: {str(e)}")
    document_indexer = None
