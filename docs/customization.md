# Personalización — dónde tocar qué

Guía rápida para editar el asistente: motor RAG, API key y datos del cerco de
información. Para entender *por qué* está armado así, ver
[architecture.md](architecture.md); para los endpoints, [api-reference.md](api-reference.md).

## API key de OpenAI

| Entorno | Dónde va |
|---|---|
| Local (desarrollo) | Archivo `.env` en la raíz del proyecto, variable `OPENAI_API_KEY=sk-...`. Se crea copiando `.env.example` (`cp .env.example .env`). **Nunca se commitea** (está en `.gitignore`). |
| Vercel (producción) | Project → Settings → Environment Variables → `OPENAI_API_KEY`. Después de cargarla hay que redeployar. |

La key se lee en [`engine/config.py`](../engine/config.py) (`get_api_key()` /
`get_openai_client()`). Si falta, cualquier consulta al asistente devuelve un
error claro (`400 INVALID_REQUEST`) en vez de fallar silenciosamente — no hace
falta tocar código para esto, solo cargar la variable.

## El motor RAG (`engine/`)

Toda la lógica de negocio vive en `engine/`, independiente de la web (se puede
probar y correr por consola sin levantar ningún server). Mapa de qué archivo
tocar según lo que quieras cambiar:

| Querés cambiar... | Archivo | Qué hay ahí |
|---|---|---|
| El **system prompt** (reglas del cerco, tono, formato de respuesta) | [`engine/prompts.py`](../engine/prompts.py) | `SYSTEM_PROMPT` (las reglas que le prohíben inventar datos) y `build_user_prompt()` |
| El **modelo de generación** (`gpt-4o-mini` → otro) | [`engine/config.py`](../engine/config.py) | `CHAT_MODEL` |
| El **modelo de embeddings** | [`engine/config.py`](../engine/config.py) | `EMBEDDING_MODEL` — **si lo cambiás hay que regenerar el índice** (`python scripts/build_index.py`), los vectores viejos no son compatibles |
| **Temperatura / longitud de respuesta** | [`engine/config.py`](../engine/config.py) | `TEMPERATURE` (0.1 = respuestas fieles al dato), `MAX_TOKENS` |
| **Cuántos chunks se recuperan por pregunta** | [`engine/config.py`](../engine/config.py) | `TOP_K` (default 3) |
| El **nombre del producto** o las **preguntas de ejemplo** | [`shared/app-config.json`](../shared/app-config.json) | Fuente única compartida por Python (`engine/config.py` la carga como `PRODUCTO`/`PREGUNTAS_DEMO`) y frontend (`lib/app-config.ts`). **No editar en config.py ni en los componentes React** |
| **Tamaño de chunk / overlap** del PDF | [`engine/config.py`](../engine/config.py) | `CHUNK_SIZE`, `CHUNK_OVERLAP` — cambiarlos también requiere re-indexar |
| Cómo se arma el contexto (qué se le manda al LLM) | [`engine/context.py`](../engine/context.py) | `build_context()`, `format_bom()`, `format_stock()` |
| Cómo se calcula similitud / se eligen los top-k chunks | [`engine/retrieval.py`](../engine/retrieval.py) | `cosine_similarities()`, `top_k_chunks()` |
| Lectura de PDF y chunking | [`engine/indexing.py`](../engine/indexing.py) | `read_pdf_text()`, `split_text_chunks()` |
| La orquestación completa (retrieve → augment → generate) | [`engine/generate.py`](../engine/generate.py) | `rag_answer()` |

Después de tocar `config.py` o `prompts.py` **no** hace falta re-indexar (solo
afecta la fase de generación). Solo hay que re-indexar
(`python scripts/build_index.py`) cuando cambia: el PDF de fichas, la BOM, el
modelo de embeddings, o `CHUNK_SIZE`/`CHUNK_OVERLAP`.

## Datos del cerco de información

| Fuente | Archivo | Cómo se actualiza |
|---|---|---|
| Fichas de proveedores | `data/source/datos_maincal_EJEMPLO.pdf` | Reemplazar el PDF (mismo esquema: 1 insumo crítico por sección) → correr `python scripts/build_index.py` |
| BOM del producto | `data/source/bom_cronos_n04.xlsx` | Editar el Excel (columnas: `codigo, insumo, unidad, consumo_por_unidad, critico`) → correr `python scripts/build_index.py` |
| Stock actual | `data/source/stock.json` | Editar directo el JSON, o regenerar con `python scripts/seed_example_data.py` (solo datos de ejemplo) |

`data/index/` (chunks, embeddings, BOM normalizada) se genera automáticamente
por `build_index.py` — no se edita a mano.

## Frontend (si querés cambiar textos, colores o preguntas de ejemplo)

- Preguntas de ejemplo y nombre del producto: `shared/app-config.json` (fuente única — la leen `engine/config.py` del lado Python y `lib/app-config.ts` del lado frontend; `engine/cli.py` importa `PREGUNTAS_DEMO` desde `engine.config`).
- Paleta de colores / tipografía: variables CSS en `app/globals.css` (`--color-*`) y `tailwind.config.ts`.
- Textos de la página principal: `app/page.tsx`.

## Probar un cambio rápido sin levantar la web

```bash
.venv/Scripts/python -m engine.cli demo   # corre las preguntas de ejemplo por consola
.venv/Scripts/python -m engine.cli        # modo interactivo
```
