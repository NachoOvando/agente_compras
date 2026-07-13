"""Fase de augmentation: arma el contexto que se inyecta al LLM.

Contexto = chunks recuperados (RAG sobre fichas PDF)
         + BOM completa del producto (inyección directa, datos exactos)
         + stock actual (inyección directa, con overrides opcionales).

Los datos numéricos NO pasan por embeddings para no perder precisión
(sección 3 del spec).
"""

import json
from functools import lru_cache

from engine import config


@lru_cache(maxsize=1)
def load_bom() -> list[dict]:
    """Carga la BOM normalizada (generada por scripts/build_index.py)."""
    if not config.BOM_JSON_PATH.exists():
        raise FileNotFoundError(
            "No se encontró data/index/bom.json. "
            "Generalo corriendo: python scripts/build_index.py"
        )
    with open(config.BOM_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_stock_file() -> dict:
    if not config.STOCK_JSON_PATH.exists():
        raise FileNotFoundError(
            "No se encontró data/source/stock.json. "
            "Generalo corriendo: python scripts/seed_example_data.py"
        )
    with open(config.STOCK_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_stock(overrides: dict[str, float] | None = None) -> dict:
    """Stock actual de insumos críticos, con overrides opcionales por código.

    Los overrides representan la carga manual/dinámica de stock del spec:
    el usuario puede pisar el valor de un insumo sin tocar el archivo.
    """
    stock = json.loads(json.dumps(_load_stock_file()))  # copia profunda
    if overrides:
        for item in stock["items"]:
            if item["codigo"] in overrides:
                item["stock_actual"] = overrides[item["codigo"]]
    return stock


def format_bom(bom: list[dict]) -> str:
    """BOM como tabla de texto plano para el contexto del LLM."""
    lineas = [
        f"BOM del producto {config.PRODUCTO} (consumo por par producido):",
        "codigo | insumo | unidad | consumo_por_par | critico",
    ]
    for fila in bom:
        lineas.append(
            f"{fila['codigo']} | {fila['insumo']} | {fila['unidad']} | "
            f"{fila['consumo_por_unidad']} | {'SI' if fila['critico'] else 'NO'}"
        )
    return "\n".join(lineas)


def format_stock(stock: dict) -> str:
    """Stock actual como bloque de texto plano para el contexto del LLM."""
    lineas = [
        f"STOCK ACTUAL de insumos críticos (fecha: {stock['fecha_actualizacion']}):",
    ]
    for item in stock["items"]:
        lineas.append(
            f"- {item['insumo']} ({item['codigo']}): stock actual "
            f"{item['stock_actual']} {item['unidad']}, stock mínimo "
            f"{item['stock_minimo']} {item['unidad']}"
        )
    return "\n".join(lineas)


def build_context(retrieved: list[dict], bom: list[dict], stock: dict) -> str:
    """Concatena fichas recuperadas + BOM + stock en un único contexto."""
    fichas = "\n\n".join(res["chunk"] for res in retrieved)
    return (
        "=== FICHAS DE PROVEEDORES (fragmentos recuperados) ===\n"
        f"{fichas}\n\n"
        "=== BOM DEL PRODUCTO ===\n"
        f"{format_bom(bom)}\n\n"
        "=== STOCK ACTUAL ===\n"
        f"{format_stock(stock)}"
    )
