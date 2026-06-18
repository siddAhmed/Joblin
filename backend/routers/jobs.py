from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models.company_catalog import CompanyCatalog
from backend.models.match import Match
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
    stmt = (
        select(UserJob, RawJob)
        .join(RawJob, UserJob.raw_job_id == RawJob.id)
        .where(UserJob.user_id == current_user.id)
        .order_by(UserJob.first_seen_at.desc())
    )
    if company_id:
        stmt = stmt.where(RawJob.catalog_company_id == company_id)
    if search:
        stmt = stmt.where(RawJob.title.ilike(f"%{search}%"))
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": uj.id, "company_id": rj.catalog_company_id, "title": rj.title,
            "location": rj.location, "url": rj.url,
            "first_seen_at": uj.first_seen_at, "is_active": rj.is_active,
        }
        for uj, rj in rows
    ]


@router.get("/{job_id}")
async def get_job(job_id: int, session: Session, current_user: CurrentUser):
    row = (await session.execute(
        select(UserJob, RawJob)
        .join(RawJob, UserJob.raw_job_id == RawJob.id)
        .where(UserJob.id == job_id, UserJob.user_id == current_user.id)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    uj, rj = row
    match = (await session.execute(
        select(Match).where(Match.job_id == job_id)
    )).scalar_one_or_none()
    return {
        "id": uj.id, "title": rj.title, "company_id": rj.catalog_company_id,
        "location": rj.location, "url": rj.url,
        "raw_description": rj.raw_description,
        "match": {"score": match.score, "tier": match.tier, "summary": match.summary} if match else None,
    }


@router.post("/{job_id}/dismiss")
async def dismiss_job(job_id: int, session: Session, current_user: CurrentUser):
    row = (await session.execute(
        select(UserJob, RawJob)
        .join(RawJob, UserJob.raw_job_id == RawJob.id)
        .where(UserJob.id == job_id, UserJob.user_id == current_user.id)
    )).one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    uj, rj = row

    match = (await session.execute(
        select(Match).where(Match.job_id == job_id)
    )).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=400, detail="Job has no match to dismiss")

    match.not_interested_at = datetime.now(timezone.utc)

    catalog = await session.get(CompanyCatalog, rj.catalog_company_id)
    fb = FeedbackExample(
        job_id=job_id,
        company_name=catalog.name if catalog else "",
        normalized_title=rj.normalized_title,
        normalized_location=rj.normalized_location,
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
