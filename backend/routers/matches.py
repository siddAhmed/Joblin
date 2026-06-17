from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.discord import post_match_to_discord
from backend.models.match import Match
from backend.models.job import Job
from backend.models.company import Company

router = APIRouter(prefix="/matches", tags=["matches"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_matches(
    session: Session,
    current_user: CurrentUser,
    tier: str | None = Query(None),
    company_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = (
        select(Match, Job, Company)
        .join(Job, Match.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(Company.user_id == current_user.id)
        .where(Match.hidden_at == None)
        .order_by(Match.created_at.desc())
    )
    if tier:
        stmt = stmt.where(Match.tier == tier)
    if company_id:
        stmt = stmt.where(Company.id == company_id)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": m.id, "job_id": m.job_id, "score": m.score, "tier": m.tier,
            "summary": m.summary, "is_preview": m.is_preview,
            "notified_at": m.notified_at, "not_interested_at": m.not_interested_at,
            "created_at": m.created_at,
            "job_title": j.title,
            "company_name": c.name,
            "location": j.location,
            "job_url": j.url,
        }
        for m, j, c in rows
    ]


class BulkNotifyRequest(BaseModel):
    match_ids: list[int]


@router.post("/notify")
async def bulk_notify(req: BulkNotifyRequest, session: Session, current_user: CurrentUser):
    settings = await get_all_settings(session, user_id=current_user.id)
    webhook_url = settings.get("discord_webhook_url", "")
    notified = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match or match.is_preview or match.hidden_at:
            continue
        job = await session.get(Job, match.job_id)
        if not job or job.user_id != current_user.id:
            continue
        company = await session.get(Company, job.company_id) if job else None
        if not company:
            continue
        try:
            await post_match_to_discord(
                webhook_url=webhook_url,
                title=job.title,
                company_name=company.name,
                location=job.location,
                score=match.score,
                tier=match.tier.value,
                summary=match.summary,
                job_url=job.url,
                mention_type=settings.get("discord_mention_type", "none"),
                mention_id=settings.get("discord_mention_id", ""),
            )
            match.notified_at = datetime.now(timezone.utc)
            notified += 1
        except Exception:
            pass

    await session.commit()
    return {"notified": notified}


@router.post("/{match_id}/dismiss")
async def dismiss_match(match_id: int, session: Session, current_user: CurrentUser):
    match = (await session.execute(
        select(Match)
        .join(Job, Match.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(Match.id == match_id, Company.user_id == current_user.id)
    )).scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    match.hidden_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "dismissed"}
