"""Tests del armado de contexto: BOM (fija y variable por talle) + stock + políticas."""

import json

import pytest

from engine import config, context


@pytest.fixture(autouse=True)
def datos_de_prueba(tmp_path, monkeypatch):
    """Apunta el engine a archivos temporales y limpia los caches lru."""
    bom_path = tmp_path / "bom.json"
    stock_path = tmp_path / "stock.json"
    politicas_path = tmp_path / "politicas.json"

    bom = [
        {"codigo": "INS-001", "insumo": "Cuero vacuno", "unidad": "m2",
         "consumo_por_unidad": 0.19, "critico": True},
        {"codigo": "INS-006", "insumo": "Hilo", "unidad": "m",
         "consumo_por_unidad": 8, "critico": False},
    ]
    stock = {
        "fecha_actualizacion": "2026-07-12",
        "items": [
            {"codigo": "INS-001", "insumo": "Cuero vacuno", "unidad": "m2",
             "stock_actual": 150, "stock_minimo": 400},
        ],
    }
    politicas = [
        {"insumo": "Cuero vacuno", "politica": "Revisión periódica (R,S)",
         "lead_time_dias": 15, "demanda_media_mensual": 850, "desvio_mensual": 40,
         "stock_seguridad": 100, "rop": 400, "stock_maximo": 900,
         "cobertura_ss_dias": 3.5},
    ]
    bom_path.write_text(json.dumps(bom), encoding="utf-8")
    stock_path.write_text(json.dumps(stock), encoding="utf-8")
    politicas_path.write_text(json.dumps(politicas), encoding="utf-8")

    monkeypatch.setattr(config, "BOM_JSON_PATH", bom_path)
    monkeypatch.setattr(config, "STOCK_JSON_PATH", stock_path)
    monkeypatch.setattr(config, "POLITICAS_JSON_PATH", politicas_path)
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_politicas.cache_clear()
    yield
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_politicas.cache_clear()


def test_load_stock_sin_overrides_devuelve_archivo():
    stock = context.load_stock()
    assert stock["items"][0]["stock_actual"] == 150


def test_load_stock_con_override_pisa_el_valor():
    stock = context.load_stock({"INS-001": 999})
    assert stock["items"][0]["stock_actual"] == 999
    # El archivo original (cacheado) no se modifica
    assert context.load_stock()["items"][0]["stock_actual"] == 150


def test_override_de_codigo_inexistente_se_ignora():
    stock = context.load_stock({"INS-999": 5})
    assert stock["items"][0]["stock_actual"] == 150


def test_load_politicas_devuelve_archivo():
    politicas = context.load_politicas()
    assert politicas[0]["insumo"] == "Cuero vacuno"
    assert politicas[0]["rop"] == 400


def test_politicas_faltante_da_error_claro(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "POLITICAS_JSON_PATH", tmp_path / "no_existe.json")
    context.load_politicas.cache_clear()
    with pytest.raises(FileNotFoundError, match="build_index"):
        context.load_politicas()


def test_build_context_incluye_las_cuatro_fuentes():
    retrieved = [{"index": 0, "score": 0.9, "chunk": "Ficha del cuero vacuno"}]
    ctx = context.build_context(
        retrieved, context.load_bom(), context.load_stock(), context.load_politicas()
    )
    assert "Ficha del cuero vacuno" in ctx
    assert "INS-001 | Cuero vacuno | m2 | 0.19 | SI" in ctx
    assert "stock actual 150 m2" in ctx
    assert "FICHAS DE PROVEEDORES" in ctx
    assert "BOM DEL PRODUCTO" in ctx
    assert "STOCK ACTUAL" in ctx
    assert "POLÍTICAS DE INVENTARIO" in ctx
    assert "400" in ctx  # ROP de la política de prueba


def test_bom_faltante_da_error_claro(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "BOM_JSON_PATH", tmp_path / "no_existe.json")
    context.load_bom.cache_clear()
    with pytest.raises(FileNotFoundError, match="build_index"):
        context.load_bom()


def test_format_bom_insumo_talle_dependiente_muestra_detalle():
    bom = [
        {"codigo": "INS-002", "insumo": "Conjunto Sistema PU", "unidad": "g",
         "consumo_por_unidad": None, "critico": True,
         "consumo_por_talle": {"34": 369.167, "40": 478.167, "50": 587.167}},
    ]
    out = context.format_bom(bom)
    assert "variable por talle (ver detalle abajo)" in out
    assert "DETALLE POR TALLE" in out
    assert "T34=369.167" in out
    assert "T50=587.167" in out


def test_format_bom_sin_insumos_talle_dependientes_no_muestra_detalle():
    bom = [
        {"codigo": "INS-001", "insumo": "Cuero vacuno", "unidad": "m2",
         "consumo_por_unidad": 0.19, "critico": True},
    ]
    out = context.format_bom(bom)
    assert "DETALLE POR TALLE" not in out


def test_format_bom_insumo_fijo_no_afectado_por_conviven_con_variable():
    bom = [
        {"codigo": "INS-001", "insumo": "Cuero vacuno", "unidad": "m2",
         "consumo_por_unidad": 0.19, "critico": True},
        {"codigo": "INS-002", "insumo": "Conjunto Sistema PU", "unidad": "g",
         "consumo_por_unidad": None, "critico": True,
         "consumo_por_talle": {"34": 369.167, "50": 587.167}},
    ]
    out = context.format_bom(bom)
    assert "INS-001 | Cuero vacuno | m2 | 0.19 | SI" in out
