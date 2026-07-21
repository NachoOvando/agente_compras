# Progreso del proyecto — Asistente de Compras

> Snapshot al **19/07/2026**. Documento de estado para retomar contexto rápido
> (propio, para la tesis, o para una sesión nueva de Claude Code). No es un
> changelog exhaustivo — para eso está `git log`. Para "cómo está armado"
> ver [architecture.md](architecture.md); para "qué toco para cambiar X" ver
> [customization.md](customization.md).

## Qué es

Prototipo de tesis: asistente conversacional (LLM + RAG) que recomienda
prioridades de compra de insumos críticos del producto **Cronos-N04** para
la empresa, respondiendo **exclusivamente** con datos reales de la empresa
(el "cerco de información"). Si el dato no está ahí, dice que no lo tiene —
nunca inventa. Empezó como notebook (`chatbot_maincal_v2.ipynb` /
`chatbot_compras.ipynb`, en la carpeta de la tesis) y se reconstruyó como web
app completa: Next.js 15 (App Router, React 19) + FastAPI, un solo deploy en
Vercel.

## Estado actual: funcional con datos 100% reales

Las 4 fuentes del cerco de información ya no son ficticias:

| Fuente | Archivo | Contenido |
|---|---|---|
| Fichas de proveedores | `data/source/Cerco_informacion.pdf` | 3 fichas reales (Poliresinas San Luis, Flecksteel, Papel Pack) |
| BOM del producto | `data/source/BOM _ CRONOS-N04.xlsx` | Export crudo de SAP (220 filas, 17 talles, columna `Tipo` Critico/No Critico) |
| Políticas de inventario | `data/source/politicas_inventario.xlsx` | Lead time, demanda, stock de seguridad, ROP reales (análisis de la tesis) |
| Stock actual | `data/source/stock.json` | `stock_minimo` = ROP real; `stock_actual` es el único dato todavía placeholder (es el input manual/diario por diseño) |

**Insumos críticos reales**: Conjunto Sistema PU (variable por talle),
Puntera de acero, Caja de empaque. *No* son cuero vacuno / suela / puntera
como asumía la spec original — ese set salió del análisis real de políticas
de inventario de la tesis, no de la ficha de ejemplo inicial.

Verificado end-to-end (tests automatizados + LLM real + navegador): 62/62
tests, lint y typecheck en verde, deploy a Vercel sin errores.

## Funcionalidades implementadas

- **RAG sobre fichas de proveedores**: embeddings (`text-embedding-3-small`)
  + similitud coseno, `TOP_K=3`. Chunking **1 chunk por ficha** (no todo el
  PDF junto) para que la recuperación tenga granularidad real.
