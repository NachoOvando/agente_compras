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
import re
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


# Talle: sufijo al final de "Número de material", ej. "CRONOS, -N, 04, T. 40".
_RE_TALLA = re.compile(r"T\.\s*(\d+)")
# Familia: descripción del componente sin el sufijo de talle (mismo talle
# puede venir como ", T. 34" o " T34,5" — cubre ambas formas).
_RE_SUFIJO_TALLE = re.compile(r",?\s*T\.?\s*\d+([,.]\d+)?$")

# Unidades de medida SAP → unidad amigable usada en el resto del sistema.
UM_A_UNIDAD = {"G": "g", "KG": "kg", "PAA": "par", "UN": "unidad", "M": "m"}

# Códigos SAP críticos que se combinan en un único insumo crítico "lógico"
# (ej. el conjunto sistema PU viene de 4 componentes SAP distintos que se
# compran/consumen juntos). Se matchea por substring sobre la familia SAP
# (post-eliminación del sufijo de talle), en mayúsculas.
CRITICOS_SAP_A_INSUMO = {
    "SISTEMA PU": "Conjunto Sistema PU",
    "CAJA EMPAQUE": "Caja de empaque",
    "PUNTERA ACERO": "Puntera de acero",
}
# Orden fijo de códigos para los críticos (debe coincidir con data/source/stock.json).
ORDEN_CRITICOS = ["Conjunto Sistema PU", "Puntera de acero", "Caja de empaque"]


def _insumo_de_familia(familia: str, critico: bool) -> str:
    """Nombre de insumo a partir de la familia SAP. Los críticos se combinan
    según CRITICOS_SAP_A_INSUMO (ej. los 4 componentes del sistema PU pasan a
    ser un solo insumo crítico); los no críticos usan la familia tal cual."""
    if not critico:
        return familia
    familia_upper = familia.upper()
    for clave, insumo in CRITICOS_SAP_A_INSUMO.items():
        if clave in familia_upper:
            return insumo
    raise ValueError(
        f"Componente crítico '{familia}' no tiene mapeo a insumo conocido. "
        "Agregalo a CRITICOS_SAP_A_INSUMO en scripts/build_index.py."
    )


def _unidad_de(um) -> str:
    clave = str(um).strip().upper()
    if clave not in UM_A_UNIDAD:
        raise ValueError(
            f"Unidad de medida SAP desconocida: '{um}'. Agregala a UM_A_UNIDAD "
            "en scripts/build_index.py."
        )
    return UM_A_UNIDAD[clave]


def build_bom_json() -> None:
    """Normaliza la BOM a partir del export crudo de SAP (una fila por
    componente x talle). Agrupa por familia (ignorando el sufijo de talle),
    fusiona los componentes críticos que forman un mismo insumo lógico (ver
    CRITICOS_SAP_A_INSUMO) y detecta consumo fijo vs. variable por talle:
    si el consumo es igual en todos los talles disponibles usa
    consumo_por_unidad; si varía, exige que estén los 17 talles y arma
    consumo_por_talle (nunca conviven ambos con un número ambiguo)."""
    if not config.BOM_XLSX_PATH.exists():
        raise FileNotFoundError(f"No se encontró la BOM '{config.BOM_XLSX_PATH}'.")
    df = pd.read_excel(config.BOM_XLSX_PATH)
    columnas = {"Número de material", "Componente de lista de materia", "Cantidad", "UM", "Tipo"}
    faltantes = columnas - set(df.columns)
    if faltantes:
        raise ValueError(f"La BOM no tiene las columnas esperadas: faltan {faltantes}")

    df = df.rename(columns={
        "Número de material": "talla_texto",
        "Componente de lista de materia": "componente",
        "Cantidad": "cantidad",
        "UM": "um",
        "Tipo": "tipo",
    })

    df["talla"] = df["talla_texto"].str.extract(_RE_TALLA)[0]
    sin_talla = df[df["talla"].isna()]
    if not sin_talla.empty:
        raise ValueError(
            "No se pudo extraer el talle de estas filas de 'Número de material': "
            f"{sorted(sin_talla['talla_texto'].unique().tolist())}"
        )

    df["familia"] = df["componente"].str.replace(_RE_SUFIJO_TALLE, "", regex=True).str.strip()
    df["critico"] = df["tipo"].astype(str).str.strip().str.lower() == "critico"
    df["insumo"] = df.apply(lambda f: _insumo_de_familia(f["familia"], f["critico"]), axis=1)
    df["unidad"] = df["um"].apply(_unidad_de)

    # Varios componentes SAP pueden mapear al mismo insumo lógico (ej. los 4
    # del sistema PU): sumar cantidad por insumo+talle.
    agregado = df.groupby(["insumo", "talla"], as_index=False).agg(
        cantidad=("cantidad", "sum"), unidad=("unidad", "first"), critico=("critico", "first"),
    )
    for insumo, grupo in agregado.groupby("insumo"):
        if grupo["unidad"].nunique() > 1:
            raise ValueError(
                f"El insumo '{insumo}' mezcla unidades de medida distintas: "
                f"{sorted(grupo['unidad'].unique().tolist())}"
            )
        if grupo["critico"].nunique() > 1:
            raise ValueError(f"El insumo '{insumo}' mezcla filas críticas y no críticas.")

    no_criticos = sorted(set(agregado["insumo"]) - set(ORDEN_CRITICOS))
    codigo_por_insumo = {
        nombre: f"INS-{i:03d}"
        for i, nombre in enumerate(ORDEN_CRITICOS + no_criticos, start=1)
    }

    talles_esperados = set(config.TALLES)
    bom = []
    for insumo in ORDEN_CRITICOS + no_criticos:
        grupo = agregado[agregado["insumo"] == insumo]
        if grupo.empty:
            continue  # insumo crítico esperado que no aparece en este export
        unidad = grupo["unidad"].iloc[0]
        critico = bool(grupo["critico"].iloc[0])
        valores = {row["talla"]: round(float(row["cantidad"]), 6) for _, row in grupo.iterrows()}
        valores_unicos = set(valores.values())

        if len(valores_unicos) == 1:
            consumo_por_unidad, consumo_por_talle = valores_unicos.pop(), None
        else:
            faltan = talles_esperados - set(valores)
            if faltan:
                raise ValueError(
                    f"El insumo '{insumo}' tiene consumo variable por talle pero no "
                    f"cubre todos los talles: faltan T{', T'.join(sorted(faltan))}."
                )
            consumo_por_unidad = None
            consumo_por_talle = {t: valores[t] for t in config.TALLES}

        bom.append({
            "codigo": codigo_por_insumo[insumo],
            "insumo": insumo,
            "unidad": unidad,
            "consumo_por_unidad": consumo_por_unidad,
            "critico": critico,
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
    "CONJ SISTEMA PU": "Conjunto Sistema PU",
    "PUNTERA ACERO 59 NORMAL": "Puntera de acero",
    "CAJA EMPAQUE (BOTA/BOTÍN)": "Caja de empaque",
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
