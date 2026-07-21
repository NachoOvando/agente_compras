"""Tests de rag_answer: la orquestación retrieve → augment → generate.

Sin llamadas reales a OpenAI: se inyecta un cliente fake por el parámetro
`client=` y se stubean el índice y los embeddings de la pregunta.
"""

import json

import numpy as np
import pytest

from engine import config, context, generate, retrieval


class FakeClient:
    """Cliente OpenAI falso: registra las llamadas y devuelve contenido fijo."""

    def __init__(self, answer="respuesta de prueba"):
        self.chat_calls = []
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.chat_calls.append(kwargs)

                class _Msg:
                    content = answer

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]

                return _Resp()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


@pytest.fixture(autouse=True)
def entorno_de_prueba(tmp_path, monkeypatch):
    """Índice fake, BOM y stock temporales; embeddings de pregunta stubeados."""
    # BOM, stock y políticas en archivos temporales (mismo patrón que test_context.py)
    bom_path = tmp_path / "bom.json"
    stock_path = tmp_path / "stock.json"
    politicas_path = tmp_path / "politicas.json"
    curva_path = tmp_path / "curva_talles.json"
    bom_path.write_text(json.dumps([
        {"codigo": "INS-001", "insumo": "Puntera de acero", "unidad": "par",
         "consumo_por_unidad": 1.0, "critico": True},
        {"codigo": "INS-002", "insumo": "Conjunto Sistema PU", "unidad": "g",
         "consumo_por_unidad": None, "critico": True,
         "consumo_por_talle": {"34": 369.167, "40": 478.167, "50": 587.167}},
    ]), encoding="utf-8")
    stock_path.write_text(json.dumps({
        "fecha_actualizacion": "2026-07-12",
        "items": [{"codigo": "INS-001", "insumo": "Puntera de acero", "unidad": "par",
                   "stock_actual": 150, "stock_minimo": 400}],
    }), encoding="utf-8")
    politicas_path.write_text(json.dumps([
        {"insumo": "Puntera de acero", "politica": "Revisión periódica (R,S)",
         "lead_time_dias": 15, "demanda_media_mensual": 850, "desvio_mensual": 40,
         "stock_seguridad": 100, "rop": 400, "stock_maximo": 900,
         "cobertura_ss_dias": 3.5},
    ]), encoding="utf-8")
    curva_path.write_text(json.dumps({
        "talles": {"34": 0.5, "40": 13.0, "50": 0.1},
    }), encoding="utf-8")
    monkeypatch.setattr(config, "BOM_JSON_PATH", bom_path)
    monkeypatch.setattr(config, "STOCK_JSON_PATH", stock_path)
    monkeypatch.setattr(config, "POLITICAS_JSON_PATH", politicas_path)
    monkeypatch.setattr(config, "CURVA_TALLES_JSON_PATH", curva_path)
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_politicas.cache_clear()
    context.load_curva_talles.cache_clear()

    # Índice fake: 3 chunks con embeddings ortogonales
    chunks = ("ficha de la puntera de acero", "ficha del sistema PU", "ficha de la caja de empaque")
    embeddings = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    monkeypatch.setattr(retrieval, "load_index", lambda: (chunks, embeddings))

    # La pregunta siempre se embebe como un vector alineado al primer chunk.
    # Se patchea el nombre importado en engine.generate (no engine.indexing).
    monkeypatch.setattr(generate, "get_embeddings",
                        lambda client, texts: np.array([[0.9, 0.1, 0.0]]))
    yield
    context.load_bom.cache_clear()
    context._load_stock_file.cache_clear()
    context.load_politicas.cache_clear()
    context.load_curva_talles.cache_clear()


def test_rag_answer_devuelve_answer_y_sources():
    client = FakeClient(answer="comprar puntera primero")
    resultado = generate.rag_answer("¿qué compro primero?", client=client)

    assert resultado["answer"] == "comprar puntera primero"
    assert len(resultado["sources"]) == config.TOP_K
    # sources expone index+score pero NO el texto del chunk
    assert set(resultado["sources"][0].keys()) == {"index", "score"}
    assert resultado["sources"][0]["index"] == 0  # el más similar


