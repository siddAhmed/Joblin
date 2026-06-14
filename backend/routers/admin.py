from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models.feedback import FeedbackExample
from backend.models.job import Job
from backend.models.match import Match
from backend.models.run import Run, RunCompanyResult

router = APIRouter(prefix="/admin", tags=["admin"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/reset")
async def reset_job_data(session: Session, current_user: CurrentUser):
    counts = {}

    user_job_ids = (await session.execute(
        select(Job.id).where(Job.user_id == current_user.id)
    )).scalars().all()

    counts["feedback_examples"] = (await session.execute(
        select(func.count()).select_from(FeedbackExample).where(FeedbackExample.user_id == current_user.id)
    )).scalar() or 0
    await session.execute(delete(FeedbackExample).where(FeedbackExample.user_id == current_user.id))

    counts["matches"] = (await session.execute(
        select(func.count()).select_from(Match).where(Match.job_id.in_(user_job_ids))
    )).scalar() or 0
    await session.execute(delete(Match).where(Match.job_id.in_(user_job_ids)))

    user_run_ids = (await session.execute(
        select(Run.id).where(Run.user_id == current_user.id)
    )).scalars().all()

    counts["run_company_results"] = (await session.execute(
        select(func.count()).select_from(RunCompanyResult).where(RunCompanyResult.run_id.in_(user_run_ids))
    )).scalar() or 0
    await session.execute(delete(RunCompanyResult).where(RunCompanyResult.run_id.in_(user_run_ids)))

    counts["jobs"] = len(user_job_ids)
    await session.execute(delete(Job).where(Job.user_id == current_user.id))

    counts["runs"] = len(user_run_ids)
    await session.execute(delete(Run).where(Run.user_id == current_user.id))

    await session.commit()
    return {"deleted": counts}
