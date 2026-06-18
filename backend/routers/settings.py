import asyncio
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings, set_setting
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.discord import post_match_to_discord
from cerebras.cloud.sdk import AsyncCerebras
from google import genai
from groq import AsyncGroq

router = APIRouter(prefix="/settings", tags=["settings"])
Session = Annotated[AsyncSession, Depends(get_session)]

SCHEDULE_KEYS = {"schedule_cron", "scheduler_enabled", "schedule_timezone"}


@router.get("")
async def get_settings(session: Session, current_user: CurrentUser):
    return await get_all_settings(session, user_id=current_user.id)


@router.patch("")
async def update_settings(request: Request, body: dict, session: Session, current_user: CurrentUser):
    for key, value in body.items():
        await set_setting(session, key, value, user_id=current_user.id)

    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is not None and SCHEDULE_KEYS & set(body.keys()):
        from backend.scheduler import sync_user_schedule
        await sync_user_schedule(scheduler, current_user.id)

    return {"updated": list(body.keys())}


@router.post("/discord/test")
async def test_discord(session: Session, current_user: CurrentUser):
    settings = await get_all_settings(session, user_id=current_user.id)
    webhook_url = settings.get("discord_webhook_url", "")
    if not webhook_url:
        return {"error": "No webhook URL configured"}
    try:
        await post_match_to_discord(
            webhook_url=webhook_url,
            title="Joblin test notification",
            company_name="Joblin",
            location="Self-hosted",
            score=1.0,
            tier="strong",
            summary="This is a test notification from Joblin.",
            job_url="https://github.com",
            mention_type="none",
            mention_id="",
        )
        return {"status": "sent"}
    except Exception as exc:
        return {"error": str(exc)}


class CriteriaTestRequest(BaseModel):
    description: str


class ValidateKeysRequest(BaseModel):
    groq_api_key: str = ""
    cerebras_api_key: str = ""
    gemini_api_key: str = ""


class KeyResult(BaseModel):
    valid: bool
    error: Optional[str] = None


@router.post("/criteria/test")
async def test_criteria(req: CriteriaTestRequest, session: Session, current_user: CurrentUser):
    from backend.llm.factory import get_filter_provider
    from backend.llm.protocol import CriteriaConfig

    settings = await get_all_settings(session, user_id=current_user.id)
    criteria = CriteriaConfig.from_dict(settings.get("criteria") or {})
    provider = get_filter_provider(settings)
    try:
        result = await provider.filter(
            title="Test Job",
            company_name="Test Company",
            location=None,
            description=req.description,
            criteria=criteria,
            negative_examples=[],
        )
        return {"score": result.score, "reasoning": result.reasoning}
    except Exception as exc:
        return {"error": str(exc)}


async def _check_groq(api_key: str) -> KeyResult:
    try:
        client = AsyncGroq(api_key=api_key)
        await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return KeyResult(valid=True)
    except Exception as exc:
        return KeyResult(valid=False, error=(str(exc) or "Could not reach provider")[:200])


async def _check_cerebras(api_key: str) -> KeyResult:
    try:
        client = AsyncCerebras(api_key=api_key)
        await client.chat.completions.create(
            model="gpt-oss-120b",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1,
        )
        return KeyResult(valid=True)
    except Exception as exc:
        return KeyResult(valid=False, error=(str(exc) or "Could not reach provider")[:200])


async def _check_gemini(api_key: str) -> KeyResult:
    try:
        client = genai.Client(api_key=api_key)
        await client.aio.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents="hi",
        )
        return KeyResult(valid=True)
    except Exception as exc:
        return KeyResult(valid=False, error=(str(exc) or "Could not reach provider")[:200])


@router.post("/validate-keys")
async def validate_keys(body: ValidateKeysRequest, current_user: CurrentUser):
    checks: dict[str, object] = {}
    if body.groq_api_key:
        checks["groq"] = _check_groq(body.groq_api_key)
    if body.cerebras_api_key:
        checks["cerebras"] = _check_cerebras(body.cerebras_api_key)
    if body.gemini_api_key:
        checks["gemini"] = _check_gemini(body.gemini_api_key)

    if not checks:
        return JSONResponse(content={}, status_code=200)

    results_list = await asyncio.gather(*checks.values())
    results: dict[str, KeyResult] = dict(zip(checks.keys(), results_list))

    any_invalid = any(not r.valid for r in results.values())
    return JSONResponse(
        content={k: v.model_dump() for k, v in results.items()},
        status_code=422 if any_invalid else 200,
    )
