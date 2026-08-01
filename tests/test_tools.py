"""Tests de engine/tools.py: el cálculo de necesidad de insumos vive acá,
en Python — nunca en el LLM. Bug real que motivó esto: el modelo reutilizaba
un total ya calculado de un turno anterior y lo volvía a multiplicar
(1000 pares → 497 337 g → "× 1000" → 497 337 000 g, "no alcanza" cuando en
realidad sobraba). La herramienta siempre recalcula desde los datos.
"""

import json

import pytest

from engine import config, context, tools


@pytest.fixture(autouse=True)
def datos_de_prueba(tmp_path, monkeypatch):
    bom_path = tmp_path / "bom.json"
    stock_path = tmp_path / "stock.json"
    curva_path = tmp_path / "curva_talles.json"

    bom = [
        {"codigo": "INS-001", "insumo": "Conjunto Sistema PU", "unidad": "g",
         "consumo_por_unidad": None, "critico": True,
         "consumo_por_talle": {"34": 300.0, "40": 400.0, "50": 500.0}},
        {"codigo": "INS-002", "insumo": "Puntera de acero", "unidad": "par",
         "consumo_por_unidad": 1.0, "critico": True},
        {"codigo": "INS-003", "insumo": "Hilo", "unidad": "m",
         "consumo_por_unidad": 8, "critico": False},
    ]
    stock = {
        "fecha_actualizacion": "2026-07-12",
        "items": [
            {"codigo": "INS-001", "insumo": "Conjunto Sistema PU", "unidad": "g",
             "stock_actual": 500000, "stock_minimo": 100000},
            {"codigo": "INS-002", "insumo": "Puntera de acero", "unidad": "par",
             "stock_actual": 100, "stock_minimo": 400},
        ],
    }
    curva = {"talles": {"34": 10.0, "40": 50.0, "50": 40.0}}
    bom_path.write_text(json.dumps(bom), encoding="utf-8")
    stock_path.write_text(json.dumps(stock), encoding="utf-8")
    curva_path.write_text(json.dumps(curva), encoding="utf-8")

    monkeypatch.setattr(config, "BOM_JSON_PATH", bom_path)
    monkeypatch.setattr(config, "STOCK_JSON_PATH", stock_path)
    monkeypatch.setattr(config, "CURVA_TALLES_JSON_PATH", curva_path)
    monkeypatch.setattr(config, "TALLES", ["34", "40", "50"])
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_curva_talles.cache_clear()
    yield
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_curva_talles.cache_clear()


def test_sin_talle_ni_curva_pide_aclaracion_sin_ningun_numero():
    resultado = tools.calcular_necesidad_insumos(cantidad_pares=1000)
    assert resultado["necesita_aclaracion"] is True
    assert "Conjunto Sistema PU" in resultado["insumos_con_consumo_variable"]
    # No debe haber ningún cálculo mientras falta la aclaración.
    assert "insumos" not in resultado


def test_con_talle_puntual_calcula_con_el_valor_exacto_del_talle():
    resultado = tools.calcular_necesidad_insumos(cantidad_pares=200, talle="40")
    pu = next(i for i in resultado["insumos"] if i["insumo"] == "Conjunto Sistema PU")
    assert pu["consumo_por_par"] == 400.0
    assert pu["necesidad"] == 200 * 400.0
    assert pu["alcanza"] is True


def test_talle_con_prefijo_t_se_normaliza():
    resultado = tools.calcular_necesidad_insumos(cantidad_pares=200, talle="T40")
    pu = next(i for i in resultado["insumos"] if i["insumo"] == "Conjunto Sistema PU")
    assert pu["consumo_por_par"] == 400.0


def test_talle_fuera_de_rango_devuelve_error():
    resultado = tools.calcular_necesidad_insumos(cantidad_pares=200, talle="99")
    assert "error" in resultado
    assert "99" in resultado["error"]


def test_con_curva_normal_calcula_el_consumo_ponderado_no_el_total_anterior():
    """El caso exacto del bug real: la herramienta recalcula desde bom+curva,
    nunca reutiliza un número que el LLM haya dicho antes."""
    resultado = tools.calcular_necesidad_insumos(
        cantidad_pares=1000, aplicar_curva_normal=True
    )
    pu = next(i for i in resultado["insumos"] if i["insumo"] == "Conjunto Sistema PU")
    ponderado_esperado = 300.0 * 0.10 + 400.0 * 0.50 + 500.0 * 0.40  # 430.0
    assert pu["consumo_por_par"] == pytest.approx(ponderado_esperado)
    assert pu["necesidad"] == pytest.approx(1000 * ponderado_esperado)
    assert pu["necesidad"] != pytest.approx(1000 * 1000 * ponderado_esperado)


def test_insumo_de_consumo_fijo_no_depende_del_talle():
    resultado = tools.calcular_necesidad_insumos(cantidad_pares=200, talle="40")
    puntera = next(i for i in resultado["insumos"] if i["insumo"] == "Puntera de acero")
    assert puntera["consumo_por_par"] == 1.0
    assert puntera["necesidad"] == 200.0
    assert puntera["alcanza"] is False  # stock 100 < necesidad 200
    assert puntera["faltante"] == 100.0


def test_no_incluye_insumos_no_criticos():
    resultado = tools.calcular_necesidad_insumos(cantidad_pares=200, talle="40")
    nombres = [i["insumo"] for i in resultado["insumos"]]
    assert "Hilo" not in nombres


def test_stock_overrides_afectan_el_resultado():
    resultado = tools.calcular_necesidad_insumos(
        cantidad_pares=200, talle="40", stock_overrides={"INS-002": 999}
    )
    puntera = next(i for i in resultado["insumos"] if i["insumo"] == "Puntera de acero")
    assert puntera["stock_actual"] == 999
    assert puntera["alcanza"] is True


def test_cantidad_no_numerica_devuelve_error():
    resultado = tools.calcular_necesidad_insumos(cantidad_pares="muchos")
    assert "error" in resultado


def test_cantidad_negativa_o_cero_devuelve_error():
    assert "error" in tools.calcular_necesidad_insumos(cantidad_pares=0)
    assert "error" in tools.calcular_necesidad_insumos(cantidad_pares=-5)


def test_ejecutar_despacha_por_nombre():
    resultado = tools.ejecutar(
        tools.NOMBRE_CALCULAR, {"cantidad_pares": 200, "talle": "40"}
    )
    assert "insumos" in resultado


def test_ejecutar_herramienta_desconocida_devuelve_error_sin_lanzar():
    resultado = tools.ejecutar("otra_cosa", {})
    assert "error" in resultado
