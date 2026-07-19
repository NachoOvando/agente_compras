"""Tests de los endpoints FastAPI: contrato {data}/{error, code} y mapeo de errores.

El motor se stubea en el namespace de api.index (donde están los nombres
importados); no hay llamadas a OpenAI ni dependencia del índice real.
"""

import pytest
from fastapi.testclient import TestClient

import api.index as api_index

client = TestClient(api_index.app)


def test_health_devuelve_status_ok():
    r = client.get("/api/py/health")
    assert r.status_code == 200
    assert r.json() == {"data": {"status": "ok"}}


def test_stock_devuelve_data_con_items(monkeypatch):
    stock_fake = {"fecha_actualizacion": "2026-07-12", "items": [{"codigo": "INS-001"}]}
    monkeypatch.setattr(api_index.engine_context, "load_stock", lambda: stock_fake)
    r = client.get("/api/py/stock")
    assert r.status_code == 200
    assert r.json() == {"data": stock_fake}


def test_stock_no_encontrado_da_500_con_codigo(monkeypatch):
    def falla():
        raise FileNotFoundError("falta stock.json")
    monkeypatch.setattr(api_index.engine_context, "load_stock", falla)
    r = client.get("/api/py/stock")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "STOCK_NOT_FOUND"
    assert "error" in body


def test_ask_devuelve_answer_y_sources(monkeypatch):
    resultado = {"answer": "comprar puntera", "sources": [{"index": 0, "score": 0.9}]}
    monkeypatch.setattr(api_index, "rag_answer",
                        lambda q, stock_overrides=None, history=None: resultado)
    r = client.post("/api/py/ask", json={"question": "¿qué compro?"})
    assert r.status_code == 200
    assert r.json() == {"data": resultado}


def test_ask_pasa_stock_overrides(monkeypatch):
    capturado = {}

    def fake(q, stock_overrides=None, history=None):
        capturado["overrides"] = stock_overrides
        return {"answer": "ok", "sources": []}

    monkeypatch.setattr(api_index, "rag_answer", fake)
    client.post("/api/py/ask",
                json={"question": "p", "stockOverrides": {"INS-001": 500}})
    assert capturado["overrides"] == {"INS-001": 500}


def test_ask_pasa_historial(monkeypatch):
    capturado = {}

    def fake(q, stock_overrides=None, history=None):
        capturado["history"] = history
        return {"answer": "ok", "sources": []}

    monkeypatch.setattr(api_index, "rag_answer", fake)
    client.post("/api/py/ask", json={
        "question": "p",
        "history": [
            {"role": "user", "content": "hola"},
            {"role": "assistant", "content": "hola!"},
        ],
    })
    assert capturado["history"] == [
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "hola!"},
    ]


def test_ask_sin_historial_pasa_none(monkeypatch):
    capturado = {}

    def fake(q, stock_overrides=None, history=None):
        capturado["history"] = history
        return {"answer": "ok", "sources": []}

    monkeypatch.setattr(api_index, "rag_answer", fake)
    client.post("/api/py/ask", json={"question": "p"})
    assert capturado["history"] is None


def test_ask_historial_con_rol_invalido_da_422(monkeypatch):
    monkeypatch.setattr(
        api_index, "rag_answer",
        lambda q, stock_overrides=None, history=None: {"answer": "ok", "sources": []},
    )
    r = client.post("/api/py/ask", json={
        "question": "p",
        "history": [{"role": "system", "content": "hola"}],
    })
    assert r.status_code == 422


def test_ask_historial_mas_largo_que_el_tope_da_422(monkeypatch):
    monkeypatch.setattr(
        api_index, "rag_answer",
        lambda q, stock_overrides=None, history=None: {"answer": "ok", "sources": []},
    )
    historial_largo = [{"role": "user", "content": "x"}] * (api_index.engine_config.MAX_HISTORY_TURNS * 2 + 1)
    r = client.post("/api/py/ask", json={"question": "p", "history": historial_largo})
    assert r.status_code == 422


def test_ask_pregunta_vacia_da_422():
    r = client.post("/api/py/ask", json={"question": ""})
    assert r.status_code == 422  # validación Pydantic (min_length=1)


@pytest.mark.parametrize("excepcion,status,code", [
    (FileNotFoundError("falta el índice, corré build_index"), 500, "INDEX_NOT_FOUND"),
    (ValueError("falta OPENAI_API_KEY"), 400, "INVALID_REQUEST"),
])
def test_ask_mapea_errores_conocidos(monkeypatch, excepcion, status, code):
    def falla(q, stock_overrides=None, history=None):
        raise excepcion
    monkeypatch.setattr(api_index, "rag_answer", falla)
    r = client.post("/api/py/ask", json={"question": "pregunta"})
    assert r.status_code == status
    assert r.json()["code"] == code


def test_ask_error_inesperado_da_502_sin_filtrar_detalles(monkeypatch):
    def falla(q, stock_overrides=None, history=None):
        raise RuntimeError("detalle-interno-secreto-xyz")
    monkeypatch.setattr(api_index, "rag_answer", falla)
    r = client.post("/api/py/ask", json={"question": "pregunta"})
    assert r.status_code == 502
    body = r.json()
    assert body["code"] == "UPSTREAM_ERROR"
    # El mensaje interno NUNCA llega al cliente (regla de seguridad)
    assert "detalle-interno-secreto-xyz" not in str(body)
