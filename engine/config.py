"""Configuración central del motor RAG.

Todos los parámetros swappeables (modelos, top-k, chunking, rutas) viven acá,
según la sección 10 del spec: cambiar de modelo debe ser tocar una sola línea.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Rutas ---
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_SOURCE_DIR = BASE_DIR / "data" / "source"
DATA_INDEX_DIR = BASE_DIR / "data" / "index"

PDF_FICHAS_PATH = DATA_SOURCE_DIR / "datos_maincal_EJEMPLO.pdf"
BOM_XLSX_PATH = DATA_SOURCE_DIR / "bom_cronos_n04.xlsx"
STOCK_JSON_PATH = DATA_SOURCE_DIR / "stock.json"

CHUNKS_JSON_PATH = DATA_INDEX_DIR / "chunks.json"
EMBEDDINGS_NPY_PATH = DATA_INDEX_DIR / "embeddings.npy"
BOM_JSON_PATH = DATA_INDEX_DIR / "bom.json"

SHARED_CONFIG_PATH = BASE_DIR / "shared" / "app-config.json"

# --- Modelos OpenAI ---
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

# --- Parámetros RAG ---
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 300
EMBEDDING_BATCH_SIZE = 100
TOP_K = 3

# --- Parámetros de generación ---
TEMPERATURE = 0.1  # baja: respuestas fieles al dato, sin creatividad
MAX_TOKENS = 800

# Contenido compartido con el frontend (fuente única: shared/app-config.json,
# que src/lib/app-config.ts importa del lado TypeScript).
def _load_shared_config() -> dict:
    if not SHARED_CONFIG_PATH.exists():
        raise FileNotFoundError(
            "No se encontró shared/app-config.json (archivo versionado con el "
            "producto y las preguntas demo, compartido con el frontend)."
        )
    with open(SHARED_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


_shared = _load_shared_config()
PRODUCTO: str = _shared["producto"]
PREGUNTAS_DEMO: list[str] = _shared["preguntasDemo"]


def get_api_key() -> str:
    """Devuelve la API key de OpenAI o falla con un mensaje claro."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "No se encontró OPENAI_API_KEY. Verificá que exista un archivo .env "
            "en la raíz del proyecto con la línea: OPENAI_API_KEY=tu_clave "
            "(en Vercel, configurala como Environment Variable del proyecto)."
        )
    return api_key


def get_openai_client():
    """Crea el cliente de OpenAI validando primero la API key."""
    from openai import OpenAI

    return OpenAI(api_key=get_api_key())
