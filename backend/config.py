import os
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.setting import Setting
from backend.models.user import User

DEFAULTS: dict[str, Any] = {
    "discord_webhook_url": os.getenv("DISCORD_WEBHOOK_URL", ""),
    "discord_mention_type": "none",
    "discord_mention_id": "",
    "criteria": {
        "title_allowlist": "",
        "title_denylist": "intern|junior",
        "location_allowlist": "",
        "location_denylist": "",
        "seniority_allowlist": ["senior", "staff", "principal", "lead", "mid"],
        "exclusion_keywords": [],
        "profile_description": "",
    },
    "schedule_cron": "0 */4 * * *",
    "schedule_preset": "custom",
    "schedule_time": "06:00",
    "schedule_day_of_week": 1,
    "schedule_timezone": "Asia/Kolkata",
    "schedule_custom_mode": "cron",
    "schedule_interval_value": 4,
    "schedule_interval_unit": "hours",
    "staleness_threshold_hours": 4,
    "quarantine_threshold": 3,
    "groq_api_key": os.getenv("GROQ_API_KEY", ""),
    "cerebras_api_key": os.getenv("CEREBRAS_API_KEY", ""),
    "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
    "llm_filter_provider": "groq",
    "llm_summarize_provider": "cerebras",
    "scheduler_enabled": False,
}


async def seed_defaults(session: AsyncSession, user_id: int) -> None:
    user = await session.get(User, user_id)
    if user is None:
        return
    for key, default_value in DEFAULTS.items():
        existing = (await session.execute(
            select(Setting).where(Setting.user_id == user_id, Setting.key == key)
        )).scalar_one_or_none()
        if existing is None:
            session.add(Setting(user_id=user_id, key=key, value=default_value))
    await session.commit()


async def get_setting(session: AsyncSession, key: str, user_id: int) -> Any:
    row = (await session.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == key)
    )).scalar_one_or_none()
    if row is None:
        return DEFAULTS.get(key)
    return row.value


async def set_setting(session: AsyncSession, key: str, value: Any, user_id: int) -> None:
    row = (await session.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == key)
    )).scalar_one_or_none()
    if row is None:
        session.add(Setting(user_id=user_id, key=key, value=value))
    else:
        row.value = value
    await session.commit()


async def get_all_settings(session: AsyncSession, user_id: int) -> dict[str, Any]:
    rows = (await session.execute(
        select(Setting).where(Setting.user_id == user_id)
    )).scalars().all()
    result = dict(DEFAULTS)
    for row in rows:
        result[row.key] = row.value
    return result
