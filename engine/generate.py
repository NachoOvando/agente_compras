"""Fase de generación: rag_answer orquesta retrieve → augment → generate."""

import json

import numpy as np

from engine import config, context, prompts, retrieval, tools
from engine.indexing import get_embeddings


def _tool_call_a_dict(tool_call) -> dict:
    """Serializa un tool_call de la respuesta del SDK de OpenAI a dict plano,
    para poder reenviarlo tal cual en el segundo mensaje 'assistant'."""
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.function.name,
            "arguments": tool_call.function.arguments,
        },
    }


def rag_answer(question: str, stock_overrides: dict[str, float] | None = None,
               k: int = config.TOP_K, client=None,
               history: list[dict[str, str]] | None = None) -> dict:
    """Responde una pregunta usando el cerco de información.

    Devuelve {"answer": str, "sources": [{"index", "score"}, ...]}.
    `client` es inyectable para tests; por defecto se crea el cliente real.
    `history` es una lista opcional de turnos previos {"role": "user"|
    "assistant", "content": str} — solo pregunta y respuesta, nunca el
    contexto armado — que se antepone a la pregunta actual para que el
    modelo entienda repreguntas ("¿y cuál es su proveedor?").
    """
    if not question or not question.strip():
        raise ValueError("La pregunta no puede estar vacía.")

    if client is None:
        client = config.get_openai_client()

    # RETRIEVE: embeddings de la pregunta vs. índice precomputado de fichas
    chunks, chunk_embeddings = retrieval.load_index()
    question_embedding = get_embeddings(client, [question])[0]
    retrieved = retrieval.top_k_chunks(
        np.asarray(question_embedding), chunks, chunk_embeddings, k=k
    )

    # AUGMENT: fichas recuperadas + BOM + stock + políticas + curva de talles
    # + contexto de negocio
    bom = context.load_bom()
    stock = context.load_stock(stock_overrides)
    politicas = context.load_politicas()
    curva_talles = context.load_curva_talles()
    contexto_negocio = context.load_contexto_negocio()
    full_context = context.build_context(
        retrieved, bom, stock, politicas, curva_talles, contexto_negocio
    )

    # GENERATE
    messages = [{"role": "system", "content": prompts.SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append(
        {"role": "user", "content": prompts.build_user_prompt(question, full_context)}
    )

    response = client.chat.completions.create(
        model=config.CHAT_MODEL,
        messages=messages,
        temperature=config.TEMPERATURE,
        max_tokens=config.MAX_TOKENS,
        tools=tools.TOOLS_SPEC,
    )
    message = response.choices[0].message

    # Si el modelo pidió calcular, la aritmética la hace engine/tools.py (no
    # el LLM) y se le devuelve el resultado exacto para que solo lo redacte.
    # Una sola ronda: no hay loop de tool calls encadenados.
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [_tool_call_a_dict(tc) for tc in tool_calls],
        })
        for tool_call in tool_calls:
            argumentos = json.loads(tool_call.function.arguments or "{}")
            resultado = tools.ejecutar(
                tool_call.function.name, argumentos, stock_overrides=stock_overrides
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(resultado, ensure_ascii=False),
            })

        response = client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=messages,
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
        )
        message = response.choices[0].message

    return {
        "answer": message.content,
        "sources": [{"index": r["index"], "score": r["score"]} for r in retrieved],
    }
