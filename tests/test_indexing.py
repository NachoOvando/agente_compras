"""Tests de chunking y lectura de PDF (fase de preparación)."""

import pytest

from engine.indexing import split_text_chunks


def test_chunking_cubre_todo_el_texto():
    texto = "abcdefghij" * 100  # 1000 caracteres
    chunks = split_text_chunks(texto, chunk_size=300, overlap=50)
    # El primer chunk arranca al inicio y el último llega al final del texto
    assert chunks[0].startswith("abcdefghij")
    assert texto.endswith(chunks[-1][-10:])


def test_chunking_respeta_tamano_y_overlap():
    texto = "x" * 1000
    chunks = split_text_chunks(texto, chunk_size=300, overlap=50)
    assert all(len(c) <= 300 for c in chunks)
    # Con overlap 50, cada chunk avanza 250 caracteres: ceil((1000-300)/250)+1 = 4
    assert len(chunks) == 4


def test_chunking_texto_corto_devuelve_un_chunk():
    chunks = split_text_chunks("texto corto", chunk_size=1500, overlap=300)
    assert chunks == ["texto corto"]


def test_chunking_valida_parametros():
    with pytest.raises(ValueError):
        split_text_chunks("texto", chunk_size=0, overlap=0)
    with pytest.raises(ValueError):
        split_text_chunks("texto", chunk_size=100, overlap=100)