- **BOM inyectada directa** (sin embeddings, precisión numérica): parseada
  del export crudo de SAP — agrupa componentes por familia, fusiona los que
  forman un insumo crítico lógico (ej. 4 componentes SAP → "Conjunto Sistema
  PU"), y detecta automáticamente si el consumo es fijo o varía por talle.
- **Consumo variable por talle**: el calzado tiene 17 talles (T34–T50); el
  Conjunto Sistema PU consume distinto según el talle. El talle viaja como
  texto libre dentro de la pregunta (nunca se agregó un campo estructurado)
  — el modelo debe usar el valor exacto de la tabla o pedir el talle si hace
  falta y no se especificó, nunca promediar.
- **Políticas de inventario reales**: `stock_minimo` = ROP calculado con
  lead time + demanda + variabilidad, no un número arbitrario. El contexto
  también expone stock de seguridad, stock máximo y política de revisión
  para que el asistente pueda explicar el "por qué" de una prioridad.
- **Memoria de conversación**: historial de pregunta+respuesta (nunca el
  contexto armado, que es pesado y se reconstruye fresco en cada llamada) de
  punta a punta — motor Python → API → frontend → CLI interactivo. Permite
  repreguntas ("¿y en qué presentación viene?") sin repetir el insumo.
- **UI** rediseñada con el skill `ui-ux-pro-max` (paleta "Enterprise SaaS",
  Plus Jakarta Sans, íconos Phosphor, accesibilidad AA).
- **CLI** (`python -m engine.cli demo` / modo interactivo) para probar sin
  levantar la web — útil para la defensa.
- **Curva normal de talles**: si preguntan por una cantidad total de pares
  sin desglose por talle (ej. "¿alcanza el stock para 5000 pares?"), el
  asistente **pregunta primero** si aplica la curva normal de talles o si el
  usuario prefiere un talle puntual — nunca promedia ni asume (bug real que
  motivó esto: el LLM había inventado "un promedio de talles" para responder
  una orden grande, con un total que ni siquiera cerraba con el detalle).
  `data/source/curva_talles.json` es **placeholder** (campana de ejemplo
  T41-T42), falta la curva real.
- **Markdown en el chat**: `MessageBubble.tsx` renderiza la respuesta con
  `react-markdown` + `remark-gfm` — antes el `**negrita**` que el modelo ya
  emitía se veía como texto crudo con asteriscos.

## Decisiones de diseño que vale la pena recordar

- **Sin base de datos**: el cerco de información son archivos versionados en
  git (`data/source/` + `data/index/` precomputado), justificado en
  `architecture.md`.
- **El talle no tiene campo estructurado en la API.** Una orden real de
  fábrica es una corrida de talles (ej. 100 pares T38, 200 T40...) — texto
  libre lo maneja mejor que un `<select>` de un solo talle, y el costo en
  tokens de mandar la tabla completa por talle es despreciable.
- **`requirements.txt` (raíz) vs. `requirements-dev.txt`**: Vercel solo
  instala el primero (runtime lean: fastapi, openai, numpy, dotenv); pandas/
  openpyxl/pypdf/pytest quedan en el segundo, solo para local.
- **`vercel.json` no lleva `"runtime"`** — el runtime Python built-in se
  auto-detecta; declararlo con un valor tipo `"python3.12"` rompe el deploy
  ("Function Runtimes must have a valid version"). Ya rompió dos veces por
  reintroducirse sin querer al resolver merges — si vuelve a pasar, revisar
  el archivo antes de asumir que hace falta.
- **Otra sesión de Claude Code (cloud) trabaja sobre el mismo repo de forma
  independiente**, y el usuario también sube archivos manualmente por la web
  de GitHub. Por eso desde mitad de proyecto es rutina correr `git fetch` +
  revisar `main..origin/main` antes de cada push.

## Pendiente / próximos pasos

- `stock_actual` en `stock.json` sigue siendo un valor de ejemplo — falta
  reemplazarlo por una fuente real (manual o integración con ERP/logística),
  tal como está planteado desde la spec original.
- `curva_talles.json` es de ejemplo — falta la distribución real de
  producción/ventas por talle de la empresa.
- **Limitación conocida de `gpt-4o-mini`** (no es un bug de código): en
  preguntas de suficiencia que deberían evaluar los 3 insumos críticos a la
  vez, a veces el modelo solo enumera 1 o 2 en vez de los 3 (verificado con
  llamadas reales, reproducible en ~1 de cada 3 intentos pese a un prompt
  explícito paso a paso). **Lo que sí quedó 100% resuelto y confirmado 3/3**:
  el bug original (promediar/inventar un talle en vez de preguntar) — cuando
  la pregunta involucra específicamente el insumo variable por talle, el
  asistente nunca promedia; pregunta o dice que no tiene el dato. Si la
  confiabilidad en preguntas multi-insumo importa para la defensa, probar
  `CHAT_MODEL = "gpt-4o"` en `engine/config.py` (un modelo más grande, más
  caro) antes de invertir más tiempo en prompt engineering — puede ser un
  techo del modelo chico, no del prompt.
- Vercel: confirmar que el deploy productivo funciona de punta a punta con
  el fix de `vercel.json` (se corrigió el error, falta la confirmación en
  producción con `OPENAI_API_KEY` cargada ahí).
- Sin autenticación (prototipo académico) — no es un pendiente funcional,
  pero vale tenerlo presente si se piensa exponer más ampliamente.

## Dónde mirar para más detalle

- [architecture.md](architecture.md) — por qué está armado así.
- [customization.md](customization.md) — qué archivo tocar para cada cambio.
- [api-reference.md](api-reference.md) — contrato de los 3 endpoints.
- [deployment.md](deployment.md) — cómo correr local y deployar.
- `CLAUDE.md` (raíz del repo) — contexto para retomar con Claude Code.
