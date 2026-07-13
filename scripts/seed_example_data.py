"""Genera los datos de ejemplo del cerco de información (ficticios).

Crea:
- data/source/bom_cronos_n04.xlsx  (BOM completa del producto, salida simulada de ERP)
- data/source/stock.json           (stock actual de los insumos críticos)

Las fichas de proveedores (datos_maincal_EJEMPLO.pdf) ya existen y se copian aparte.
Correr desde la raíz del proyecto: python scripts/seed_example_data.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openpyxl import Workbook

from engine import config

# BOM del Cronos-N04: consumo por par producido. Los 3 primeros son los
# insumos críticos (coinciden con las fichas del PDF); el resto son no
# críticos y por diseño NO tienen ficha ni stock en el cerco.
BOM_CRONOS_N04 = [
    ("INS-001", "Cuero vacuno", "m2", 0.19, "SI"),
    ("INS-002", "Suela de poliuretano (PU)", "par", 1, "SI"),
    ("INS-003", "Puntera de acero", "par", 1, "SI"),
    ("INS-004", "Plantilla anatómica", "par", 1, "NO"),
    ("INS-005", "Cordones 120 cm", "par", 1, "NO"),
    ("INS-006", "Hilo de coser poliéster", "m", 8, "NO"),
    ("INS-007", "Ojalillos metálicos", "unidad", 12, "NO"),
    ("INS-008", "Adhesivo de poliuretano", "kg", 0.03, "NO"),
    ("INS-009", "Forro interior textil", "m2", 0.12, "NO"),
    ("INS-010", "Etiqueta y caja individual", "unidad", 1, "NO"),
]

# Stock actual: coherente con las fichas del PDF de ejemplo.
STOCK = {
    "fecha_actualizacion": "2026-07-12",
    "items": [
        {"codigo": "INS-001", "insumo": "Cuero vacuno", "unidad": "m2",
         "stock_actual": 150, "stock_minimo": 400},
        {"codigo": "INS-002", "insumo": "Suela de poliuretano (PU)", "unidad": "par",
         "stock_actual": 3200, "stock_minimo": 1500},
        {"codigo": "INS-003", "insumo": "Puntera de acero", "unidad": "par",
         "stock_actual": 6000, "stock_minimo": 4000},
    ],
}


def crear_bom_xlsx() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = f"BOM {config.PRODUCTO}"
    ws.append(["codigo", "insumo", "unidad", "consumo_por_unidad", "critico"])
    for fila in BOM_CRONOS_N04:
        ws.append(list(fila))
    config.BOM_XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(config.BOM_XLSX_PATH)
    print(f"BOM generada: {config.BOM_XLSX_PATH}")


def crear_stock_json() -> None:
    config.STOCK_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.STOCK_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(STOCK, f, ensure_ascii=False, indent=2)
    print(f"Stock generado: {config.STOCK_JSON_PATH}")


if __name__ == "__main__":
    crear_bom_xlsx()
    crear_stock_json()
