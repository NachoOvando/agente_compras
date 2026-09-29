"""Fase de preparación del RAG: lectura de PDF, chunking y embeddings.

Estas funciones se usan desde scripts/build_index.py (offline). En runtime
solo se embebe la pregunta del usuario con get_embeddings.
"""

from pathlib import Path

import numpy as np

from engine import config


def read_pdf_pages(pdf_path: Path) -> list[str]:
    """Extrae el texto de un PDF página por página, validando existencia y
    contenido. Cada ficha de proveedor ocupa una página, así que esto
    devuelve directamente 1 entrada por ficha (páginas sin texto se descartan)."""
    from pypdf import PdfReader

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo '{pdf_path}'. "
            "Verificá que las fichas de proveedores estén en data/source/."
        )

    reader = PdfReader(str(pdf_path))
    paginas = []
    for page in reader.pages:
        contenido = page.extract_text()
        if contenido and contenido.strip():
            paginas.append(contenido.strip())

    if not paginas:
        raise ValueError(
            f"El PDF '{pdf_path.name}' se leyó pero no se pudo extraer texto. "
            "Puede ser un PDF escaneado (imagen) sin texto seleccionable."
        )
    return paginas


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


def split_pages_into_chunks(pages: list[str], chunk_size: int = config.CHUNK_SIZE,
                            overlap: int = config.CHUNK_OVERLAP) -> list[str]:
    """1 chunk por página/ficha; solo subdivide las páginas más largas que
    chunk_size (con el mismo overlap que split_text_chunks). Así una ficha
    completa siempre se recupera entera, sin mezclarse con otras."""
    chunks = []
    for pagina in pages:
        if len(pagina) <= chunk_size:
            chunks.append(pagina)
        else:
            chunks.extend(split_text_chunks(pagina, chunk_size, overlap))
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
