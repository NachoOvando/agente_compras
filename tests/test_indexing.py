"""Tests de chunking y lectura de PDF (fase de preparación)."""

import pytest

from engine.indexing import read_pdf_pages, split_pages_into_chunks, split_text_chunks


class _FakePage:
    def __init__(self, texto):
        self._texto = texto

    def extract_text(self):
        return self._texto


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


def test_read_pdf_pages_devuelve_una_entrada_por_pagina_no_vacia(tmp_path, monkeypatch):
    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"contenido irrelevante, PdfReader esta mockeado")

    class _FakeReader:
        def __init__(self, path):
            self.pages = [_FakePage("Ficha A"), _FakePage(""), _FakePage("Ficha B")]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    paginas = read_pdf_pages(pdf_path)
    assert paginas == ["Ficha A", "Ficha B"]  # la página vacía se descarta


def test_read_pdf_pages_archivo_inexistente_da_error_claro(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_pdf_pages(tmp_path / "no_existe.pdf")


def test_read_pdf_pages_sin_texto_extraible(tmp_path, monkeypatch):
    pdf_path = tmp_path / "fake.pdf"
    pdf_path.write_bytes(b"contenido irrelevante")

    class _FakeReader:
        def __init__(self, path):
            self.pages = [_FakePage(None), _FakePage("")]

    monkeypatch.setattr("pypdf.PdfReader", _FakeReader)
    with pytest.raises(ValueError):
        read_pdf_pages(pdf_path)


def test_split_pages_into_chunks_una_ficha_por_chunk():
    paginas = ["Ficha corta A", "Ficha corta B"]
    chunks = split_pages_into_chunks(paginas, chunk_size=1500, overlap=300)
    assert chunks == paginas


def test_split_pages_into_chunks_subdivide_pagina_mas_larga_que_chunk_size():
    pagina_larga = "x" * 1000
    chunks = split_pages_into_chunks([pagina_larga], chunk_size=300, overlap=50)
    assert len(chunks) == 4  # mismo cálculo que test_chunking_respeta_tamano_y_overlap
    assert all(len(c) <= 300 for c in chunks)
