from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings, set_setting
from backend.database import get_session
from backend.discord import post_match_to_discord

router = APIRouter(prefix="/settings", tags=["settings"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def get_settings(session: Session):
    return await get_all_settings(session)


@router.patch("")
async def update_settings(body: dict, session: Session):
    for key, value in body.items():
        await set_setting(session, key, value)
    return {"updated": list(body.keys())}


@router.post("/discord/test")
async def test_discord(session: Session):
    settings = await get_all_settings(session)
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


@router.post("/criteria/test")
async def test_criteria(req: CriteriaTestRequest, session: Session):
    from backend.llm.factory import get_filter_provider
    from backend.llm.protocol import CriteriaConfig

    settings = await get_all_settings(session)
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
