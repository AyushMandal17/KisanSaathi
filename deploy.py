"""Public hackathon demo: isolated fictional profiles, read-only, no local secrets."""
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.config import Settings

# Set the default app's storage before importing its factory. A Vercel checkout
# is read-only; neither the deployment nor local preview may open the user's DB.
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["CACHE_PATH"] = str(Path(tempfile.gettempdir()) / "kisansaathi-tool-cache.sqlite3")
from app.main import create_app
from app.repository import FarmerRepository
from app.schemas import FarmerProfile

settings = Settings(_env_file=None)
api = create_app(settings)
with api.state.session_factory() as session:
    repository = FarmerRepository(session)
    payload = json.loads((settings.data_dir / "seed_farmers.json").read_text(encoding="utf-8"))
    for item in payload["farmers"]:
        repository.create(FarmerProfile.model_validate(item))

@api.middleware("http")
async def demo_profiles_only(request: Request, call_next):
    if request.method != "GET" and "/farmers" in request.url.path:
        return JSONResponse(status_code=403, content={"detail": "Hosted demo profiles are read-only."})
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response

app = FastAPI(title="KisanSaathi hosted demo")
app.mount("/api", api)
