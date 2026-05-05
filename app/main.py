from fastapi import FastAPI

from app.routes import admin, public

app = FastAPI(title="AI Olympiad Leaderboard")
app.include_router(public.router)
app.include_router(admin.router)
