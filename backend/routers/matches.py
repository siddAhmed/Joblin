from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.discord import post_match_to_discord
from backend.models.match import Match
from backend.models.job import Job
from backend.models.company import Company

router = APIRouter(prefix="/matches", tags=["matches"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_matches(
    session: Session,
    tier: str | None = Query(None),
    company_id: int | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    stmt = select(Match).order_by(Match.created_at.desc())
    if tier:
        stmt = stmt.where(Match.tier == tier)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": m.id, "job_id": m.job_id, "score": m.score, "tier": m.tier,
            "summary": m.summary, "is_preview": m.is_preview,
            "notified_at": m.notified_at, "not_interested_at": m.not_interested_at,
            "created_at": m.created_at,
        }
        for m in rows
    ]


class BulkNotifyRequest(BaseModel):
    match_ids: list[int]


@router.post("/notify")
async def bulk_notify(req: BulkNotifyRequest, session: Session):
    settings = await get_all_settings(session)
    webhook_url = settings.get("discord_webhook_url", "")
    notified = 0

    for match_id in req.match_ids:
        match = await session.get(Match, match_id)
        if not match or match.is_preview:
            continue
        job = await session.get(Job, match.job_id)
        company = await session.get(Company, job.company_id) if job else None
        if not job or not company:
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
