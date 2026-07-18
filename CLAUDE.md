# CLAUDE.md — Asistente de Compras Maincal

Contexto del proyecto para Claude Code. Complementa (no reemplaza) las
convenciones globales de `~/.claude/CLAUDE.md` — en caso de conflicto, este
archivo tiene precedencia por ser específico del repo.

## Qué es

Prototipo de tesis: asistente conversacional (LLM + RAG) que recomienda
prioridades de compra de insumos críticos del producto **Cronos-N04** para
Maincal S.A., respondiendo **exclusivamente** con datos de la empresa (el
"cerco de información"). Si el dato no está ahí, dice que no lo tiene — nunca
inventa. Spec original en la carpeta de la tesis (ver "Material fuente" abajo).

## Stack

Next.js 15 (App Router, React 19) + TypeScript + Tailwind (frontend) + FastAPI
(Python, motor RAG), un solo proyecto deployable en Vercel. Sin base de datos —
el cerco de información son archivos (PDF + Excel + JSON), ver
`docs/architecture.md` para la justificación.

## Estructura relevante

```
engine/          motor RAG (lógica de negocio, testeable sin servidor)
api/index.py     FastAPI — solo routing, delega a engine/
shared/          app-config.json: producto y preguntas demo (fuente única Python+TS)
scripts/         build_index.py (indexar), seed_example_data.py (datos de ejemplo)
data/source/     cerco de información: PDF fichas, BOM.xlsx, stock.json, politicas_inventario.xlsx
data/index/      índice generado (chunks/embeddings/bom.json/politicas.json) — no editar a mano
src/             frontend Next.js: src/app/, src/components/, src/lib/
tests/           pytest del motor
docs/            architecture.md, api-reference.md, deployment.md, customization.md
.claude/skills/  skill ui-ux-pro-max (diseño) instalado — ver docs/architecture.md
```

## Dónde editar (detalle completo en `docs/customization.md`)

- **API key de OpenAI**: `.env` (local, nunca commitear) / Environment Variables en Vercel (producción). Se lee en `engine/config.py`.
- **Nombre del producto / preguntas de ejemplo**: `shared/app-config.json` (fuente única para Python y frontend — no editar en `engine/config.py` ni en componentes).
- **System prompt / reglas del cerco**: `engine/prompts.py`.
- **Modelos, TOP_K, temperature, chunk size**: `engine/config.py`.
- **Armado de contexto (BOM + stock + fichas + políticas de inventario)**: `engine/context.py`.
- **Insumos críticos actuales**: Suela de poliuretano (PU) — consumo variable por talle (T34–T50) —, Puntera de acero y Caja de empaque (`data/source/politicas_inventario.xlsx`, mapeo de nombres SAP en `FAMILIA_A_INSUMO` de `scripts/build_index.py`).
- **Búsqueda semántica**: `engine/retrieval.py`.
- Cambiar el PDF, la BOM o `CHUNK_SIZE`/modelo de embeddings requiere re-indexar: `python scripts/build_index.py`.

Dependencias Python: `requirements.txt` = runtime de la serverless function
(lo único que Vercel instala); `requirements-dev.txt` = local (scripts + tests).

## Comandos

```bash
npm run dev                                  # Next.js (:3000) + FastAPI (:8000) juntos
npm run next-dev / npm run fastapi-dev        # por separado
.venv/Scripts/python -m pytest                # tests del motor y de la API
npm run lint && npm run typecheck             # antes de cerrar cualquier tarea
.venv/Scripts/python scripts/build_index.py   # regenerar índice de embeddings
.venv/Scripts/python -m engine.cli demo       # probar el asistente por consola
```

## Material fuente de la tesis

Spec original, notebooks previos y capítulos de la tesis (fuera de este repo):
`C:\Users\nacho\OneDrive\Escritorio\Facultad\Proyecto Final - Guaita Ovando\Proyecto Final\Compras\`
En particular `SPEC_asistente_compras.md` (brief completo) y
`chatbot_maincal_v2.ipynb` (prototipo original, portado a `engine/`).

## Estado actual

- Motor RAG, API, frontend, tests y docs: completos y verificados (pytest,
  lint, typecheck, build de producción, y prueba manual end-to-end en navegador).
- UI rediseñada con el skill `ui-ux-pro-max` (paleta "Enterprise SaaS", Plus
  Jakarta Sans, íconos Phosphor, accesibilidad AA).
- `OPENAI_API_KEY` real cargada y el índice de embeddings ya se generó al
  menos una vez con datos reales.
- **BOM y políticas de inventario son datos REALES de Maincal** (BOM
  exportada de SAP con 17 talles; políticas con lead time/demanda/ROP reales
  para los 3 insumos críticos). `stock_actual` en `stock.json` sigue siendo
  un placeholder — es el input manual/diario, no vino de ningún archivo real.
- **Pendiente**: fichas de proveedores (PDF) reales para Suela de poliuretano
  (PU), Puntera de acero y Caja de empaque — el PDF actual todavía describe
  otro set de insumos (cuero/suela/puntera) de la versión de ejemplo original.
