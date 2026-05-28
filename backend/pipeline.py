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
    from backend.scrapers import (
        greenhouse as gh_mod,
        lever as lever_mod,
        ashby as ashby_mod,
        workable as workable_mod,
        smartrecruiters as sr_mod,
        workday as wd_mod,
        crawl4ai as c4ai_mod,
    )

    ats = company.ats_type.value if company.ats_type else "crawl4ai"

    if ats == "greenhouse":
        return await gh_mod.fetch_greenhouse_jobs(company.ats_identifier or "")
    if ats == "lever":
        return await lever_mod.fetch_lever_jobs(company.ats_identifier or "")
    if ats == "ashby":
        return await ashby_mod.fetch_ashby_jobs(company.ats_identifier or "")
    if ats == "workable":
        return await workable_mod.fetch_workable_jobs(company.ats_identifier or "")
    if ats == "smartrecruiters":
        return await sr_mod.fetch_smartrecruiters_jobs(company.ats_identifier or "")
    if ats == "workday":
        return await wd_mod.fetch_workday_jobs(company.custom_api_url or company.careers_url)
    if ats == "custom":
        return await c4ai_mod.fetch_crawl4ai_jobs(
            company.custom_api_url or company.careers_url,
            css_selector=company.css_selector,
        )
    return await c4ai_mod.fetch_crawl4ai_jobs(
        company.careers_url,
        css_selector=company.css_selector,
    )


async def execute_run(run_id: int, session: AsyncSession) -> None:
    from datetime import datetime, timezone
    from sqlalchemy import select as sa_select
    from backend.config import get_all_settings
    from backend.llm.factory import get_filter_provider, get_summarize_provider
    from backend.llm.protocol import CriteriaConfig, FeedbackExample
    from backend.models.match import Match, MatchTier
    from backend.models.feedback import FeedbackExample as FBModel
    from backend.discord import post_match_to_discord

    run = await session.get(Run, run_id)
    if not run:
        return

    settings = await get_all_settings(session)
    criteria = CriteriaConfig.from_dict(settings.get("criteria") or {})
    quarantine_threshold = int(settings.get("quarantine_threshold") or 3)
    is_preview = run.is_preview

    filter_provider = get_filter_provider(settings)
    summarize_provider = get_summarize_provider(settings)

    fb_rows = (await session.execute(
        sa_select(FBModel).order_by(FBModel.dismissed_at.desc()).limit(5)
    )).scalars().all()
    negative_examples = [
        FeedbackExample(
            company_name=r.company_name,
            normalized_title=r.normalized_title,
            normalized_location=r.normalized_location,
            summary=r.summary,
        )
        for r in fb_rows
    ]

    stmt = sa_select(Company).where(Company.is_active == True)
    if run.company_ids:
        stmt = stmt.where(Company.id.in_(run.company_ids))
    companies = (await session.execute(stmt)).scalars().all()

    await _emit(run_id, "run_started", {"run_id": run_id, "company_count": len(companies)})

    total_found = total_heuristic = total_confirmed = total_notified = 0

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

        total_found += len(scraped)
        new_jobs: list[tuple[Job, ScrapedJob]] = []

        for sj in scraped:
            job_id_str = compute_job_id(sj, company.id)
            existing = (await session.execute(
                sa_select(Job).where(Job.company_id == company.id, Job.job_id == job_id_str)
            )).scalar_one_or_none()

            if existing:
                existing.last_seen_at = datetime.now(timezone.utc)
                continue

            job = Job(
                company_id=company.id,
                job_id=job_id_str,
                title=sj.title,
                location=sj.location,
                url=sj.url,
                raw_description=sj.raw_description,
                normalized_title=_normalize(sj.title),
                normalized_location=_normalize(sj.location or ""),
                is_active=True,
            )
            session.add(job)
            await session.flush()
            new_jobs.append((job, sj))

        passed = [(job, sj) for job, sj in new_jobs if passes_heuristic(sj, criteria.__dict__)]
        total_heuristic += len(passed)

        confirmed_count = 0
        notified_count = 0

        for job, sj in passed:
            try:
                filter_result = await filter_provider.filter(
                    title=sj.title,
                    company_name=company.name,
                    location=sj.location,
                    description=sj.raw_description,
                    criteria=criteria,
                    negative_examples=negative_examples,
                )
            except Exception:
                filter_result = None

            if not filter_result or filter_result.score < 0.4:
                continue

            tier = MatchTier.strong if filter_result.score >= 0.7 else MatchTier.borderline

            try:
                summary = await summarize_provider.summarize(
                    title=sj.title,
                    company_name=company.name,
                    description=sj.raw_description,
                    score=filter_result.score,
                )
            except Exception:
                summary = ""

            match = Match(
                job_id=job.id,
                run_id=run_id,
                score=filter_result.score,
                tier=tier,
                summary=summary,
                filter_reasoning=filter_result.reasoning,
                is_preview=is_preview,
            )
            session.add(match)
            await session.flush()
            confirmed_count += 1

            if not is_preview and settings.get("discord_webhook_url"):
                try:
                    await post_match_to_discord(
                        webhook_url=settings["discord_webhook_url"],
                        title=sj.title,
                        company_name=company.name,
                        location=sj.location,
                        score=filter_result.score,
                        tier=tier.value,
                        summary=summary,
                        job_url=sj.url,
                        mention_type=settings.get("discord_mention_type", "none"),
                        mention_id=settings.get("discord_mention_id", ""),
                    )
                    match.notified_at = datetime.now(timezone.utc)
                    notified_count += 1
                except Exception:
                    pass

        await session.commit()
        total_confirmed += confirmed_count
        total_notified += notified_count

        await _emit(run_id, "company_done", {
            "company_id": company.id,
            "jobs_found": len(scraped),
            "passed_heuristic": len(passed),
            "confirmed": confirmed_count,
        })

        result_row.status = CompanyResultStatus.done
        result_row.jobs_found = len(scraped)
        result_row.passed_heuristic = len(passed)
        result_row.confirmed = confirmed_count
        company.quarantine_count = 0

    if total_notified > 0:
        await _emit(run_id, "discord_posted", {"count": total_notified})

    run.total_jobs_found = total_found
    run.total_passed_heuristic = total_heuristic
    run.total_confirmed = total_confirmed
    run.total_notified = total_notified
    run.status = RunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    await _emit(run_id, "run_done", {
        "run_id": run_id, "status": "completed", "total_confirmed": total_confirmed
    })
    _run_queues.pop(run_id, None)
