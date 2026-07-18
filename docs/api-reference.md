# API Reference — Asistente de Compras

Base: FastAPI en `api/index.py`. En desarrollo corre en `http://127.0.0.1:8000`;
Next.js reescribe `/api/py/*` hacia ahí (ver `next.config.js`). En producción
(Vercel) la misma ruta llega a la serverless function.

Todas las respuestas siguen el contrato:
- Éxito: `{ "data": ... }`
- Error: `{ "error": "<mensaje legible>", "code": "<CODIGO>" }`

Sin autenticación (prototipo). Swagger UI disponible en `/api/py/docs`.

---

## GET /api/py/health

Sanity check del deploy.

```json
{ "data": { "status": "ok" } }
```

## GET /api/py/stock

Stock actual de los insumos críticos (desde `data/source/stock.json`).

```json
{
  "data": {
    "fecha_actualizacion": "2026-07-12",
    "items": [
      { "codigo": "INS-001", "insumo": "Conjunto Sistema PU", "unidad": "g",
        "stock_actual": 9800000, "stock_minimo": 13433330.0 }
    ]
  }
}
```

Errores: `500 STOCK_NOT_FOUND` si falta el archivo (ver `docs/customization.md`).

## POST /api/py/ask

Consulta al asistente RAG.

Request:
```json
{
  "question": "¿Qué insumo tengo que comprar primero?",
  "stockOverrides": { "INS-001": 500 }
}
```

- `question`: obligatoria, 1–1000 caracteres.
- `stockOverrides`: opcional; pisa el stock actual por código de insumo solo
  para esta consulta (simulación de escenarios).

Response:
```json
{
  "data": {
    "answer": "La prioridad de compra es el cuero vacuno...",
    "sources": [ { "index": 0, "score": 0.62 } ]
  }
}
```

`sources` identifica los chunks del índice usados como contexto (trazabilidad).

Errores:
- `400 INVALID_REQUEST`: pregunta vacía o `OPENAI_API_KEY` no configurada.
- `422` (FastAPI): body con formato inválido.
- `500 INDEX_NOT_FOUND`: índice no generado (correr `scripts/build_index.py`).
- `502 UPSTREAM_ERROR`: fallo al llamar a OpenAI (sin detalles internos hacia el cliente).
