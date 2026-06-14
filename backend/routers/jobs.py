from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models.job import Job
from backend.models.match import Match
from backend.models.company import Company
from backend.models.feedback import FeedbackExample

router = APIRouter(prefix="/jobs", tags=["jobs"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_jobs(
    session: Session,
    current_user: CurrentUser,
    company_id: int | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = select(Job).where(Job.user_id == current_user.id).order_by(Job.first_seen_at.desc())
    if company_id:
        stmt = stmt.where(Job.company_id == company_id)
    if search:
        stmt = stmt.where(Job.title.ilike(f"%{search}%"))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": j.id, "company_id": j.company_id, "title": j.title,
            "location": j.location, "url": j.url,
            "first_seen_at": j.first_seen_at, "is_active": j.is_active,
        }
        for j in rows
    ]


@router.get("/{job_id}")
async def get_job(job_id: int, session: Session, current_user: CurrentUser):
    job = (await session.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    match = (await session.execute(
        select(Match).where(Match.job_id == job_id)
    )).scalar_one_or_none()
    return {
        "id": job.id, "title": job.title, "company_id": job.company_id,
        "location": job.location, "url": job.url,
        "raw_description": job.raw_description,
        "match": {"score": match.score, "tier": match.tier, "summary": match.summary} if match else None,
    }


@router.post("/{job_id}/dismiss")
async def dismiss_job(job_id: int, session: Session, current_user: CurrentUser):
    job = (await session.execute(
        select(Job).where(Job.id == job_id, Job.user_id == current_user.id)
    )).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    match = (await session.execute(
        select(Match).where(Match.job_id == job_id)
    )).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=400, detail="Job has no match to dismiss")

    match.not_interested_at = datetime.now(timezone.utc)

    company = await session.get(Company, job.company_id)
    fb = FeedbackExample(
        job_id=job_id,
        company_name=company.name if company else "",
        normalized_title=job.normalized_title,
        normalized_location=job.normalized_location,
        summary=match.summary,
        user_id=current_user.id,
    )
    session.add(fb)

    all_fb = (await session.execute(
        select(FeedbackExample)
        .where(FeedbackExample.user_id == current_user.id)
        .order_by(FeedbackExample.dismissed_at.desc())
    )).scalars().all()
    for old in all_fb[50:]:
        await session.delete(old)

    await session.commit()
    return {"status": "dismissed"}
