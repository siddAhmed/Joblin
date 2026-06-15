from datetime import datetime, timezone, timedelta

from apscheduler import AsyncScheduler, ConflictPolicy, ScheduleLookupError
from apscheduler.triggers.cron import CronTrigger

from backend.database import AsyncSessionLocal
from backend.config import get_setting


async def _run_scrape_job(user_id: int) -> None:
    from backend.models.run import Run, RunStatus
    from backend.pipeline import execute_run
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        staleness_hours = float(await get_setting(session, "staleness_threshold_hours", user_id=user_id) or 4)
        # SQLAlchemy strips tz on write to SQLite — completed_at comes back naive UTC,
        # so cutoff must also be naive UTC for the comparison to work.
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=staleness_hours)
        last_run = (await session.execute(
            select(Run)
            .where(Run.status == RunStatus.completed, Run.user_id == user_id)
            .order_by(Run.completed_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if last_run and last_run.completed_at and last_run.completed_at > cutoff:
            return

        run = Run(is_preview=False, user_id=user_id)
        session.add(run)
        await session.commit()
        await session.refresh(run)

    async with AsyncSessionLocal() as session:
        await execute_run(run.id, session)


async def _schedule_user_job(scheduler: AsyncScheduler, user_id: int) -> None:
    async with AsyncSessionLocal() as session:
        cron_expr = str(await get_setting(session, "schedule_cron", user_id=user_id) or "0 */4 * * *")
        enabled = bool(await get_setting(session, "scheduler_enabled", user_id=user_id) or False)
        tz = str(await get_setting(session, "schedule_timezone", user_id=user_id) or "UTC")

    job_id = f"scrape_cron_{user_id}"

    if not enabled:
        try:
            await scheduler.remove_schedule(job_id)
        except ScheduleLookupError:
            pass
        return

    parts = cron_expr.split()
    if len(parts) == 5:
        minute, hour, day, month, day_of_week = parts
    else:
        minute, hour, day, month, day_of_week = "0", "*/4", "*", "*", "*"

    await scheduler.add_schedule(
        _run_scrape_job,
        CronTrigger(minute=minute, hour=hour, day=day, month=month, day_of_week=day_of_week, timezone=tz),
        id=job_id,
        kwargs={"user_id": user_id},
        conflict_policy=ConflictPolicy.replace,
    )


async def start_scheduler(scheduler: AsyncScheduler) -> None:
    from backend.models.user import User
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        user_ids = [u.id for u in (await session.execute(select(User))).scalars().all()]

    for user_id in user_ids:
        await _schedule_user_job(scheduler, user_id)


async def sync_user_schedule(scheduler: AsyncScheduler, user_id: int) -> None:
    await _schedule_user_job(scheduler, user_id)
