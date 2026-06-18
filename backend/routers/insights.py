from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.llm.factory import get_filter_provider
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models.company_catalog import CompanyCatalog
from backend.models.job_skill import JobSkill
from backend.models.match import Match

router = APIRouter(prefix="/insights", tags=["insights"])
Session = Annotated[AsyncSession, Depends(get_session)]


class AnalyzeRequest(BaseModel):
    match_ids: list[int]


@router.post("/analyze")
async def analyze_skills(req: AnalyzeRequest, session: Session, current_user: CurrentUser):
    settings = await get_all_settings(session, user_id=current_user.id)
    provider = get_filter_provider(settings)

    analyzed = 0
    skipped = 0
    skills_found = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match:
            continue

        row = (await session.execute(
            select(UserJob, RawJob)
            .join(RawJob, UserJob.raw_job_id == RawJob.id)
            .where(UserJob.id == match.job_id, UserJob.user_id == current_user.id)
        )).one_or_none()
        if not row:
            continue
        uj, rj = row

        existing = (await session.execute(
            select(func.count()).select_from(JobSkill).where(JobSkill.job_id == uj.id)
        )).scalar() or 0
        if existing > 0:
            skipped += 1
            continue

        try:
            skills = await provider.extract_skills(rj.title, rj.raw_description)
        except Exception:
            continue

        for skill in skills:
            if not isinstance(skill, str) or not skill.strip():
                continue
            stmt = sqlite_insert(JobSkill).values(
                job_id=uj.id, skill_name=skill.strip()
            ).on_conflict_do_nothing()
            await session.execute(stmt)
            skills_found += 1

        await session.commit()
        analyzed += 1

    return {"analyzed": analyzed, "skipped": skipped, "skills_found": skills_found}


@router.get("/skills")
async def list_skills(session: Session, current_user: CurrentUser):
    rows = (await session.execute(
        select(JobSkill.skill_name, func.count(JobSkill.id).label("count"))
        .join(UserJob, JobSkill.job_id == UserJob.id)
        .where(UserJob.user_id == current_user.id)
        .group_by(JobSkill.skill_name)
        .order_by(func.count(JobSkill.id).desc())
    )).all()

    total_jobs = (await session.execute(
        select(func.count(func.distinct(JobSkill.job_id)))
        .join(UserJob, JobSkill.job_id == UserJob.id)
        .where(UserJob.user_id == current_user.id)
    )).scalar() or 0

    return {
        "skills": [{"name": row.skill_name, "count": row.count} for row in rows],
        "total_jobs_analyzed": total_jobs,
    }


@router.get("/skills/{name}/citations")
async def get_citations(name: str, session: Session, current_user: CurrentUser):
    rows = (await session.execute(
        select(CompanyCatalog.name.label("company_name"), RawJob.title.label("job_title"))
        .select_from(JobSkill)
        .join(UserJob, JobSkill.job_id == UserJob.id)
        .join(RawJob, UserJob.raw_job_id == RawJob.id)
        .join(CompanyCatalog, RawJob.catalog_company_id == CompanyCatalog.id)
        .where(JobSkill.skill_name == name, UserJob.user_id == current_user.id)
        .order_by(JobSkill.created_at.desc())
    )).all()
    return [{"company_name": row.company_name, "job_title": row.job_title} for row in rows]
