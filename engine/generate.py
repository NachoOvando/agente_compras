"""Fase de generación: rag_answer orquesta retrieve → augment → generate."""

import numpy as np

from engine import config, context, prompts, retrieval
from engine.indexing import get_embeddings


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

    # AUGMENT: fichas recuperadas + BOM + stock actual + políticas (datos exactos)
    bom = context.load_bom()
    stock = context.load_stock(stock_overrides)
    politicas = context.load_politicas()
    full_context = context.build_context(retrieved, bom, stock, politicas)

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
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": [{"index": r["index"], "score": r["score"]} for r in retrieved],
    }
