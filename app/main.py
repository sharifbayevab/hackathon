from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routes import admin, public

app = FastAPI(title="AI Olympiad Leaderboard")
app.include_router(public.router)
app.include_router(admin.router)

# Public static assets (test_features.csv etc.). Groundtruth is NOT here.
app.mount("/files", StaticFiles(directory=str(settings.assets_dir)), name="files")
