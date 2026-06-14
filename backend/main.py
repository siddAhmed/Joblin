import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.database import AsyncSessionLocal
from backend.routers import system, companies, runs as runs_router, jobs, matches, settings as settings_router, presets
from backend.routers.admin import router as admin_router
from backend.routers.insights import router as insights_router
from backend.routers.resume import router as resume_router
from backend.routers.usage import router as usage_router
from backend.routers.applications import router as applications_router


FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from apscheduler import AsyncScheduler
    from backend.config import seed_defaults
    from backend.scheduler import start_scheduler

    async with AsyncSessionLocal() as session:
        await seed_defaults(session, user_id=1)

    async with AsyncScheduler() as scheduler:
        app.state.scheduler = scheduler
        await start_scheduler(scheduler)
        await scheduler.start_in_background()
        yield


def create_app() -> FastAPI:
    app = FastAPI(title="Joblin", lifespan=lifespan)
    app.include_router(system.router, prefix="/api")
    app.include_router(companies.router, prefix="/api")
    app.include_router(runs_router.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(matches.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(presets.router, prefix="/api")
    app.include_router(usage_router, prefix="/api")
    app.include_router(admin_router, prefix="/api")
    app.include_router(insights_router, prefix="/api")
    app.include_router(resume_router, prefix="/api")
    app.include_router(applications_router, prefix="/api")
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="spa")
    return app


app = create_app()
