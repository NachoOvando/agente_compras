"""Fase de preparación del RAG (offline). Correr al actualizar cualquier fuente.

1. Lee las fichas de proveedores (PDF), las divide en chunks y genera
   embeddings por lotes → guarda data/index/chunks.json + embeddings.npy.
2. Normaliza la BOM (Excel → JSON) para inyección directa en runtime,
   sin depender de pandas/openpyxl en la serverless function. Soporta
   consumo variable por talle (columnas opcionales T34..T50).
3. Normaliza las políticas de inventario (Excel → JSON) de los insumos
   críticos: lead time, demanda, stock de seguridad, ROP, stock máximo.

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
    """Normaliza la BOM. Soporta consumo fijo por par (consumo_por_unidad) y,
    opcionalmente, consumo variable por talle (columnas T34..T50: si un
    insumo las trae completas, manda ese detalle y consumo_por_unidad queda
    en None — nunca conviven un número "de referencia" ambiguo con la tabla
    real, para que el LLM no pueda usar el valor equivocado por error)."""
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

    talle_cols = [f"T{t}" for t in config.TALLES]
    presentes = [c for c in talle_cols if c in df.columns]
    if 0 < len(presentes) < len(talle_cols):
        faltan = sorted(set(talle_cols) - set(presentes))
        raise ValueError(
            "La BOM tiene columnas de talle incompletas a nivel archivo: "
            f"faltan {faltan}. Si algún insumo varía por talle hay que agregar "
            "las 17 columnas T34..T50; si ninguno varía, no agregar ninguna."
        )
    tiene_talles = len(presentes) == len(talle_cols)

    bom = []
    for _, fila in df.iterrows():
        codigo, insumo = fila["codigo"], fila["insumo"]
        consumo_por_talle = None
        consumo_por_unidad = fila["consumo_por_unidad"]

        if tiene_talles:
            valores = fila[talle_cols]
            completos, algunos = valores.notna().all(), valores.notna().any()
            if algunos and not completos:
                faltan = [t for t in config.TALLES if pd.isna(fila[f"T{t}"])]
                raise ValueError(
                    f"La fila '{codigo}' ({insumo}) tiene talles incompletos en "
                    f"DETALLE POR TALLE: faltan T{', T'.join(faltan)}. Completá "
                    "las 17 columnas o dejalas todas en blanco."
                )
            if completos:
                consumo_por_talle = {t: float(fila[f"T{t}"]) for t in config.TALLES}
                if pd.notna(consumo_por_unidad):
                    print(
                        f"Aviso: '{codigo}' ({insumo}) tiene consumo_por_unidad Y "
                        "detalle por talle; se usa el detalle por talle."
                    )
                consumo_por_unidad = None

        bom.append({
            "codigo": codigo,
            "insumo": insumo,
            "unidad": fila["unidad"],
            "consumo_por_unidad": (
                float(consumo_por_unidad) if pd.notna(consumo_por_unidad) else None
            ),
            "critico": str(fila["critico"]).strip().upper() == "SI",
            "consumo_por_talle": consumo_por_talle,
        })

    config.DATA_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.BOM_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(bom, f, ensure_ascii=False, indent=2)
    print(f"BOM normalizada: {config.BOM_JSON_PATH} ({len(bom)} insumos)")


# Equivalencia entre el nombre de familia del archivo de políticas de
# inventario (planificación/SAP) y el nombre de insumo usado en la BOM y
# las fichas de proveedores. Agregar acá si cambia el set de insumos críticos.
FAMILIA_A_INSUMO = {
    "CONJ SISTEMA PU": "Suela de poliuretano (PU)",
    "PUNTERA ACERO 59 NORMAL": "Puntera de acero",
    "CAJA EMPAQUE (BOTA/BOTÍN)": "Caja de empaque",
    # Identidad: los datos de ejemplo (scripts/seed_example_data.py) ya usan
    # el nombre amigable directamente, sin nomenclatura SAP de por medio.
    "Suela de poliuretano (PU)": "Suela de poliuretano (PU)",
    "Puntera de acero": "Puntera de acero",
    "Caja de empaque": "Caja de empaque",
}


def build_politicas_json() -> None:
    """Normaliza las políticas de inventario (lead time, demanda, stock de
    seguridad, ROP, stock máximo) de los insumos críticos. Inyección directa
    igual que la BOM y el stock: son números exactos, no pasan por embeddings."""
    if not config.POLITICAS_XLSX_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo de políticas de inventario "
            f"'{config.POLITICAS_XLSX_PATH}'."
        )
    df = pd.read_excel(config.POLITICAS_XLSX_PATH)
    columnas = {
        "Familia", "Política", "Lead_Time_dias", "Demanda_media_mensual",
        "Desvio_mensual", "Stock_Seguridad", "ROP_o_Nivel_Objetivo",
        "Stock_Maximo", "Cobertura_SS_dias",
    }
    faltantes = columnas - set(df.columns)
    if faltantes:
        raise ValueError(
            f"El archivo de políticas no tiene las columnas esperadas: faltan {faltantes}"
        )

    politicas = []
    for _, fila in df.iterrows():
        familia = str(fila["Familia"]).strip()
        insumo = FAMILIA_A_INSUMO.get(familia)
        if insumo is None:
            raise ValueError(
                f"La familia '{familia}' del archivo de políticas no tiene "
                "equivalencia en FAMILIA_A_INSUMO (scripts/build_index.py). "
                "Agregala si es un insumo crítico nuevo."
            )
        politicas.append({
            "insumo": insumo,
            "politica": str(fila["Política"]).strip(),
            "lead_time_dias": float(fila["Lead_Time_dias"]),
            "demanda_media_mensual": float(fila["Demanda_media_mensual"]),
            "desvio_mensual": float(fila["Desvio_mensual"]),
            "stock_seguridad": float(fila["Stock_Seguridad"]),
            "rop": float(fila["ROP_o_Nivel_Objetivo"]),
            "stock_maximo": float(fila["Stock_Maximo"]),
            "cobertura_ss_dias": float(fila["Cobertura_SS_dias"]),
        })

    config.DATA_INDEX_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.POLITICAS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(politicas, f, ensure_ascii=False, indent=2)
    print(
        f"Políticas de inventario normalizadas: {config.POLITICAS_JSON_PATH} "
        f"({len(politicas)} insumos)"
    )


if __name__ == "__main__":
    build_bom_json()
    build_politicas_json()
    build_pdf_index()
    print("\nÍndice completo. El asistente ya puede responder consultas.")
