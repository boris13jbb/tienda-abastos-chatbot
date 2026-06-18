#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sistema de embeddings simplificado sin PyTorch ni sentence-transformers.
Fallback robusto basado en vectores hash normalizados (solo requiere numpy).
"""

import logging
from typing import List, Optional, Union

import numpy as np

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_VECTOR_SIZE = 128


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    a = np.array(vec1, dtype=float)
    b = np.array(vec2, dtype=float)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _hash_embedding(text: str, size: int = _VECTOR_SIZE) -> List[float]:
    """Genera un vector determinista a partir del texto (sin modelos externos)."""
    lowered = text.lower().strip()
    seed = abs(hash(lowered)) % (2**32)
    rng = np.random.default_rng(seed)
    vector = rng.random(size).astype(float)
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector.tolist()


class SimpleEmbeddingManager:
    """Gestor de embeddings ligero para entornos sin sentence-transformers/sklearn."""

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or "simple-hash-fallback"
        self._backend = "hash"
        self._initialize_embedding_model()

    def _initialize_embedding_model(self) -> None:
        # Intentar langchain-huggingface solo si está disponible
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            self._embedding_model = HuggingFaceEmbeddings(
                model_name=settings.EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
            self._backend = "huggingface"
            logger.info("Gestor simple: langchain-huggingface (CPU)")
            return
        except Exception as e:
            logger.warning(f"langchain-huggingface no disponible: {e}")

        self._embedding_model = None
        self._backend = "hash"
        logger.info("Gestor simple: fallback hash normalizado (sin ML externo)")

    def get_embeddings(self, texts: Union[str, List[str]]) -> List[List[float]]:
        if isinstance(texts, str):
            texts = [texts]

        if self._backend == "huggingface" and self._embedding_model is not None:
            try:
                return self._embedding_model.embed_documents(texts)
            except Exception as e:
                logger.warning(f"Fallo huggingface en simple manager, usando hash: {e}")
                self._backend = "hash"

        return [_hash_embedding(text) for text in texts]

    def calculate_similarity(self, text1: str, text2: str) -> float:
        try:
            embedding1 = self.get_embeddings(text1)[0]
            embedding2 = self.get_embeddings(text2)[0]
            return _cosine_similarity(embedding1, embedding2)
        except Exception as e:
            logger.error(f"Error calculando similitud: {e}")
            return 0.0


simple_embedding_manager: SimpleEmbeddingManager | None = None


def get_simple_embedding_manager() -> Optional[SimpleEmbeddingManager]:
    global simple_embedding_manager
    if simple_embedding_manager is None:
        try:
            simple_embedding_manager = SimpleEmbeddingManager()
            logger.info("Gestor de embeddings simple inicializado")
        except Exception as e:
            logger.error(f"Error inicializando gestor simple: {e}")
            simple_embedding_manager = None
    return simple_embedding_manager


def simple_embed_text(text: str) -> List[float]:
    manager = get_simple_embedding_manager()
    if manager is None:
        return _hash_embedding(text)
    embeddings = manager.get_embeddings(text)
    return embeddings[0] if embeddings else _hash_embedding(text)
