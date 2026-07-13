"""Tests de búsqueda semántica con embeddings sintéticos (sin API)."""

import numpy as np

from engine.retrieval import cosine_similarities, top_k_chunks


def test_cosine_identico_da_uno():
    v = np.array([1.0, 2.0, 3.0])
    matriz = np.array([[1.0, 2.0, 3.0], [-1.0, -2.0, -3.0]])
    sims = cosine_similarities(v, matriz)
    np.testing.assert_allclose(sims[0], 1.0)
    np.testing.assert_allclose(sims[1], -1.0)


def test_top_k_devuelve_los_mas_similares_en_orden():
    chunks = ("chunk sobre cuero", "chunk sobre suelas", "chunk sobre punteras")
    embeddings = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.9, 0.1, 0.0],  # casi paralelo al primero
    ])
    pregunta = np.array([1.0, 0.0, 0.0])

    resultados = top_k_chunks(pregunta, chunks, embeddings, k=2)

    assert len(resultados) == 2
    assert resultados[0]["chunk"] == "chunk sobre cuero"
    assert resultados[1]["chunk"] == "chunk sobre punteras"
    assert resultados[0]["score"] >= resultados[1]["score"]


def test_top_k_no_excede_cantidad_de_chunks():
    chunks = ("unico chunk",)
    embeddings = np.array([[1.0, 0.0]])
    resultados = top_k_chunks(np.array([1.0, 0.0]), chunks, embeddings, k=5)
    assert len(resultados) == 1


def test_cosine_vector_nulo_no_divide_por_cero():
    matriz = np.array([[0.0, 0.0], [1.0, 0.0]])
    sims = cosine_similarities(np.array([1.0, 0.0]), matriz)
    assert np.isfinite(sims).all()
