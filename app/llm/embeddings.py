#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo para la gestión de embeddings.
Permite seleccionar el modelo de embeddings a utilizar dinámicamente.
"""

import logging
from typing import List, Optional, Union

# Aplicar parches de PyTorch antes de cualquier importación
from app.utils.torch_patch import apply_torch_patches
apply_torch_patches()

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class EmbeddingManager:
    """
    Gestiona la creación de embeddings para representación vectorial de texto.
    El modelo de embeddings se elige dinámicamente basado en settings.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self._embedding_model = None
        self._initialize_embedding_model()

    def _initialize_embedding_model(self) -> None:
        """
        Inicializa el modelo de embeddings basado en el nombre.
        """
        try:
            # Parche completo y robusto para el error de autocast en PyTorch
            import torch
            import sys
            import importlib

            # Verificar si autocast existe en torch.amp
            if hasattr(torch, 'amp'):
                if not hasattr(torch.amp, 'autocast'):
                    # Crear un mock completo de autocast si no existe
                    class MockAutocast:
                        def __init__(self, device_type='cuda', dtype=None, enabled=True, cache_enabled=None):
                            self.device_type = device_type
                            self.dtype = dtype
                            self.enabled = enabled
                            self.cache_enabled = cache_enabled

                        def __enter__(self):
                            return self

                        def __exit__(self, *args):
                            pass

                        def __call__(self, *args, **kwargs):
                            return self

                    torch.amp.autocast = MockAutocast
                    logger.info("Parche aplicado: MockAutocast completo creado para torch.amp")

            # Parche adicional: interceptar la importación problemática de forma más robusta
            original_import = __builtins__['__import__']

            def patched_import(name, globals=None, locals=None, fromlist=(), level=0):
                # Interceptar importaciones problemáticas relacionadas con autocast
                if name == 'torch.amp.autocast' or (fromlist and 'autocast' in fromlist and 'torch.amp' in name):
                    # Asegurar que torch.amp.autocast existe antes de retornarlo
                    if hasattr(torch, 'amp') and hasattr(torch.amp, 'autocast'):
                        if fromlist and 'autocast' in fromlist:
                            # Crear un módulo mock para la importación from torch.amp import autocast
                            class MockModule:
                                autocast = torch.amp.autocast
                            return MockModule()
                        return torch.amp.autocast
                    else:
                        # Crear el mock si aún no existe
                        class MockAutocast:
                            def __init__(self, *args, **kwargs):
                                pass
                            def __enter__(self):
                                return self
                            def __exit__(self, *args):
                                pass
                            def __call__(self, *args, **kwargs):
                                return self

                        if not hasattr(torch, 'amp'):
                            torch.amp = type('MockAmp', (), {})()
                        torch.amp.autocast = MockAutocast

                        # Agregar autocast_mode si no existe
                        if not hasattr(torch.amp, 'autocast_mode'):
                            class MockAutocastMode:
                                def __init__(self, *args, **kwargs):
                                    pass
                                def __enter__(self):
                                    return self
                                def __exit__(self, *args):
                                    pass
                            torch.amp.autocast_mode = MockAutocastMode

                        if fromlist and 'autocast' in fromlist:
                            class MockModule:
                                autocast = MockAutocast
                            return MockModule()
                        return MockAutocast

                # Para otras importaciones, usar el comportamiento normal
                return original_import(name, globals, locals, fromlist, level)

            # Aplicar el parche temporalmente
            __builtins__['__import__'] = patched_import

            try:
                # Intentar importar con manejo de errores específicos
                if "sentence-transformers" in self.model_name:
                    logger.info(f"Inicializando sentence-transformers con modelo: {self.model_name}")

                    # Parche específico para sentence-transformers antes de la importación
                    try:
                        import sentence_transformers
                        # Verificar si sentence_transformers tiene problemas con autocast
                        if hasattr(sentence_transformers, 'models') and hasattr(sentence_transformers.models, 'Transformer'):
                            logger.info("sentence-transformers disponible, procediendo con inicialización")
                    except Exception as st_error:
                        logger.warning(f"Advertencia en verificación previa de sentence-transformers: {st_error}")

                    from sentence_transformers import SentenceTransformer
                    self._embedding_model = SentenceTransformer(self.model_name)
                    logger.info(f"Modelo de embeddings inicializado exitosamente: {self.model_name} (sentence-transformers)")

                else:
                    logger.info(f"Inicializando con langchain_huggingface: {self.model_name}")
                    # Fall back a langchain_huggingface si no es sentence-transformers
                    from langchain_huggingface import HuggingFaceEmbeddings
                    self._embedding_model = HuggingFaceEmbeddings(model_name=self.model_name)
                    logger.info(f"Modelo de embeddings inicializado exitosamente: {self.model_name} (langchain-huggingface)")

            finally:
                # Restaurar la importación original
                __builtins__['__import__'] = original_import
                logger.debug("Importación original restaurada")

        except ImportError as e:
            logger.error(f"Error de importación: {str(e)}")
            logger.info("Iniciando secuencia de fallback para modelo de embeddings...")

            # Secuencia de fallback múltiple
            fallback_models = [
                "all-MiniLM-L6-v2",
                "all-mpnet-base-v2",
                "distilbert-base-nli-mean-tokens",
                "paraphrase-MiniLM-L6-v2"
            ]

            for fallback_model in fallback_models:
                try:
                    logger.info(f"Intentando fallback con modelo: {fallback_model}")
                    from sentence_transformers import SentenceTransformer
                    self._embedding_model = SentenceTransformer(fallback_model)
                    logger.info(f"Modelo de embeddings fallback inicializado exitosamente: {fallback_model}")
                    self.model_name = fallback_model  # Actualizar el nombre del modelo
                    break
                except Exception as fallback_error:
                    logger.warning(f"Fallback falló para {fallback_model}: {str(fallback_error)}")
                    continue
            else:
                # Si todos los fallbacks fallan, intentar con langchain como último recurso
                try:
                    logger.info("Intentando último recurso con langchain_huggingface...")
                    from langchain_huggingface import HuggingFaceEmbeddings
                    self._embedding_model = HuggingFaceEmbeddings(
                        model_name="sentence-transformers/all-MiniLM-L6-v2",
                        model_kwargs={'device': 'cpu'},  # Forzar CPU
                        encode_kwargs={'normalize_embeddings': True}
                    )
                    logger.info("Modelo de embeddings último recurso inicializado con langchain_huggingface (CPU)")
                except Exception as final_error:
                    logger.error(f"Error en último recurso langchain: {str(final_error)}")

                    # Fallback ultra-simple con embeddings básicos
                    try:
                        logger.info("Intentando fallback ultra-simple...")
                        from app.llm.simple_embeddings import get_simple_embedding_manager
                        simple_manager = get_simple_embedding_manager()
                        if simple_manager:
                            self._embedding_model = simple_manager
                            self.model_name = "simple-embeddings"
                            logger.info("✅ Fallback ultra-simple inicializado")
                        else:
                            raise Exception("Fallback simple falló")
                    except Exception as ultra_error:
                        logger.error(f"Error en fallback ultra-simple: {str(ultra_error)}")
                        raise ImportError(f"No se pudo inicializar ningún modelo de embeddings. Error original: {str(e)}")

        except Exception as e:
            logger.error(f"Error general al inicializar modelo de embeddings: {str(e)}")
            logger.error(f"Tipo de error: {type(e).__name__}")
            logger.error(f"Argumentos del error: {e.args}")

            # Información adicional de depuración
            import torch
            logger.info(f"Versión de PyTorch: {torch.__version__}")
            logger.info(f"torch.amp disponible: {hasattr(torch, 'amp')}")
            if hasattr(torch, 'amp'):
                logger.info(f"torch.amp.autocast disponible: {hasattr(torch.amp, 'autocast')}")

            raise

    def get_embeddings(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Genera embeddings para uno o varios textos.
        """
        if self._embedding_model is None:
            raise ValueError("Modelo de embeddings no inicializado")

        try:
            if isinstance(texts, str):
                texts = [texts]

            # Opcional: Normalizar el texto (si quieres seguir limpiando)
            from app.rag.text_processor import text_processor
            processed_texts = []
            for text in texts:
                normalized_text = text_processor.normalize_text(text)
                clean_text = text_processor.remove_stopwords(normalized_text)
                processed_texts.append(clean_text)

            logger.debug(f"Textos procesados para embeddings: {len(processed_texts)} textos")

            if hasattr(self._embedding_model, 'encode'):
                embeddings = self._embedding_model.encode(processed_texts)
                return embeddings.tolist()
            elif hasattr(self._embedding_model, 'embed_documents'):
                return self._embedding_model.embed_documents(processed_texts)
            elif hasattr(self._embedding_model, 'get_embeddings'):
                # Fallback simple
                return self._embedding_model.get_embeddings(processed_texts)
            else:
                raise ValueError("El modelo de embeddings no tiene métodos conocidos")
        except Exception as e:
            logger.error(f"Error al generar embeddings: {str(e)}")
            raise

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calcula la similitud coseno entre dos textos.
        """
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity

        try:
            embedding1 = self.get_embeddings(text1)[0]
            embedding2 = self.get_embeddings(text2)[0]

            vec1 = np.array(embedding1).reshape(1, -1)
            vec2 = np.array(embedding2).reshape(1, -1)

            return float(cosine_similarity(vec1, vec2)[0][0])
        except Exception as e:
            logger.error(f"Error al calcular similitud: {str(e)}")
            return 0.0

# --- Instancia Global ---
embedding_manager = None

def get_embedding_manager():
    """
    Obtiene la instancia del gestor de embeddings, inicializándola si es necesario.
    Si falla sentence-transformers, usa el gestor simple (hash o huggingface CPU).
    """
    global embedding_manager
    if embedding_manager is not None:
        return embedding_manager

    try:
        embedding_manager = EmbeddingManager()
        logger.info(f"Gestor de embeddings inicializado correctamente ({settings.EMBEDDING_MODEL})")
        return embedding_manager
    except Exception as e:
        logger.error(f"Error al inicializar gestor de embeddings principal: {str(e)}")

    logger.info("Intentando inicializar con gestor simple como fallback...")
    try:
        from app.llm.simple_embeddings import get_simple_embedding_manager

        simple_manager = get_simple_embedding_manager()
        if not simple_manager:
            logger.error("No se pudo inicializar el gestor simple de embeddings")
            return None

        class EmbeddingManagerWrapper:
            def __init__(self, simple_manager):
                self._simple_manager = simple_manager
                self.model_name = getattr(simple_manager, "model_name", "simple-embeddings-fallback")

            def get_embeddings(self, texts):
                return self._simple_manager.get_embeddings(texts)

            def calculate_similarity(self, text1, text2):
                return self._simple_manager.calculate_similarity(text1, text2)

        embedding_manager = EmbeddingManagerWrapper(simple_manager)
        logger.info("Gestor de embeddings simple inicializado como fallback")
        return embedding_manager
    except Exception as fallback_error:
        logger.error(f"Error al inicializar gestor simple como fallback: {fallback_error}")
        return None

# --- NUEVO: Función embed_text usada en health_check ---
def embed_text(text: str) -> List[float]:
    """Genera un vector de embedding para un solo texto."""
    manager = get_embedding_manager()
    if manager is None:
        from app.llm.simple_embeddings import simple_embed_text
        return simple_embed_text(text)

    embedding = manager.get_embeddings(text)
    return embedding[0] if embedding else []
