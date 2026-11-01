# React dashboard and Vercel deployment

The supplied dashboard design is integrated under `web/`. The existing Streamlit UI remains available in `ui/`. Farmer and staff views call the same FastAPI advice, profile, snapshot, alert and FPO endpoints. Source labels and demo-rule warnings are shown with results. Soil uploads, accounts, notifications and a shared conversation archive are not implemented.

## Live demo

https://kisan-saathi-gamma-wine.vercel.app

The public deployment uses fictional read-only profiles, simulated weather, sample mandi prices, and template-based replies by default. It does not upload the local `.env` or farmer database. Role selection chooses a presentation, not an authenticated account. Conversations persist only until the browser page reloads.

`deploy.py` creates an isolated in-memory demo database and mounts the existing API at `/api`. The cache lives in temporary storage. This is intentional: neither is durable on serverless infrastructure. Profile mutation is blocked in this entrypoint; the original local API is unaffected. The rate limiter is process-local and is not a distributed production abuse control.

## Local React preview

Use Node.js 22.12+ or 24 and the existing Python 3.12 environment. From the project folder, terminal 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn deploy:app --host 127.0.0.1 --port 8002
```

For Ayush's prepared workspace, replace `.\.venv\Scripts\python.exe` with `..\..\work\.venv\Scripts\python.exe`.

Terminal 2:

```powershell
cd web
npm ci
npm run dev
```

Open http://127.0.0.1:5173. Vite proxies `/api` to port 8002. This preview ignores the local `.env`; set process environment variables explicitly to test live services. The existing Streamlit setup still uses `.env` as before.

## Deployment

Vercel project: `kisan-saathi2/kisan-saathi`. Repository root is the deployment root, not `web/`. `vercel.json` defines a Vite frontend service and a FastAPI backend service, with `/api/*` routed to Python. `pyproject.toml` contains only backend runtime dependencies; `requirements.txt` remains the complete local development/Streamlit environment.

The GitHub repository is connected to this Vercel project. Push updates to `main` to trigger a deployment. Alternatively, from the project root:

```powershell
npx vercel login
npx vercel --prod
```

Local `.env` files, runtime files, dependencies and build outputs are excluded from deployment and Git. Never set secrets with a `VITE_` prefix: those values are public browser configuration.

To enable live data later, set `DATA_MODE=live` in Vercel's server environment. Add `DATA_GOV_API_KEY` and the verified `DATA_GOV_RESOURCE_ID` for mandi access. For an LLM, set `USE_MOCK_LLM=false` and a private provider key such as `GROQ_API_KEY`. Redeploy after changing environment settings. All agronomic rules remain demo rules even with live data.

Before accepting real personal farmer records, add authentication, authorization, a durable database and a distributed request limiter. This deployment intentionally accepts no profile changes.

## Checks

```powershell
cd web
npm run build
cd ..
python -m scripts.check_hosted
python -m pytest -m "not live"
```

The hosted check verifies API routing, fictional seed records, blocked writes, snapshots, FPO, Hindi advice across rain/dry/outage scenarios, alerts and controlled errors.

Configuration references: https://vercel.com/docs/services and https://vercel.com/docs/frameworks/backend/fastapi.
