"""Fase de preparación del RAG: lectura de PDF, chunking y embeddings.

Estas funciones se usan desde scripts/build_index.py (offline). En runtime
solo se embebe la pregunta del usuario con get_embeddings.
"""

from pathlib import Path

import numpy as np

from engine import config


def read_pdf_text(pdf_path: Path) -> str:
    """Extrae el texto completo de un PDF, validando existencia y contenido."""
    from pypdf import PdfReader

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo '{pdf_path}'. "
            "Verificá que las fichas de proveedores estén en data/source/."
        )

    reader = PdfReader(str(pdf_path))
    texto = ""
    for page in reader.pages:
        contenido = page.extract_text()
        if contenido:  # algunas páginas pueden devolver None
            texto += contenido

    if not texto.strip():
        raise ValueError(
            f"El PDF '{pdf_path.name}' se leyó pero no se pudo extraer texto. "
            "Puede ser un PDF escaneado (imagen) sin texto seleccionable."
        )
    return texto


def split_text_chunks(texto: str, chunk_size: int = config.CHUNK_SIZE,
                      overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """Divide el texto en chunks de tamaño fijo con overlap entre consecutivos."""
    if chunk_size <= 0:
        raise ValueError("chunk_size debe ser mayor que 0")
    if overlap >= chunk_size:
        raise ValueError("overlap debe ser menor que chunk_size")

    chunks = []
    start = 0
    while start < len(texto):
        end = start + chunk_size
        chunks.append(texto[start:end])
        start = end - overlap
    return chunks


def get_embeddings(client, texts: list[str],
                   batch_size: int = config.EMBEDDING_BATCH_SIZE) -> np.ndarray:
    """Genera embeddings por lotes para no chocar con límites de la API."""
    embeddings = []
    for i in range(0, len(texts), batch_size):
        lote = texts[i:i + batch_size]
        response = client.embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=lote,
        )
        embeddings.extend(item.embedding for item in response.data)
    return np.array(embeddings)
