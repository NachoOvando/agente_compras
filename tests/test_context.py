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
    curva_path = tmp_path / "curva_talles.json"

    bom = [
        {"codigo": "INS-001", "insumo": "Puntera de acero", "unidad": "par",
         "consumo_por_unidad": 1.0, "critico": True},
        {"codigo": "INS-006", "insumo": "Hilo", "unidad": "m",
         "consumo_por_unidad": 8, "critico": False},
    ]
    stock = {
        "fecha_actualizacion": "2026-07-12",
        "items": [
            {"codigo": "INS-001", "insumo": "Puntera de acero", "unidad": "par",
             "stock_actual": 150, "stock_minimo": 400},
        ],
    }
    politicas = [
        {"insumo": "Puntera de acero", "politica": "Revisión periódica (R,S)",
         "lead_time_dias": 15, "demanda_media_mensual": 850, "desvio_mensual": 40,
         "stock_seguridad": 100, "rop": 400, "stock_maximo": 900,
         "cobertura_ss_dias": 3.5},
    ]
    curva = {"talles": {"34": 10.0, "40": 50.0, "50": 40.0}}
    bom_path.write_text(json.dumps(bom), encoding="utf-8")
    stock_path.write_text(json.dumps(stock), encoding="utf-8")
    politicas_path.write_text(json.dumps(politicas), encoding="utf-8")
    curva_path.write_text(json.dumps(curva), encoding="utf-8")

    monkeypatch.setattr(config, "BOM_JSON_PATH", bom_path)
    monkeypatch.setattr(config, "STOCK_JSON_PATH", stock_path)
    monkeypatch.setattr(config, "POLITICAS_JSON_PATH", politicas_path)
    monkeypatch.setattr(config, "CURVA_TALLES_JSON_PATH", curva_path)
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_politicas.cache_clear()
    context.load_curva_talles.cache_clear()
    yield
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_politicas.cache_clear()
    context.load_curva_talles.cache_clear()


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
    assert politicas[0]["insumo"] == "Puntera de acero"
    assert politicas[0]["rop"] == 400


def test_politicas_faltante_da_error_claro(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "POLITICAS_JSON_PATH", tmp_path / "no_existe.json")
    context.load_politicas.cache_clear()
    with pytest.raises(FileNotFoundError, match="build_index"):
        context.load_politicas()


def test_load_curva_talles_devuelve_archivo():
    curva = context.load_curva_talles()
    assert curva["40"] == 50.0


def test_curva_talles_faltante_da_error_claro(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "CURVA_TALLES_JSON_PATH", tmp_path / "no_existe.json")
    context.load_curva_talles.cache_clear()
    with pytest.raises(FileNotFoundError, match="curva_talles"):
        context.load_curva_talles()


def test_format_curva_talles_marca_que_es_placeholder():
    out = context.format_curva_talles({"34": 10.0, "40": 50.0})
    assert "PLACEHOLDER" in out
    assert "T34=10.0%" in out
    assert "T40=50.0%" in out


def test_build_context_incluye_las_cinco_fuentes():
    retrieved = [{"index": 0, "score": 0.9, "chunk": "Ficha de la puntera de acero"}]
    ctx = context.build_context(
        retrieved, context.load_bom(), context.load_stock(), context.load_politicas(),
        context.load_curva_talles(),
    )
    assert "Ficha de la puntera de acero" in ctx
    assert "INS-001 | Puntera de acero | par | 1.0 | SI" in ctx
    assert "stock actual 150 par" in ctx
    assert "FICHAS DE PROVEEDORES" in ctx
    assert "BOM DEL PRODUCTO" in ctx
    assert "STOCK ACTUAL" in ctx
    assert "POLÍTICAS DE INVENTARIO" in ctx
    assert "400" in ctx  # ROP de la política de prueba
    assert "CURVA NORMAL DE TALLES" in ctx
    assert "T40=50.0%" in ctx


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
        {"codigo": "INS-001", "insumo": "Puntera de acero", "unidad": "par",
         "consumo_por_unidad": 1.0, "critico": True},
    ]
    out = context.format_bom(bom)
    assert "DETALLE POR TALLE" not in out


def test_format_bom_insumo_fijo_no_afectado_por_conviven_con_variable():
    bom = [
        {"codigo": "INS-001", "insumo": "Puntera de acero", "unidad": "par",
         "consumo_por_unidad": 1.0, "critico": True},
        {"codigo": "INS-002", "insumo": "Conjunto Sistema PU", "unidad": "g",
         "consumo_por_unidad": None, "critico": True,
         "consumo_por_talle": {"34": 369.167, "50": 587.167}},
    ]
    out = context.format_bom(bom)
    assert "INS-001 | Puntera de acero | par | 1.0 | SI" in out
