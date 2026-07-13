# Arquitectura — Asistente de Compras Maincal (LLM + RAG)

## Qué es

Asistente conversacional que recomienda prioridades de compra de insumos críticos
del producto Cronos-N04, respondiendo **exclusivamente** con datos de la empresa
(el "cerco de información"). Si el dato no está en el cerco, responde que no lo
tiene — nunca inventa. Prueba de concepto de tesis, con datos de ejemplo ficticios.

## Decisiones principales

| Decisión | Razonamiento |
|---|---|
| Monorepo Next.js + FastAPI (patrón del template oficial de Vercel) | Un solo deploy en Vercel: Next.js sirve la UI y `api/index.py` corre como serverless function Python. Python es obligatorio para la parte de datos (pandas, numpy, embeddings) según los estándares del proyecto. |
| Embeddings **precomputados offline** (`scripts/build_index.py`) y commiteados en `data/index/` | El filesystem de Vercel es read-only y las funciones tienen cold start: generar embeddings en runtime sería lento, caro y fallaría al escribir a disco. En runtime solo se embebe la pregunta del usuario. |
| Doble tratamiento de fuentes: fichas PDF → RAG; BOM y stock → inyección directa | El texto descriptivo se recupera bien por similitud semántica. Los números (consumos, stock) deben ser exactos: pasan al contexto sin pasar por embeddings para no perder precisión. |
| BOM Excel → `bom.json` en build | La serverless function no necesita pandas/openpyxl: solo lee JSON. Menos peso y menos cold start. |
| Overrides de stock por request (sin persistencia) | El spec define el stock como input manual/dinámico. Con filesystem read-only no se puede persistir; el panel de la UI envía `stockOverrides` con cada consulta. |
| **Sin base de datos** | El cerco de información son archivos (PDF + Excel + JSON) y el prototipo no tiene usuarios ni estado persistente. Agregar PostgreSQL sería complejidad sin función. Si se integra un ERP/inventario real, ese será el momento de revisar esta decisión. |
| Similitud coseno con numpy (sin scikit-learn) | Es una operación de dos líneas; evita cargar sklearn en la serverless function (límite de tamaño de Vercel). |

## Capas

```
Browser
  └── Componentes React (src/components/ — presentación)
        └── src/lib/api-client.ts (fetch tipado, contrato {data}/{error,code})
              └── api/index.py (FastAPI — solo routing y validación)
                    └── engine/ (motor RAG — lógica de dominio, testeable sin servidor)
                          └── data/ (cerco de información: fuentes + índice precomputado)
```

Reglas respetadas: los componentes no llaman a la API directamente (pasan por
`src/lib/`), los routers no tienen lógica de negocio (delegan a `engine/`), y el
motor no importa nada de FastAPI ni de React.

## Flujo de una consulta

1. La UI envía `POST /api/py/ask` con la pregunta (+ overrides de stock si el usuario editó el panel).
2. `engine.generate.rag_answer`:
   - **Retrieve**: embebe la pregunta (`text-embedding-3-small`), similitud coseno contra el índice precomputado de fichas, selecciona `TOP_K=3` chunks.
   - **Augment**: contexto = chunks + BOM completa + stock actual (con overrides).
   - **Generate**: `gpt-4o-mini` con system prompt que impone el cerco (`temperature=0.1`, `max_tokens=800`).
3. La respuesta vuelve como `{ data: { answer, sources } }`.

## Fase de preparación (offline, al actualizar fuentes)

```
python scripts/seed_example_data.py   # regenera BOM.xlsx y stock.json de ejemplo
python scripts/build_index.py         # PDF → chunks → embeddings; BOM.xlsx → bom.json
```

Los artefactos generados (`data/index/`) se commitean: son parte del deploy.

## Escalabilidad prevista (sección 10 del spec)

- Agregar un insumo crítico: sumar su ficha al PDF + su entrada en `stock.json`, y re-correr `build_index.py`. Sin tocar código.
- Agregar un producto: sumar su BOM (hoy el motor asume un producto; generalizar `engine/context.py` para indexar BOM por producto).
- Cambiar de modelos: una línea en `engine/config.py` (`EMBEDDING_MODEL`, `CHAT_MODEL`). Ojo: cambiar el modelo de embeddings exige regenerar el índice.
- Stock automático: reemplazar la lectura de `stock.json` por un fetch al ERP/sistema de inventario dentro de `engine/context.py`.
