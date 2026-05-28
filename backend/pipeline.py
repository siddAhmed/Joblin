import asyncio
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_setting
from backend.models.company import Company
from backend.models.job import Job
from backend.models.run import Run, RunCompanyResult, RunStatus, CompanyResultStatus
from backend.scrapers.base import ScrapedJob
from backend.scrapers.heuristics import passes_heuristic
from backend.scrapers.job_id import compute_job_id

_run_queues: dict[int, asyncio.Queue] = {}


def get_run_queue(run_id: int) -> asyncio.Queue:
    if run_id not in _run_queues:
        _run_queues[run_id] = asyncio.Queue()
    return _run_queues[run_id]


async def _emit(run_id: int, event_type: str, data: dict) -> None:
    q = get_run_queue(run_id)
    await q.put({"type": event_type, "data": data})


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


async def _fetch_jobs(company: Company) -> list[ScrapedJob]:
    from backend.scrapers import greenhouse as gh_mod

    if company.ats_type.value == "greenhouse":
        return await gh_mod.fetch_greenhouse_jobs(company.ats_identifier or "")
    return []


async def execute_run(run_id: int, session: AsyncSession) -> None:
    run = await session.get(Run, run_id)
    if not run:
        return

    criteria_setting = await get_setting(session, "criteria")
    quarantine_threshold = int(await get_setting(session, "quarantine_threshold") or 3)

    stmt = select(Company).where(Company.is_active == True)
    if run.company_ids:
        stmt = stmt.where(Company.id.in_(run.company_ids))
    companies = (await session.execute(stmt)).scalars().all()

    await _emit(run_id, "run_started", {"run_id": run_id, "company_count": len(companies)})

    total_found = total_heuristic = total_confirmed = 0

    for company in companies:
        result_row = RunCompanyResult(
            run_id=run_id, company_id=company.id, status=CompanyResultStatus.scraping
        )
        session.add(result_row)
        await session.commit()
        await session.refresh(result_row)

        await _emit(run_id, "company_scraping", {"company_id": company.id, "company_name": company.name})

        try:
            scraped = await _fetch_jobs(company)
        except Exception as exc:
            company.quarantine_count += 1
            if company.quarantine_count >= quarantine_threshold:
                company.quarantined_at = datetime.now(timezone.utc)
                company.quarantine_reason = str(exc)
            result_row.status = CompanyResultStatus.failed
            result_row.error_message = str(exc)
            await session.commit()
            await _emit(run_id, "company_failed", {"company_id": company.id, "error": str(exc)})
            continue

        found_count = len(scraped)
        total_found += found_count

        new_jobs: list[tuple[Job, ScrapedJob]] = []
        for sj in scraped:
            job_id_str = compute_job_id(sj, company.id)
            existing = (
                await session.execute(
                    select(Job).where(Job.company_id == company.id, Job.job_id == job_id_str)
                )
            ).scalar_one_or_none()

            if existing:
                existing.last_seen_at = datetime.now(timezone.utc)
                continue

            normalized_title = _normalize(sj.title)
            job = Job(
                company_id=company.id,
                job_id=job_id_str,
                title=sj.title,
                location=sj.location,
                url=sj.url,
                raw_description=sj.raw_description,
                normalized_title=normalized_title,
                normalized_location=_normalize(sj.location or ""),
                is_active=True,
            )
            session.add(job)
            await session.flush()
            new_jobs.append((job, sj))

        passed = [(job, sj) for job, sj in new_jobs if passes_heuristic(sj, criteria_setting or {})]
        total_heuristic += len(passed)

        await _emit(run_id, "company_done", {
            "company_id": company.id,
            "jobs_found": found_count,
            "passed_heuristic": len(passed),
            "confirmed": 0,
        })

        result_row.status = CompanyResultStatus.done
        result_row.jobs_found = found_count
        result_row.passed_heuristic = len(passed)
        company.quarantine_count = 0

    run.total_jobs_found = total_found
    run.total_passed_heuristic = total_heuristic
    run.total_confirmed = total_confirmed
    run.status = RunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    await _emit(run_id, "run_done", {"run_id": run_id, "status": "completed", "total_confirmed": total_confirmed})
    _run_queues.pop(run_id, None)
