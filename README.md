# Asistente de Compras — Maincal S.A. (LLM + RAG)

Prototipo de tesis: asistente conversacional que recomienda prioridades de
compra de insumos críticos del producto **Cronos-N04**, respondiendo
**exclusivamente** con datos de la empresa (fichas de proveedores, BOM y stock
actual). Si el dato no está en ese "cerco de información", responde que no lo
tiene — nunca inventa.

Web app: **Next.js 15 + TypeScript + Tailwind** (frontend) y **FastAPI**
(motor RAG en Python), deployable como un único proyecto en **Vercel**.

## Arranque rápido

```bash
npm install
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
cp .env.example .env                                # completar OPENAI_API_KEY
.venv/Scripts/python scripts/build_index.py         # índice de embeddings
npm run dev                                         # UI en http://localhost:3000
```

Requiere que `data/source/` ya tenga las fichas de proveedores (PDF), la BOM
(export de SAP) y `stock.json` — ver [docs/customization.md](docs/customization.md).

Detalle completo en [docs/deployment.md](docs/deployment.md).

## Estructura

- `src/` — frontend Next.js (App Router): `src/app/`, `src/components/`, `src/lib/`.
- `api/index.py` — FastAPI (serverless en Vercel), solo routing.
- `engine/` — motor RAG: config, chunking, embeddings, retrieval, contexto, prompts, generación. Incluye CLI (`python -m engine.cli demo`).
- `shared/app-config.json` — producto y preguntas demo (fuente única para Python y frontend).
- `scripts/build_index.py` — build del índice (offline): fichas, BOM y políticas de inventario.
- `data/source/` — cerco de información (PDF de fichas, BOM export de SAP, stock.json, políticas de inventario).
- `data/index/` — índice precomputado (chunks + embeddings + BOM y políticas normalizadas).
- `tests/` — pytest del motor (sin llamadas a la API de OpenAI).
- `docs/` — [arquitectura](docs/architecture.md), [API](docs/api-reference.md), [deploy](docs/deployment.md), [personalización](docs/customization.md), [progreso](docs/progress.md).
- `CLAUDE.md` — contexto del proyecto para Claude Code (dónde editar RAG, API key, estado actual).

## Datos

Los datos son **reales de Maincal S.A.**: fichas de proveedores (PDF), BOM
(export de SAP) y políticas de inventario. `stock_actual` en `stock.json` es
el input manual/diario. Ver [docs/customization.md](docs/customization.md)
para el flujo de actualización.
