import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.database import AsyncSessionLocal
from backend.routers import system, companies, runs as runs_router


FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from backend.config import seed_defaults
    async with AsyncSessionLocal() as session:
        await seed_defaults(session)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Joblin", lifespan=lifespan)
    app.include_router(system.router, prefix="/api")
    app.include_router(companies.router, prefix="/api")
    app.include_router(runs_router.router, prefix="/api")
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
    return app


app = create_app()
