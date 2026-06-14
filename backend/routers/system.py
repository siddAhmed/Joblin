from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models import Company, Match, Run
from backend.models.job import Job

router = APIRouter(tags=["system"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/stats")
async def stats(session: Session, current_user: CurrentUser):
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    total_companies = (await session.execute(
        select(func.count()).select_from(Company).where(Company.user_id == current_user.id)
    )).scalar_one()

    total_jobs_in_db = (await session.execute(
        select(func.count()).select_from(Job).where(Job.user_id == current_user.id)
    )).scalar_one()

    todays_matches = (await session.execute(
        select(func.count()).select_from(Match)
        .join(Job, Match.job_id == Job.id)
        .where(Job.user_id == current_user.id, Match.created_at >= today_start)
    )).scalar_one()

    strong_today = (await session.execute(
        select(func.count()).select_from(Match)
        .join(Job, Match.job_id == Job.id)
        .where(
            Job.user_id == current_user.id,
            Match.created_at >= today_start,
            Match.tier == "strong",
        )
    )).scalar_one()

    quarantine_count = (await session.execute(
        select(func.count()).select_from(Company).where(
            Company.user_id == current_user.id,
            Company.quarantined_at.isnot(None),
        )
    )).scalar_one()

    last_run = (await session.execute(
        select(Run.completed_at)
        .where(Run.user_id == current_user.id)
        .order_by(Run.completed_at.desc())
        .limit(1)
    )).scalar_one_or_none()

    return {
        "total_companies": total_companies,
        "total_jobs_in_db": total_jobs_in_db,
        "todays_matches": todays_matches,
        "strong_today": strong_today,
        "quarantine_count": quarantine_count,
        "last_run_completed_at": last_run,
    }


@router.get("/onboarding-status")
async def onboarding_status(session: Session, current_user: CurrentUser):
    company_count = (await session.execute(
        select(func.count()).select_from(Company).where(Company.user_id == current_user.id)
    )).scalar_one()
    return {"needs_onboarding": company_count == 0}
