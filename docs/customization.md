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
| **Rango de talles soportado** | [`engine/config.py`](../engine/config.py) | `TALLES` (default 34–50) |
| El **nombre del producto** o las **preguntas de ejemplo** | [`shared/app-config.json`](../shared/app-config.json) | Fuente única compartida por Python (`engine/config.py` la carga como `PRODUCTO`/`PREGUNTAS_DEMO`) y frontend (`src/lib/app-config.ts`). **No editar en config.py ni en los componentes React** |
| **Tamaño de chunk / overlap** del PDF | [`engine/config.py`](../engine/config.py) | `CHUNK_SIZE`, `CHUNK_OVERLAP` — cambiarlos también requiere re-indexar |
| Cómo se arma el contexto (qué se le manda al LLM) | [`engine/context.py`](../engine/context.py) | `build_context()`, `format_bom()`, `format_stock()`, `format_politicas()`, `format_curva_talles()`, `load_contexto_negocio()` |
| Cómo se calcula la necesidad de insumos para una cantidad de pares (talle puntual o curva normal) | [`engine/tools.py`](../engine/tools.py) | `calcular_necesidad_insumos()` — el LLM nunca hace esta cuenta, la invoca como tool (function calling de OpenAI) y solo redacta el resultado exacto que devuelve Python |
| Cómo se calcula similitud / se eligen los top-k chunks | [`engine/retrieval.py`](../engine/retrieval.py) | `cosine_similarities()`, `top_k_chunks()` |
| Lectura de PDF y chunking (1 chunk por ficha) | [`engine/indexing.py`](../engine/indexing.py) | `read_pdf_pages()`, `split_pages_into_chunks()`, `split_text_chunks()` |
| La orquestación completa (retrieve → augment → generate, incluida la ronda de tool calling) | [`engine/generate.py`](../engine/generate.py) | `rag_answer()` |

Después de tocar `config.py` o `prompts.py` **no** hace falta re-indexar (solo
afecta la fase de generación). Solo hay que re-indexar
(`python scripts/build_index.py`) cuando cambia: el PDF de fichas, la BOM, el
modelo de embeddings, o `CHUNK_SIZE`/`CHUNK_OVERLAP`.

## Datos del cerco de información

| Fuente | Archivo | Cómo se actualiza |
|---|---|---|
| Fichas de proveedores | `data/source/Cerco_informacion.pdf` | Reemplazar el PDF (1 ficha por insumo crítico: insumo, unidad, proveedor, contacto, origen, presentación — **no** traen lead time, precio ni MOQ, eso vive en políticas de inventario) → correr `python scripts/build_index.py` |
| BOM del producto | `data/source/BOM _ CRONOS-N04.xlsx` | Export crudo de SAP (una fila por componente × talle: `Número de material`, `Componente de lista de materia`, `Cantidad`, `UM`, `Tipo`). Actualizarla es soltar el export nuevo con ese mismo nombre → correr `python scripts/build_index.py`, sin transformar nada a mano. El parser (`build_bom_json()` en `scripts/build_index.py`) agrupa por familia (ignorando el sufijo de talle), detecta consumo fijo vs. variable por talle automáticamente, y fusiona los componentes críticos que forman un insumo lógico único según `CRITICOS_SAP_A_INSUMO` (ej. los 4 componentes del sistema PU → "Conjunto Sistema PU") — agregar ahí si cambia el set de insumos críticos |
| Políticas de inventario | `data/source/politicas_inventario.xlsx` | Editar el Excel (columnas: `Familia, UM, Política, Lead_Time_dias, Demanda_media_mensual, Desvio_mensual, Stock_Seguridad, ROP_o_Nivel_Objetivo, Stock_Maximo, Cobertura_SS_dias`). El nombre de `Familia` tiene que estar en `FAMILIA_A_INSUMO` (`scripts/build_index.py`) — agregarlo ahí si es un insumo crítico nuevo → correr `python scripts/build_index.py` |
| Stock actual | `data/source/stock.json` | Editar directo el JSON — `stock_actual` es el input manual/diario; `stock_minimo` es el ROP real de `politicas_inventario.xlsx` |
| Curva normal de talles | `data/source/curva_talles.json` | **PLACEHOLDER** — hoy es una curva de ejemplo (campana centrada en T42, el talle medio real del negocio), no la distribución real de ventas. Editar directo el JSON: `talles.{34..50}` en % (tiene que sumar ~100). Se usa cuando el usuario pide una cantidad de pares sin desglose por talle (regla 6 del prompt) — el asistente pregunta si aplicarla antes de calcular, y `engine/tools.py` hace el cálculo ponderado en Python |
| Contexto de negocio | `data/source/contexto_negocio.md` | Prosa libre (markdown), sin nombre de la empresa: perfil productivo, metodología de criticidad de insumos, curva de ventas por talle, y qué insumos quedan fuera de alcance y por qué (ej. cordones/ojalillos → gestión reactiva). Editar directo el archivo, no requiere re-indexar |

`data/index/` (chunks, embeddings, BOM y políticas normalizadas) se genera
automáticamente por `build_index.py` — no se edita a mano.

**Insumos críticos**: son los que tienen ficha (PDF), stock y política de
inventario — hoy Conjunto Sistema PU (consumo variable por talle), Puntera
de acero y Caja de empaque. Si ese set cambia, hay que actualizar
`CRITICOS_SAP_A_INSUMO`/`FAMILIA_A_INSUMO` (`scripts/build_index.py`) y los
demás archivos de `data/source/` de forma consistente (mismo nombre de
`insumo` en los cuatro).

## Frontend (si querés cambiar textos, colores o preguntas de ejemplo)

- Preguntas de ejemplo y nombre del producto: `shared/app-config.json` (fuente única — la leen `engine/config.py` del lado Python y `src/lib/app-config.ts` del lado frontend; `engine/cli.py` importa `PREGUNTAS_DEMO` desde `engine.config`).
- Paleta de colores / tipografía: variables CSS en `src/app/globals.css` (`--color-*`) y `tailwind.config.ts`.
- Textos de la página principal: `src/app/page.tsx`.

## Probar un cambio rápido sin levantar la web

```bash
.venv/Scripts/python -m engine.cli demo   # corre las preguntas de ejemplo por consola
.venv/Scripts/python -m engine.cli        # modo interactivo
```
