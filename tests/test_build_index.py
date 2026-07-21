"""Tests del parser SAP → BOM normalizada (scripts/build_index.py:build_bom_json).

Usa DataFrames sintéticos chicos (rango de talles reducido a 3 vía monkeypatch
de config.TALLES) para no tener que escribir 17 filas por caso.
"""

import json

import pandas as pd
import pytest

from engine import config
from scripts import build_index


@pytest.fixture(autouse=True)
def talles_chicos(monkeypatch, tmp_path):
    """Reduce el rango de talles a 3 (DataFrames de prueba chicos) y redirige
    BOM_JSON_PATH a un archivo temporal — si no, build_bom_json() pisa el
    data/index/bom.json real del proyecto con datos sintéticos de test."""
    monkeypatch.setattr(config, "TALLES", ["34", "35", "36"])
    monkeypatch.setattr(config, "BOM_JSON_PATH", tmp_path / "bom.json")


def _fila(talla: str, componente: str, cantidad: float, um: str, tipo: str) -> dict:
    return {
        "Número de material": f"CRONOS, -N, 04, T. {talla}",
        "Componente de lista de materia": componente,
        "Cantidad": cantidad,
        "UM": um,
        "Tipo": tipo,
    }


def _escribir_bom(tmp_path, filas: list[dict]):
    path = tmp_path / "bom.xlsx"
    pd.DataFrame(filas).to_excel(path, index=False)
    return path


def _bom_generada() -> list[dict]:
    return json.loads(config.BOM_JSON_PATH.read_text(encoding="utf-8"))


def test_agrupa_familias_ignorando_sufijo_de_talle(tmp_path, monkeypatch):
    filas = [
        _fila(t, f"CAPELLADA CRONOS, -N, (NA), T. {t}", 1.0, "PAA", "No Critico")
        for t in ["34", "35", "36"]
    ]
    monkeypatch.setattr(config, "BOM_XLSX_PATH", _escribir_bom(tmp_path, filas))
    build_index.build_bom_json()

    bom = _bom_generada()
    assert len(bom) == 1
    assert bom[0]["insumo"] == "CAPELLADA CRONOS, -N, (NA)"
    assert bom[0]["consumo_por_unidad"] == 1.0
    assert bom[0]["consumo_por_talle"] is None
    assert bom[0]["critico"] is False


def test_fusiona_componentes_pu_criticos_con_suma_por_talle(tmp_path, monkeypatch):
    valores = {"34": (100.0, 200.0), "35": (110.0, 210.0), "36": (120.0, 220.0)}
    filas = []
    for t, (compacto, expanso) in valores.items():
        filas.append(_fila(t, "CONJ SISTEMA PU BGM COMPACTO", compacto, "G", "Critico"))
        filas.append(_fila(t, "CONJ SISTEMA PU BGM EXPANSO", expanso, "G", "Critico"))
    monkeypatch.setattr(config, "BOM_XLSX_PATH", _escribir_bom(tmp_path, filas))
    build_index.build_bom_json()

    [fila] = _bom_generada()
    assert fila["insumo"] == "Conjunto Sistema PU"
    assert fila["codigo"] == "INS-001"
    assert fila["critico"] is True
    assert fila["consumo_por_unidad"] is None
    assert fila["consumo_por_talle"] == {"34": 300.0, "35": 320.0, "36": 340.0}


def test_detecta_consumo_fijo_para_insumo_critico(tmp_path, monkeypatch):
    filas = [
        _fila(t, "PUNTERA ACERO 59 NORMAL T7", 1.0, "PAA", "Critico")
        for t in ["34", "35", "36"]
    ]
    monkeypatch.setattr(config, "BOM_XLSX_PATH", _escribir_bom(tmp_path, filas))
    build_index.build_bom_json()

    [fila] = _bom_generada()
    assert fila["insumo"] == "Puntera de acero"
    assert fila["codigo"] == "INS-002"
    assert fila["consumo_por_unidad"] == 1.0
    assert fila["consumo_por_talle"] is None


def test_critico_viene_de_columna_tipo(tmp_path, monkeypatch):
    filas = [
        _fila(t, "CAJA EMPAQUE BOTIN VORAN", 1.0, "UN", "Critico")
        for t in ["34", "35", "36"]
    ]
    monkeypatch.setattr(config, "BOM_XLSX_PATH", _escribir_bom(tmp_path, filas))
    build_index.build_bom_json()

    [fila] = _bom_generada()
    assert fila["insumo"] == "Caja de empaque"
    assert fila["critico"] is True
    assert fila["codigo"] == "INS-003"


def test_valueerror_si_faltan_columnas(tmp_path, monkeypatch):
    path = tmp_path / "bom.xlsx"
    pd.DataFrame([{"Número de material": "CRONOS T. 34"}]).to_excel(path, index=False)
    monkeypatch.setattr(config, "BOM_XLSX_PATH", path)
    with pytest.raises(ValueError, match="columnas esperadas"):
        build_index.build_bom_json()


def test_valueerror_si_consumo_variable_no_cubre_todos_los_talles(tmp_path, monkeypatch):
    filas = [
        _fila("34", "CONJ SISTEMA PU BGM COMPACTO", 100.0, "G", "Critico"),
        _fila("35", "CONJ SISTEMA PU BGM COMPACTO", 110.0, "G", "Critico"),
        # Falta talla 36: el consumo varía (100 != 110) y no cubre los 3 talles esperados.
    ]
    monkeypatch.setattr(config, "BOM_XLSX_PATH", _escribir_bom(tmp_path, filas))
    with pytest.raises(ValueError, match="no cubre todos los talles"):
        build_index.build_bom_json()


def test_valueerror_si_componente_critico_sin_mapeo_conocido(tmp_path, monkeypatch):
    filas = [
        _fila(t, "COMPONENTE MISTERIOSO", 1.0, "UN", "Critico")
        for t in ["34", "35", "36"]
    ]
    monkeypatch.setattr(config, "BOM_XLSX_PATH", _escribir_bom(tmp_path, filas))
    with pytest.raises(ValueError, match="no tiene mapeo a insumo conocido"):
        build_index.build_bom_json()


def test_valueerror_si_unidad_sap_desconocida(tmp_path, monkeypatch):
    filas = [
        _fila(t, f"CAPELLADA CRONOS, -N, (NA), T. {t}", 1.0, "XYZ", "No Critico")
        for t in ["34", "35", "36"]
    ]
    monkeypatch.setattr(config, "BOM_XLSX_PATH", _escribir_bom(tmp_path, filas))
    with pytest.raises(ValueError, match="Unidad de medida SAP desconocida"):
        build_index.build_bom_json()
