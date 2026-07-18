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
data/source/     cerco de información: PDF fichas, BOM.xlsx, stock.json
data/index/      índice generado (chunks.json, embeddings.npy, bom.json) — no editar a mano
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
- **Armado de contexto (BOM + stock + fichas)**: `engine/context.py`.
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
- **Pendiente**: cargar una `OPENAI_API_KEY` real en `.env` y correr
  `scripts/build_index.py` — sin esto el asistente no puede responder consultas
  (el resto del flujo ya está probado con datos de ejemplo).
- Datos del cerco son ficticios (mismo esquema que los reales de Maincal),
  copiados/generados desde la carpeta de la tesis. Reemplazar por datos reales
  cuando estén disponibles (ver `docs/customization.md`).
