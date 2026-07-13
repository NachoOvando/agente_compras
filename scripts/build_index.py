"""Fase de preparación del RAG (offline). Correr al actualizar cualquier fuente.

1. Lee las fichas de proveedores (PDF), las divide en chunks y genera
   embeddings por lotes → guarda data/index/chunks.json + embeddings.npy.
2. Normaliza la BOM (Excel → JSON) para inyección directa en runtime,
   sin depender de pandas/openpyxl en la serverless function.

Requiere OPENAI_API_KEY en .env. Correr desde la raíz del proyecto:
    python scripts/build_index.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from engine import config
from engine.indexing import get_embeddings, read_pdf_text, split_text_chunks


def build_pdf_index() -> None:
    texto = read_pdf_text(config.PDF_FICHAS_PATH)
    print(f"Texto extraído del PDF: {len(texto):,} caracteres")

    chunks = split_text_chunks(texto)
    print(f"Texto dividido en {len(chunks)} chunks "
          f"(tamaño {config.CHUNK_SIZE}, overlap {config.CHUNK_OVERLAP})")

    client = config.get_openai_client()
    embeddings = get_embeddings(client, chunks)
    print(f"Embeddings generados: {embeddings.shape} ({config.EMBEDDING_MODEL})")

    config.DATA_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.CHUNKS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    np.save(config.EMBEDDINGS_NPY_PATH, embeddings)
    print(f"Índice guardado en {config.DATA_INDEX_DIR}")


def build_bom_json() -> None:
    if not config.BOM_XLSX_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró la BOM '{config.BOM_XLSX_PATH}'. "
            "Generala corriendo: python scripts/seed_example_data.py"
        )
    df = pd.read_excel(config.BOM_XLSX_PATH)
    columnas = {"codigo", "insumo", "unidad", "consumo_por_unidad", "critico"}
    faltantes = columnas - set(df.columns)
    if faltantes:
        raise ValueError(f"La BOM no tiene las columnas esperadas: faltan {faltantes}")

    bom = [
        {
            "codigo": fila["codigo"],
            "insumo": fila["insumo"],
            "unidad": fila["unidad"],
            "consumo_por_unidad": float(fila["consumo_por_unidad"]),
            "critico": str(fila["critico"]).strip().upper() == "SI",
        }
        for _, fila in df.iterrows()
    ]

    config.DATA_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.BOM_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(bom, f, ensure_ascii=False, indent=2)
    print(f"BOM normalizada: {config.BOM_JSON_PATH} ({len(bom)} insumos)")


if __name__ == "__main__":
    build_bom_json()
    build_pdf_index()
    print("\nÍndice completo. El asistente ya puede responder consultas.")
