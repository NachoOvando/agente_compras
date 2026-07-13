# Deployment — Asistente de Compras

## Requisitos

- Node.js 18+ y Python 3.10+ (desarrollado con Node 24 / Python 3.14).
- Una API key de OpenAI.

## Desarrollo local

```bash
# 1. Dependencias
npm install
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows
# source .venv/bin/activate && pip install -r requirements-dev.txt  # macOS/Linux
# (requirements-dev.txt incluye el runtime + scripts + tests; el root
#  requirements.txt es solo el runtime lean que instala Vercel)

# 2. Entorno
cp .env.example .env      # completar OPENAI_API_KEY

# 3. Datos e índice (solo la primera vez o al cambiar las fuentes)
.venv/Scripts/python scripts/seed_example_data.py
.venv/Scripts/python scripts/build_index.py

# 4. Levantar ambos servers (Next.js :3000 + FastAPI :8000)
npm run dev
```

`npm run dev` usa `concurrently` para levantar `next dev` y `uvicorn`. En dev,
Next.js reescribe `/api/py/*` a `http://127.0.0.1:8000` (ver `next.config.js`).

También se puede usar el asistente sin navegador:

```bash
.venv/Scripts/python -m engine.cli demo    # preguntas predefinidas
.venv/Scripts/python -m engine.cli         # modo interactivo
```

## Tests y checks

```bash
.venv/Scripts/python -m pytest    # tests del motor y de los endpoints
npm run lint                       # ESLint
npm run typecheck                  # tsc --noEmit
```

## Deploy en Vercel

> **Prerequisito bloqueante (manual):** `data/index/` debe estar generado y
> commiteado antes de deployar — correr `python scripts/build_index.py` con una
> `OPENAI_API_KEY` real en `.env` y commitear `chunks.json`, `embeddings.npy` y
> `bom.json`. Sin el índice, la app deploya pero no puede responder consultas.

1. Repo en GitHub: `agente_compras` (verificar que `data/index/` esté
   commiteado: los embeddings precomputados son parte del deploy).
2. En Vercel: **Import Project** → framework Next.js (se detecta solo).
   `api/index.py` se deploya automáticamente como serverless function Python.
   Vercel instala **solo el `requirements.txt` de la raíz** (runtime lean);
   `requirements-dev.txt` es exclusivamente local y Vercel nunca lo lee.
3. Configurar la Environment Variable `OPENAI_API_KEY` en el proyecto
   (Settings → Environment Variables). Nunca commitearla.
4. Deploy. Verificar `https://<proyecto>.vercel.app/api/py/health`.

### Actualizar el cerco de información

Al cambiar las fichas (PDF), la BOM o el stock:

```bash
.venv/Scripts/python scripts/build_index.py
git add data/ && git commit -m "Actualizar cerco de información" && git push
```

Vercel redeploya automáticamente con el índice nuevo.

## Variables de entorno

| Variable | Dónde | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | `.env` local / Environment Variables en Vercel | Clave de OpenAI para embeddings (`text-embedding-3-small`) y generación (`gpt-4o-mini`). |
