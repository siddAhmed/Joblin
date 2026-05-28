from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models import Company, Match, Run
from backend.models.job import Job

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/stats")
async def stats(session: AsyncSession = Depends(get_session)):
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    total_companies = (await session.execute(
        select(func.count()).select_from(Company)
    )).scalar_one()

    total_jobs_in_db = (await session.execute(
        select(func.count()).select_from(Job)
    )).scalar_one()

    todays_matches = (await session.execute(
        select(func.count()).select_from(Match).where(Match.created_at >= today_start)
    )).scalar_one()

    strong_today = (await session.execute(
        select(func.count()).select_from(Match).where(
            Match.created_at >= today_start,
            Match.tier == "strong",
        )
    )).scalar_one()

    quarantine_count = (await session.execute(
        select(func.count()).select_from(Company).where(Company.quarantined_at.isnot(None))
    )).scalar_one()

    last_run = (await session.execute(
        select(Run.completed_at).order_by(Run.completed_at.desc()).limit(1)
    )).scalar_one_or_none()

    return {
        "total_companies": total_companies,
        "total_jobs_in_db": total_jobs_in_db,
        "todays_matches": todays_matches,
        "strong_today": strong_today,
        "quarantine_count": quarantine_count,
        "last_run_completed_at": last_run,
    }
