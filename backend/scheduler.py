from datetime import datetime, timezone, timedelta

from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.triggers.cron import CronTrigger

from backend.database import AsyncSessionLocal
from backend.config import get_setting


async def _run_scrape_job() -> None:
    from backend.models.run import Run, RunStatus
    from backend.pipeline import execute_run
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        staleness_hours = float(await get_setting(session, "staleness_threshold_hours", user_id=1) or 4)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=staleness_hours)
        last_run = (await session.execute(
            select(Run)
            .where(Run.status == RunStatus.completed, Run.user_id == 1)
            .order_by(Run.completed_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if last_run and last_run.completed_at and last_run.completed_at > cutoff:
            return

        run = Run(is_preview=False, user_id=1)
        session.add(run)
        await session.commit()
        await session.refresh(run)

    async with AsyncSessionLocal() as session:
        await execute_run(run.id, session)


async def start_scheduler(scheduler: AsyncScheduler) -> None:
    async with AsyncSessionLocal() as session:
        cron_expr = await get_setting(session, "schedule_cron", user_id=1) or "0 */4 * * *"
        enabled = await get_setting(session, "scheduler_enabled", user_id=1) or False

    if not enabled:
        return

    parts = cron_expr.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
    else:
        minute, hour, day, month, day_of_week = "0", "*/4", "*", "*", "*"

    await scheduler.add_schedule(
        _run_scrape_job,
        CronTrigger(
            minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week
        ),
        id="scrape_cron",
        conflict_policy=ConflictPolicy.replace,
    )
