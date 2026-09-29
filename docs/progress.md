# Progreso del proyecto — Asistente de Compras

> Snapshot al **01/08/2026**. Documento de estado para retomar contexto rápido
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

Las fuentes del cerco de información son reales; la curva de talles es la distribución normal del repo de planificación:

| Fuente | Archivo | Contenido |
|---|---|---|
| Fichas de proveedores | `data/source/Cerco_informacion.pdf` | 3 fichas reales (Poliresinas San Luis, Flecksteel, Papel Pack) — insumo, unidad, proveedor, origen, presentación, contacto. **No** traen lead time, precio ni MOQ |
| BOM del producto | `data/source/BOM _ CRONOS-N04.xlsx` | Export crudo de SAP (220 filas, 17 talles, columna `Tipo` Critico/No Critico) |
| Políticas de inventario | `data/source/politicas_inventario.xlsx` | Lead time, demanda, stock de seguridad, ROP reales (análisis de la tesis) |
| Stock actual | `data/source/stock.json` | `stock_minimo` = ROP real; `stock_actual` es el único dato todavía placeholder (es el input manual/diario por diseño) |
| Curva normal de talles | `data/source/curva_talles.json` | Distribución normal (media 42, desvío 2,5) evaluada en los talles 34–50 y normalizada a suma 100%, la misma que usa el repo de planificación |
| Contexto de negocio | `data/source/contexto_negocio.md` | Real (sin nombre de la empresa): metodología de criticidad, curva de ventas por talle, insumos fuera de alcance y por qué |

**Insumos críticos reales**: Conjunto Sistema PU (variable por talle),
Puntera de acero, Caja de empaque. *No* son cuero vacuno / suela / puntera
como asumía la spec original — ese set salió del análisis real de políticas
de inventario de la tesis, no de la ficha de ejemplo inicial.

Verificado end-to-end (tests automatizados + LLM real + navegador): 86/86
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
  usuario prefiere un talle puntual — nunca promedia ni asume. `data/source/
  curva_talles.json` es la distribución normal del repo de planificación
  (media 42, desvío 2,5, talles 34–50).
- **Markdown en el chat**: `MessageBubble.tsx` renderiza la respuesta con
  `react-markdown` + `remark-gfm` — antes el `**negrita**` que el modelo ya
  emitía se veía como texto crudo con asteriscos.
- **Respuestas sin el desarrollo del cálculo**: el asistente narraba su propio
  procedimiento interno ("1. Listado de insumos...", "2. Cálculo: 200 ×
  464.167 = ...") en vez de ir directo al resultado. `engine/prompts.py`
  separa el procedimiento (interno) de la respuesta visible (FORMATO DE
  RESPUESTA): exige ir al resultado y usar una tabla markdown cuando hay más
  de un insumo o talle involucrado. La tabla del chat también se prolijó
  (header con fondo distinto al body).
- **Function calling: el LLM nunca hace la aritmética** (`engine/tools.py`).
  Iteración anterior (precalcular el consumo ponderado en el contexto)
  arregló un bug pero expuso dos más graves en producción, con captura real:
  (1) al preguntar "con una orden de 1000 pares, ¿alcanza?" (sin talle), el
  modelo aplicaba la curva normal **sin preguntar** — saltaba el gate porque
  el número ya estaba servido en el contexto; (2) en el turno siguiente
  ("para toda la curva de talles?"), el modelo tomó el total YA calculado del
  turno anterior (497 337 g) y lo volvió a multiplicar por 1000 →
  **497 337 000 g**, concluyendo "no alcanza" cuando sobraba 20×. Fix: el
  cálculo se sacó completamente del LLM. `calcular_necesidad_insumos` es una
  tool de OpenAI (function calling) — el modelo solo extrae cantidad/talle/
  si-aplica-curva de la pregunta; Python calcula desde `bom.json` +
  `stock.json` + `curva_talles.json`, siempre desde cero (nunca reutiliza un
  número de un turno anterior), y si falta talle/curva devuelve
  `necesita_aclaracion` **sin ningún número** — el "preguntá antes de
  calcular" pasó de ser una regla de prompt (~70% obedecida) a una garantía
  de código. Verificado reproduciendo el escenario exacto de la captura 4/4
  veces (pregunta primero, después calcula 500 023 g — no 500 023 000).
  `data/index/chunks.json` reveló de paso que las fichas reales **no**
  traen lead time/precio/MOQ (el prompt se lo prometía al modelo — corregido).
- **Contexto de negocio** (`data/source/contexto_negocio.md`, prosa libre sin
  nombre de la empresa): metodología de criticidad de insumos (K-Means K=3
  sobre volumen relativo + alcance productivo + lead time, 24 familias →
  CRÍTICO/IMPORTANTE/SECUNDARIO; pesos AHP solo para etiquetar; regla final
  con mediana de lead time), curva de ventas por talle (forecast Prophet desagregado con
  distribución normal, moda 42, consumo no lineal con el volumen), y qué
  insumos quedan fuera de este sistema y por qué (semielaborados internos;
  cordones/ojalillos → gestión reactiva, lead time corto, no seguimiento
  predictivo). Se inyecta siempre — antes, preguntar por un insumo fuera de
  alcance daba el genérico "no tengo esa información", ahora explica el
  motivo real.

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
- `curva_talles.json`: falta confirmar con Maincal la fuente y la fecha de
  la curva (la `_nota` lo indica como "a confirmar por la empresa").
- **Limitación conocida de `gpt-4o-mini`** (no es un bug de código): en
  preguntas de suficiencia que deberían evaluar los 3 insumos críticos a la
  vez, el modelo podía enumerar solo 1 o 2 en vez de los 3 (verificado antes
  del flag `¿por debajo del mínimo?` en `format_stock()`, reproducible en ~1
  de cada 3 intentos). El flag reduce el riesgo (el modelo ya no *deriva* la
  comparación, la *lee*) pero la redacción final sigue siendo del LLM — no
  está garantizado al 100% como el cálculo de `calcular_necesidad_insumos`.
  El usuario decidió explícitamente mantener `gpt-4o-mini` (no `gpt-4o`) por
  costo; si esto vuelve a fallar en pruebas, re-evaluar.
- **Resuelto (dos veces)**: el error de cálculo en el flujo de curva de
  talles. Primero se precalculó el consumo ponderado en Python pero se
  dejaba en el contexto para que el LLM multiplicara — funcionó pero expuso
  algo peor (ver "Function calling" arriba: el modelo saltaba el gate y
  reutilizaba totales de turnos anteriores). La solución final saca el
  cálculo del LLM por completo con function calling.
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