def test_rag_answer_pregunta_vacia_lanza_valueerror():
    client = FakeClient()
    with pytest.raises(ValueError):
        generate.rag_answer("   ", client=client)
    assert client.chat_calls == []  # nunca llegó a llamar al LLM


def test_rag_answer_respeta_k():
    client = FakeClient()
    resultado = generate.rag_answer("pregunta", k=1, client=client)
    assert len(resultado["sources"]) == 1


def test_rag_answer_construye_prompt_con_contexto_completo():
    client = FakeClient()
    generate.rag_answer("¿alcanza el stock?", client=client)

    [llamada] = client.chat_calls
    user_prompt = llamada["messages"][1]["content"]
    assert "ficha de la puntera de acero" in user_prompt  # chunk recuperado
    assert "INS-001 | Puntera de acero" in user_prompt    # BOM inyectada
    assert "stock actual 150 par" in user_prompt          # stock inyectado
    assert "¿alcanza el stock?" in user_prompt      # la pregunta
    assert llamada["model"] == config.CHAT_MODEL
    assert llamada["temperature"] == config.TEMPERATURE


def test_rag_answer_aplica_stock_overrides():
    client = FakeClient()
    generate.rag_answer("pregunta", stock_overrides={"INS-001": 999}, client=client)
    user_prompt = client.chat_calls[0]["messages"][1]["content"]
    assert "stock actual 999 par" in user_prompt


def test_rag_answer_bom_faltante_propaga_filenotfound(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "BOM_JSON_PATH", tmp_path / "no_existe.json")
    context.load_bom.cache_clear()
    with pytest.raises(FileNotFoundError, match="build_index"):
        generate.rag_answer("pregunta", client=FakeClient())


def test_rag_answer_incluye_detalle_por_talle_en_el_contexto():
    """Confirma que el detalle por talle llega al contexto que recibe el LLM.
    No prueba que el modelo elija la columna correcta (eso se verifica a
    mano con un cliente real, ver docs/customization.md)."""
    client = FakeClient()
    generate.rag_answer("¿cuánto sistema PU para talle 40?", client=client)
    user_prompt = client.chat_calls[0]["messages"][1]["content"]
    assert "DETALLE POR TALLE" in user_prompt
    assert "T40=478.167" in user_prompt


def test_rag_answer_incluye_curva_de_talles_en_el_contexto():
    """Confirma que la curva de talles llega al contexto. No prueba que el
    modelo pregunte antes de calcular (eso se verifica a mano, ver
    docs/customization.md)."""
    client = FakeClient()
    generate.rag_answer("¿alcanza el stock para producir 5000 pares?", client=client)
    user_prompt = client.chat_calls[0]["messages"][1]["content"]
    assert "CURVA NORMAL DE TALLES" in user_prompt
    assert "T40=13.0%" in user_prompt


def test_rag_answer_incluye_politicas_de_inventario_en_el_contexto():
    client = FakeClient()
    generate.rag_answer("¿por qué es prioritaria la puntera?", client=client)
    user_prompt = client.chat_calls[0]["messages"][1]["content"]
    assert "POLÍTICAS DE INVENTARIO" in user_prompt
    assert "Revisión periódica (R,S)" in user_prompt


def test_rag_answer_sin_historial_manda_solo_system_y_user():
    client = FakeClient()
    generate.rag_answer("pregunta", client=client)
    [llamada] = client.chat_calls
    assert len(llamada["messages"]) == 2
    assert llamada["messages"][0]["role"] == "system"
    assert llamada["messages"][1]["role"] == "user"


def test_rag_answer_antepone_el_historial_entre_system_y_la_pregunta_actual():
    client = FakeClient()
    historial = [
        {"role": "user", "content": "¿cuál es el proveedor de la puntera?"},
        {"role": "assistant", "content": "Flecksteel Ind. Art. Metálicos Ltda."},
    ]
    generate.rag_answer("¿y su lead time?", client=client, history=historial)

    [llamada] = client.chat_calls
    mensajes = llamada["messages"]
    assert len(mensajes) == 4
    assert mensajes[0]["role"] == "system"
    assert mensajes[1] == historial[0]
    assert mensajes[2] == historial[1]
    assert mensajes[3]["role"] == "user"
    assert "¿y su lead time?" in mensajes[3]["content"]
