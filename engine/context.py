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
def load_politicas() -> list[dict]:
    """Políticas de inventario de los insumos críticos (generadas por
    scripts/build_index.py a partir del análisis de lead time/demanda/ROP)."""
    if not config.POLITICAS_JSON_PATH.exists():
        raise FileNotFoundError(
            "No se encontró data/index/politicas.json. "
            "Generalo corriendo: python scripts/build_index.py"
        )
    with open(config.POLITICAS_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_curva_talles() -> dict:
    """Distribución típica de producción por talle (% que suma ~100), para
    poder desglosar una cantidad total de pares cuando el usuario no da un
    talle puntual. JSON versionado a mano en data/source/ (mismo tratamiento
    que stock.json — no pasa por scripts/build_index.py)."""
    if not config.CURVA_TALLES_JSON_PATH.exists():
        raise FileNotFoundError(
            "No se encontró data/source/curva_talles.json. Creá el archivo a "
            "mano (ver docs/customization.md)."
        )
    with open(config.CURVA_TALLES_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)["talles"]


@lru_cache(maxsize=1)
def _load_stock_file() -> dict:
    if not config.STOCK_JSON_PATH.exists():
        raise FileNotFoundError(
            "No se encontró data/source/stock.json. Creá el archivo a mano "
            "(ver docs/customization.md)."
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
    """BOM como tabla de texto plano para el contexto del LLM.

    La mayoría de los insumos consumen una cantidad fija por par. Algunos
    (ej. el conjunto sistema PU) consumen distinto según el talle del
    calzado: para esos, la tabla principal muestra un placeholder y el valor
    real va en un bloque "DETALLE POR TALLE" aparte (solo aparece si hace
    falta, para no inflar el contexto de los insumos fijos).
    """
    lineas = [
        f"BOM del producto {config.PRODUCTO} (consumo por par producido):",
        "codigo | insumo | unidad | consumo_por_par | critico",
    ]
    variables = []
    for fila in bom:
        consumo_por_talle = fila.get("consumo_por_talle")
        if consumo_por_talle:
            variables.append(fila)
            consumo_txt = "variable por talle (ver detalle abajo)"
        else:
            consumo_txt = fila["consumo_por_unidad"]
        lineas.append(
            f"{fila['codigo']} | {fila['insumo']} | {fila['unidad']} | "
            f"{consumo_txt} | {'SI' if fila['critico'] else 'NO'}"
        )

    if variables:
        lineas.append("")
        lineas.append(
            "DETALLE POR TALLE (consumo por par de los insumos que varían "
            f"según el talle, T.{config.TALLES[0]} a T.{config.TALLES[-1]}):"
        )
        for fila in variables:
            detalle = " ".join(
                f"T{t}={v}" for t, v in fila["consumo_por_talle"].items()
            )
            lineas.append(
                f"{fila['codigo']} | {fila['insumo']} ({fila['unidad']}/par): {detalle}"
            )

    return "\n".join(lineas)


def format_politicas(politicas: list[dict]) -> str:
    """Políticas de inventario de los insumos críticos, como texto plano."""
    lineas = [
        "POLÍTICAS DE INVENTARIO de los insumos críticos (calculadas con lead "
        "time, demanda y variabilidad de la demanda):",
        "insumo | política | lead_time_dias | demanda_media_mensual | "
        "desvio_mensual | stock_seguridad | ROP/nivel_objetivo | stock_maximo "
        "| cobertura_stock_seguridad_dias",
    ]
    for fila in politicas:
        lineas.append(
            f"{fila['insumo']} | {fila['politica']} | {fila['lead_time_dias']} | "
            f"{fila['demanda_media_mensual']} | {fila['desvio_mensual']} | "
            f"{fila['stock_seguridad']} | {fila['rop']} | {fila['stock_maximo']} | "
            f"{fila['cobertura_ss_dias']}"
        )
    return "\n".join(lineas)


def compute_consumo_ponderado_curva(bom: list[dict], curva_talles: dict) -> list[dict]:
    """Consumo por par ponderado por la curva normal de talles, precalculado
    en Python para cada insumo variable por talle (no depende de la cantidad
    de pares que pida el usuario — solo de datos ya cargados). Usado por
    engine/tools.py para calcular la necesidad cuando se aplica la curva
    normal — el LLM nunca ve ni suma estos números directamente (ver nota en
    tools.py: fue justo lo que causó una confusión con el talle puntual).
    Los % de la curva ya suman 100, así que la suma ponderada es el promedio."""
    ponderado = []
    for fila in bom:
        consumo_por_talle = fila.get("consumo_por_talle")
        if not consumo_por_talle:
            continue
        valor = sum(
            consumo_por_talle[t] * curva_talles[t] / 100 for t in config.TALLES
        )
        ponderado.append({
            "codigo": fila["codigo"],
            "insumo": fila["insumo"],
            "unidad": fila["unidad"],
            "consumo_ponderado_por_par": round(valor, 3),
        })
    return ponderado


def format_curva_talles(curva: dict) -> str:
    """Distribución de talles como texto plano, con la advertencia de que es
    un dato de ejemplo hasta que se cargue la curva real de la empresa. Solo
    informativo — el cálculo de necesidad con curva normal lo hace
    engine/tools.py, no el LLM a partir de este texto."""
    lineas = [
        "Distribución típica de producción por talle (% de pares por talle, "
        "PLACEHOLDER — dato de ejemplo, todavía no es la curva real):",
        " ".join(f"T{t}={pct}%" for t, pct in curva.items()),
    ]
    return "\n".join(lineas)


@lru_cache(maxsize=1)
def load_contexto_negocio() -> str:
    """Contexto operativo del negocio (perfil productivo, metodología de
    criticidad de insumos, curva de ventas, qué queda fuera de alcance y por
    qué) — prosa versionada a mano en data/source/, mismo tratamiento que
    stock.json. Se inyecta tal cual, sin pasar por embeddings: es corto y
    siempre relevante para cualquier pregunta."""
    if not config.CONTEXTO_NEGOCIO_PATH.exists():
        raise FileNotFoundError(
            "No se encontró data/source/contexto_negocio.md. Creá el archivo "
            "a mano (ver docs/customization.md)."
        )
    return config.CONTEXTO_NEGOCIO_PATH.read_text(encoding="utf-8")


def format_stock(stock: dict) -> str:
    """Stock actual como bloque de texto plano para el contexto del LLM."""
    lineas = [
        f"STOCK ACTUAL de insumos críticos (fecha: {stock['fecha_actualizacion']}):",
    ]
    for item in stock["items"]:
        bajo_minimo = item["stock_actual"] < item["stock_minimo"]
        lineas.append(
            f"- {item['insumo']} ({item['codigo']}): stock actual "
            f"{item['stock_actual']} {item['unidad']}, stock mínimo "
            f"{item['stock_minimo']} {item['unidad']}, ¿por debajo del "
            f"mínimo? {'SÍ' if bajo_minimo else 'NO'}"
        )
    lineas.append("")
    lineas.append(
        "Nota: los insumos que no aparecen en este listado (no críticos) se "
        "consideran con disponibilidad suficiente y no son limitantes para "
        "la producción."
    )
    return "\n".join(lineas)


def build_context(
    retrieved: list[dict], bom: list[dict], stock: dict, politicas: list[dict],
    curva_talles: dict, contexto_negocio: str,
) -> str:
    """Concatena fichas recuperadas + BOM + stock + políticas + curva de
    talles + contexto de negocio en un único contexto."""
    fichas = "\n\n".join(res["chunk"] for res in retrieved)
    return (
        "=== CONTEXTO DEL NEGOCIO ===\n"
        f"{contexto_negocio}\n\n"
        "=== FICHAS DE PROVEEDORES (fragmentos recuperados) ===\n"
        f"{fichas}\n\n"
        "=== BOM DEL PRODUCTO ===\n"
        f"{format_bom(bom)}\n\n"
        "=== STOCK ACTUAL ===\n"
        f"{format_stock(stock)}\n\n"
        "=== POLÍTICAS DE INVENTARIO ===\n"
        f"{format_politicas(politicas)}\n\n"
        "=== CURVA NORMAL DE TALLES ===\n"
        f"{format_curva_talles(curva_talles)}"
    )
