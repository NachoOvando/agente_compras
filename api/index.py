"""API del asistente de compras (FastAPI).

Capa fina de routing: valida entrada, delega al motor (engine/) y aplica
el contrato de respuesta { data } / { error, code }. Sin lógica de negocio.

En Vercel corre como serverless function Python; en desarrollo se levanta
con: python -m uvicorn api.index:app --reload --port 8000
"""

import logging
import sys
from pathlib import Path
from typing import Literal

# La raíz del proyecto tiene que estar en el path para importar engine/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engine import config as engine_config
from engine import context as engine_context
from engine.generate import rag_answer

app = FastAPI(
    title="Asistente de Compras",
    docs_url="/api/py/docs",
    openapi_url="/api/py/openapi.json",
)


class HistoryTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    stockOverrides: dict[str, float] | None = None
    history: list[HistoryTurn] | None = Field(
        default=None, max_length=engine_config.MAX_HISTORY_TURNS * 2
    )


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message, "code": code})


@app.get("/api/py/health")
def health():
    return {"data": {"status": "ok"}}


@app.get("/api/py/stock")
def get_stock():
    try:
        stock = engine_context.load_stock()
    except FileNotFoundError as exc:
        logger.warning("Stock no encontrado: %s", exc)
        return _error(500, "STOCK_NOT_FOUND", str(exc))
    return {"data": stock}


@app.post("/api/py/ask")
def ask(body: AskRequest):
    try:
        history = (
            [{"role": h.role, "content": h.content} for h in body.history]
            if body.history else None
        )
        result = rag_answer(
            body.question, stock_overrides=body.stockOverrides, history=history
        )
    except FileNotFoundError as exc:
        # Índice o datos del cerco no generados todavía
        logger.warning("Índice/datos no encontrados: %s", exc)
        return _error(500, "INDEX_NOT_FOUND", str(exc))
    except ValueError as exc:
        # API key faltante o pregunta inválida
        logger.warning("Solicitud inválida: %s", exc)
        return _error(400, "INVALID_REQUEST", str(exc))
    except Exception:
        # Traceback completo a los logs del server (Vercel); al cliente solo
        # el mensaje genérico — sin stack traces (regla de seguridad).
        logger.exception("Error no controlado al generar respuesta RAG")
        return _error(502, "UPSTREAM_ERROR",
                      "No se pudo generar la respuesta. Intentá de nuevo.")
    return {"data": result}
