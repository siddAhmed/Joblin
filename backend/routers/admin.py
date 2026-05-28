from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.feedback import FeedbackExample
from backend.models.job import Job
from backend.models.match import Match
from backend.models.run import Run, RunCompanyResult

router = APIRouter(prefix="/admin", tags=["admin"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/reset")
async def reset_job_data(session: Session):
    counts = {}

    counts["feedback_examples"] = (await session.execute(select(func.count()).select_from(FeedbackExample))).scalar() or 0
    await session.execute(delete(FeedbackExample))

    counts["matches"] = (await session.execute(select(func.count()).select_from(Match))).scalar() or 0
    await session.execute(delete(Match))

    counts["run_company_results"] = (await session.execute(select(func.count()).select_from(RunCompanyResult))).scalar() or 0
    await session.execute(delete(RunCompanyResult))

    counts["jobs"] = (await session.execute(select(func.count()).select_from(Job))).scalar() or 0
    await session.execute(delete(Job))

    counts["runs"] = (await session.execute(select(func.count()).select_from(Run))).scalar() or 0
    await session.execute(delete(Run))

    await session.commit()
    return {"deleted": counts}
