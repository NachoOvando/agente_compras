"""Genera los datos de ejemplo del cerco de información (ficticios).

Crea:
- data/source/bom_cronos_n04.xlsx      (BOM completa del producto, salida simulada de ERP)
- data/source/stock.json               (stock actual de los insumos críticos)
- data/source/politicas_inventario.xlsx (políticas de inventario de los insumos críticos)

Las fichas de proveedores (datos_maincal_EJEMPLO.pdf) ya existen y se copian aparte.

ATENCIÓN: si esos archivos ya existen (por ejemplo porque se cargaron datos
reales de Maincal) este script NO los pisa a menos que se pase --force —
para no destruir por accidente el cerco de información real.

Correr desde la raíz del proyecto: python scripts/seed_example_data.py [--force]
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import Workbook

from engine import config

# BOM del Cronos-N04: consumo por par producido. Los 3 primeros son los
# insumos críticos (coinciden con las fichas del PDF y con las políticas de
# inventario); el resto son no críticos y por diseño NO tienen ficha ni
# stock en el cerco. La suela de poliuretano varía por talle (T34..T50) —
# se incluye un ejemplo sintético para ejercitar ese código sin depender de
# la BOM real de Maincal.
TALLES = config.TALLES
_SUELA_PU_POR_TALLE = {t: round(3.5 + i * 0.15, 2) for i, t in enumerate(TALLES)}

BOM_CRONOS_N04 = [
    # codigo, insumo, unidad, consumo_por_unidad, critico, consumo_por_talle
    ("INS-001", "Suela de poliuretano (PU)", "par", None, "SI", _SUELA_PU_POR_TALLE),
    ("INS-002", "Puntera de acero", "par", 1, "SI", None),
    ("INS-003", "Caja de empaque", "unidad", 1, "SI", None),
    ("INS-004", "Capellada", "par", 1, "NO", None),
    ("INS-005", "Plantilla anatómica", "par", 1, "NO", None),
    ("INS-006", "Cordones 120 cm", "par", 1, "NO", None),
    ("INS-007", "Hilo de coser poliéster", "m", 8, "NO", None),
    ("INS-008", "Ojalillos metálicos", "unidad", 12, "NO", None),
]

# Stock actual: coherente con las fichas del PDF de ejemplo. stock_minimo
# coincide con el ROP/nivel objetivo de POLITICAS_INVENTARIO de abajo.
STOCK = {
    "fecha_actualizacion": "2026-07-12",
    "items": [
        {"codigo": "INS-001", "insumo": "Suela de poliuretano (PU)", "unidad": "par",
         "stock_actual": 1200, "stock_minimo": 1500},
        {"codigo": "INS-002", "insumo": "Puntera de acero", "unidad": "par",
         "stock_actual": 6000, "stock_minimo": 4000},
        {"codigo": "INS-003", "insumo": "Caja de empaque", "unidad": "unidad",
         "stock_actual": 2500, "stock_minimo": 3000},
    ],
}

# Políticas de inventario de ejemplo (mismas columnas que el archivo real
# de Maincal: revisión continua/periódica, lead time, demanda, stock de
# seguridad, ROP/nivel objetivo, stock máximo, cobertura).
POLITICAS_INVENTARIO = [
    ("Suela de poliuretano (PU)", "Revisión continua (s,Q)", 45, 4500, 180, 350, 1500, 2600, 3.1),
    ("Puntera de acero", "Revisión periódica (R,S)", 40, 4500, 150, 480, 4000, 6200, 3.2),
    ("Caja de empaque", "Revisión periódica (R,S)", 30, 4500, 150, 440, 3000, 4800, 3.0),
]


def _confirmar_o_salir(path: Path, force: bool) -> bool:
    if path.exists() and not force:
        print(f"Aviso: '{path}' ya existe y no se pisa (pasá --force para sobrescribir).")
        return False
    return True


def crear_bom_xlsx(force: bool = False) -> None:
    if not _confirmar_o_salir(config.BOM_XLSX_PATH, force):
        return
    wb = Workbook()
    ws = wb.active
    ws.title = f"BOM {config.PRODUCTO}"
    ws.append(["codigo", "insumo", "unidad", "consumo_por_unidad", "critico"]
              + [f"T{t}" for t in TALLES])
    for codigo, insumo, unidad, consumo, critico, por_talle in BOM_CRONOS_N04:
        fila = [codigo, insumo, unidad, consumo, critico]
        fila += [por_talle[t] for t in TALLES] if por_talle else [None] * len(TALLES)
        ws.append(fila)
    config.BOM_XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(config.BOM_XLSX_PATH)
    print(f"BOM generada: {config.BOM_XLSX_PATH}")


def crear_stock_json(force: bool = False) -> None:
    if not _confirmar_o_salir(config.STOCK_JSON_PATH, force):
        return
    config.STOCK_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.STOCK_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(STOCK, f, ensure_ascii=False, indent=2)
    print(f"Stock generado: {config.STOCK_JSON_PATH}")


def crear_politicas_xlsx(force: bool = False) -> None:
    if not _confirmar_o_salir(config.POLITICAS_XLSX_PATH, force):
        return
    wb = Workbook()
    ws = wb.active
    ws.title = "Politicas"
    ws.append(["Familia", "UM", "Política", "Lead_Time_dias", "Demanda_media_mensual",
               "Desvio_mensual", "Stock_Seguridad", "ROP_o_Nivel_Objetivo",
               "Stock_Maximo", "Cobertura_SS_dias"])
    # "Familia" acá usa el mismo nombre de insumo (no hay un nombre SAP
    # distinto en el dato de ejemplo) — ver FAMILIA_A_INSUMO en build_index.py
    # para el mapeo real de nombres SAP → insumo.
    for insumo, politica, lt, demanda, desvio, ss, rop, smax, cob in POLITICAS_INVENTARIO:
        ws.append([insumo, "par/unidad", politica, lt, demanda, desvio, ss, rop, smax, cob])
    config.POLITICAS_XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(config.POLITICAS_XLSX_PATH)
    print(f"Políticas de inventario generadas: {config.POLITICAS_XLSX_PATH}")


if __name__ == "__main__":
    force = "--force" in sys.argv
    crear_bom_xlsx(force)
    crear_stock_json(force)
    crear_politicas_xlsx(force)
