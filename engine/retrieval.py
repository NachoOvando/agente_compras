"""Fase de recuperación: similitud coseno contra el índice precomputado."""

import json
from functools import lru_cache

import numpy as np

from engine import config


@lru_cache(maxsize=1)
def load_index() -> tuple[tuple[str, ...], np.ndarray]:
    """Carga chunks y embeddings desde disco (una sola vez por proceso)."""
    if not config.CHUNKS_JSON_PATH.exists() or not config.EMBEDDINGS_NPY_PATH.exists():
        raise FileNotFoundError(
            "No se encontró el índice de embeddings en data/index/. "
            "Generalo corriendo: python scripts/build_index.py"
        )
    with open(config.CHUNKS_JSON_PATH, encoding="utf-8") as f:
        chunks = tuple(json.load(f))
    embeddings = np.load(config.EMBEDDINGS_NPY_PATH)
    return chunks, embeddings


def cosine_similarities(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Similitud coseno entre un vector consulta y cada fila de la matriz."""
    query_norm = np.linalg.norm(query)
    matrix_norms = np.linalg.norm(matrix, axis=1)
    # Evita división por cero ante vectores nulos
    denom = np.where(matrix_norms * query_norm == 0, 1e-12, matrix_norms * query_norm)
    return (matrix @ query) / denom


def top_k_chunks(question_embedding: np.ndarray, chunks: tuple[str, ...],
                 chunk_embeddings: np.ndarray, k: int = config.TOP_K) -> list[dict]:
    """Devuelve los k chunks más similares a la pregunta, con su score."""
    similarities = cosine_similarities(question_embedding, chunk_embeddings)
    top_indices = similarities.argsort()[::-1][:k]
    return [
        {
            "index": int(idx),
            "score": float(similarities[idx]),
            "chunk": chunks[idx],
        }
        for idx in top_indices
    ]
