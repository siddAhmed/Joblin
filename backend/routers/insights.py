from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.llm.factory import get_filter_provider
from backend.models.company import Company
from backend.models.job import Job
from backend.models.job_skill import JobSkill
from backend.models.match import Match

router = APIRouter(prefix="/insights", tags=["insights"])
Session = Annotated[AsyncSession, Depends(get_session)]


class AnalyzeRequest(BaseModel):
    match_ids: list[int]


@router.post("/analyze")
async def analyze_skills(req: AnalyzeRequest, session: Session):
    settings = await get_all_settings(session)
    provider = get_filter_provider(settings)

    analyzed = 0
    skipped = 0
    skills_found = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match:
            continue

        job = await session.get(Job, match.job_id)
        if not job:
            continue

        existing = (await session.execute(
            select(func.count()).select_from(JobSkill).where(JobSkill.job_id == job.id)
        )).scalar() or 0
        if existing > 0:
            skipped += 1
            continue

        try:
            skills = await provider.extract_skills(job.title, job.raw_description)
        except Exception:
            continue

        for skill in skills:
            if not isinstance(skill, str) or not skill.strip():
                continue
            stmt = sqlite_insert(JobSkill).values(
                job_id=job.id, skill_name=skill.strip()
            ).on_conflict_do_nothing()
            await session.execute(stmt)
            skills_found += 1

        await session.commit()
        analyzed += 1

    return {"analyzed": analyzed, "skipped": skipped, "skills_found": skills_found}


@router.get("/skills")
async def list_skills(session: Session):
    rows = (await session.execute(
        select(JobSkill.skill_name, func.count(JobSkill.id).label("count"))
        .group_by(JobSkill.skill_name)
        .order_by(func.count(JobSkill.id).desc())
    )).all()

    total_jobs = (await session.execute(
        select(func.count(func.distinct(JobSkill.job_id)))
    )).scalar() or 0

    return {
        "skills": [{"name": row.skill_name, "count": row.count} for row in rows],
        "total_jobs_analyzed": total_jobs,
    }


@router.get("/skills/{name}/citations")
async def get_citations(name: str, session: Session):
    rows = (await session.execute(
        select(Company.name.label("company_name"), Job.title.label("job_title"))
        .select_from(JobSkill)
        .join(Job, JobSkill.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(JobSkill.skill_name == name)
        .order_by(JobSkill.created_at.desc())
    )).all()
    return [{"company_name": row.company_name, "job_title": row.job_title} for row in rows]
