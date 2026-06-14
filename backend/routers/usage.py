from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.models.run import Run
from backend.models.token_usage import TokenUsage

router = APIRouter(prefix="/usage", tags=["usage"])
Session = Annotated[AsyncSession, Depends(get_session)]

PROVIDERS = ["groq", "cerebras", "gemini"]


async def _aggregate(session: AsyncSession, provider: str, since: datetime | None, user_id: int) -> dict:
    stmt = (
        select(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            func.coalesce(func.sum(TokenUsage.prompt_tokens), 0),
            func.coalesce(func.sum(TokenUsage.completion_tokens), 0),
            func.count(TokenUsage.id).filter(TokenUsage.call_type == "filter"),
            func.count(TokenUsage.id).filter(TokenUsage.call_type == "summarize"),
        )
        .join(Run, TokenUsage.run_id == Run.id)
        .where(TokenUsage.provider == provider, Run.user_id == user_id)
    )
    if since:
        stmt = stmt.where(TokenUsage.created_at >= since)
    row = (await session.execute(stmt)).one()
    return {
        "total_tokens": int(row[0]),
        "prompt_tokens": int(row[1]),
        "completion_tokens": int(row[2]),
        "filter_calls": int(row[3]),
        "summarize_calls": int(row[4]),
    }


@router.get("")
async def get_usage(session: Session, current_user: CurrentUser):
    now = datetime.now(timezone.utc)
    cutoff_7d = now - timedelta(days=7)
    cutoff_30d = now - timedelta(days=30)

    providers = {}
    for provider in PROVIDERS:
        all_time = await _aggregate(session, provider, since=None, user_id=current_user.id)
        last_7d = await _aggregate(session, provider, since=cutoff_7d, user_id=current_user.id)
        last_30d = await _aggregate(session, provider, since=cutoff_30d, user_id=current_user.id)
        providers[provider] = {
            "total_tokens_all_time": all_time["total_tokens"],
            "prompt_tokens_all_time": all_time["prompt_tokens"],
            "completion_tokens_all_time": all_time["completion_tokens"],
            "total_tokens_7d": last_7d["total_tokens"],
            "total_tokens_30d": last_30d["total_tokens"],
            "filter_calls": all_time["filter_calls"],
            "summarize_calls": all_time["summarize_calls"],
        }

    recent_stmt = (
        select(
            TokenUsage.run_id,
            TokenUsage.provider,
            func.sum(TokenUsage.total_tokens).label("tokens"),
        )
        .join(Run, TokenUsage.run_id == Run.id)
        .where(Run.user_id == current_user.id)
        .group_by(TokenUsage.run_id, TokenUsage.provider)
        .order_by(TokenUsage.run_id.desc())
        .limit(50)
    )
    recent_rows = (await session.execute(recent_stmt)).all()

    run_map: dict[int, dict] = {}
    for run_id, provider, tokens in recent_rows:
        if run_id not in run_map:
            run_map[run_id] = {"run_id": run_id, "groq": 0, "cerebras": 0, "gemini": 0}
        run_map[run_id][provider] = int(tokens)

    return {
        "providers": providers,
        "recent_runs": sorted(run_map.values(), key=lambda r: r["run_id"], reverse=True),
    }
