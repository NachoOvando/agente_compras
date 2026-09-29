# CLAUDE.md — Asistente de Compras

Contexto del proyecto para Claude Code. Complementa (no reemplaza) las
convenciones globales de `~/.claude/CLAUDE.md` — en caso de conflicto, este
archivo tiene precedencia por ser específico del repo.

## Qué es

Prototipo de tesis: asistente conversacional (LLM + RAG) que recomienda
prioridades de compra de insumos críticos del producto **Cronos-N04** para
la empresa, respondiendo **exclusivamente** con datos de la empresa (el
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
scripts/         build_index.py — único script: indexa fichas, BOM (export SAP) y políticas
data/source/     cerco de información: Cerco_informacion.pdf, BOM _ CRONOS-N04.xlsx (SAP), stock.json, politicas_inventario.xlsx, contexto_negocio.md (reales) + curva_talles.json (normal, media 42 / desvío 2,5, del repo de planificación)
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
- **Armado de contexto (BOM + stock + fichas + políticas + curva de talles + contexto de negocio)**: `engine/context.py`.
- **Cálculo de necesidad de insumos (talle puntual o curva normal)**: `engine/tools.py` — function calling de OpenAI, el LLM nunca hace la cuenta, solo redacta el resultado exacto que devuelve Python.
- **Insumos críticos actuales**: Conjunto Sistema PU — consumo variable por talle (T34–T50), fusión de 4 componentes SAP —, Puntera de acero y Caja de empaque. Mapeo SAP→insumo en `CRITICOS_SAP_A_INSUMO` (BOM) y `FAMILIA_A_INSUMO` (políticas), ambos en `scripts/build_index.py`.
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
- `OPENAI_API_KEY` real cargada y el índice se generó con datos reales.
- **Las 4 fuentes del cerco son datos REALES de la empresa**: fichas de
  proveedores (`Cerco_informacion.pdf`), BOM (export crudo de SAP,
  17 talles, parseado directo por `build_bom_json()`), políticas de
  inventario (lead time/demanda/ROP reales para los 3 insumos críticos) y
  stock (`stock_actual` es el input manual/diario, no viene de ningún
  archivo — el resto de `stock.json` sí es real).
- `scripts/seed_example_data.py` se eliminó (datos ficticios ya superados
  por los reales; el flujo de datos de ejemplo ya no existe).
- `data/source/curva_talles.json` (distribución de producción por talle) es
  la normal (media 42, desvío 2,5) del repo de planificación. Pendiente:
  confirmar con Maincal la fuente y la fecha de la curva (ver TODO en README).
  Cuando el usuario pide una cantidad de pares sin desglose por talle, el
  asistente pregunta si aplicar la curva normal o un talle puntual (regla 6
  de `engine/prompts.py`) antes de calcular, en vez de promediar.
- Chat con render de markdown (`react-markdown` + `remark-gfm` en
  `MessageBubble.tsx`) — el modelo ya devolvía negrita/listas, ahora se ven.
- **Cálculo de necesidad de insumos vía function calling** (`engine/tools.py`):
  el LLM extrae cantidad/talle/curva de la pregunta pero la aritmética la
  hace Python — corrige un bug real en producción donde el modelo reutilizaba
  un total ya calculado de un turno anterior y lo volvía a multiplicar
  (1000 pares → total → "× 1000" otra vez).
- **Contexto de negocio** (`data/source/contexto_negocio.md`, sin nombre de la
  empresa): metodología de criticidad de insumos (K-Means sobre volumen
  relativo + alcance productivo + lead time), curva de ventas por talle, y qué insumos
  quedan fuera de este sistema y por qué (ej. cordones/ojalillos → gestión
  reactiva, no predictiva) — se inyecta siempre en el contexto.
