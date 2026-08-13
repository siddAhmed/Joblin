import asyncio
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_setting, get_all_settings
from backend.models.company_catalog import CompanyCatalog
from backend.models.user_company import UserCompany
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models.run import Run, RunCompanyResult, RunStatus, CompanyResultStatus
from backend.scrapers.base import ScrapedJob
from backend.scrapers.heuristics import passes_heuristic
from backend.scrapers.job_id import compute_job_id

_run_queues: dict[int, asyncio.Queue] = {}
_cancelled_runs: set[int] = set()


def request_cancel_run(run_id: int) -> None:
    _cancelled_runs.add(run_id)


def get_run_queue(run_id: int) -> asyncio.Queue:
    if run_id not in _run_queues:
        _run_queues[run_id] = asyncio.Queue()
    return _run_queues[run_id]


async def _emit(run_id: int, event_type: str, data: dict) -> None:
    q = get_run_queue(run_id)
    await q.put({"type": event_type, "data": data})


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def _detect_seniority(normalized_title: str) -> str | None:
    for level in ("principal", "staff", "senior", "lead", "mid", "junior", "intern"):
        if level in normalized_title:
            return level
    return None


async def _fetch_jobs(company: CompanyCatalog) -> list[ScrapedJob]:
    from backend.scrapers import (
        greenhouse as gh_mod, lever as lever_mod, ashby as ashby_mod,
        workable as workable_mod, smartrecruiters as sr_mod,
        workday as wd_mod, crawl4ai as c4ai_mod,
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
        company.careers_url, css_selector=company.css_selector
    )


async def _scrape_phase(
    run_id: int,
    catalog_companies: list[CompanyCatalog],
    is_manual: bool,
    cache_hours: int,
    quarantine_threshold: int,
    session: AsyncSession,
) -> tuple[dict[int, int], dict[int, str]]:
    """Scrape companies, upsert raw_jobs. Returns ({catalog_company_id: jobs_found count}, {catalog_company_id: error_message})."""
    now = datetime.now(timezone.utc)
    counts: dict[int, int] = {}
    failed_ids: dict[int, str] = {}

    for company in catalog_companies:
        if not is_manual and company.last_scraped_at:
            age_hours = (now - company.last_scraped_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
            if age_hours < cache_hours:
                # Use cached data; count existing active raw_jobs for this company
                existing_count = len((await session.execute(
                    select(RawJob).where(
                        RawJob.catalog_company_id == company.id,
                        RawJob.is_active == True,
                    )
                )).scalars().all())
                counts[company.id] = existing_count
                await _emit(run_id, "company_skipped_cache", {
                    "company_id": company.id, "company_name": company.name,
                    "cached_jobs": existing_count,
                })
                continue

        try:
            scraped = await asyncio.wait_for(_fetch_jobs(company), timeout=60.0)
        except asyncio.TimeoutError:
            msg = "scraper timed out after 60s"
            company.quarantine_count += 1
            if company.quarantine_count >= quarantine_threshold:
                company.quarantined_at = now
                company.quarantine_reason = msg
            await session.commit()
            await _emit(run_id, "company_failed", {"company_id": company.id, "error": msg})
            counts[company.id] = 0
            failed_ids[company.id] = msg
            continue
        except Exception as exc:
            company.quarantine_count += 1
            if company.quarantine_count >= quarantine_threshold:
                company.quarantined_at = now
                company.quarantine_reason = str(exc)
            await session.commit()
            await _emit(run_id, "company_failed", {"company_id": company.id, "error": str(exc)})
            counts[company.id] = 0
            failed_ids[company.id] = str(exc)
            continue

        for sj in scraped:
            job_id_str = compute_job_id(sj, company.id)
            normalized_title = _normalize(sj.title)
            normalized_location = _normalize(sj.location or "")
            seniority = _detect_seniority(normalized_title)

            existing_raw = (await session.execute(
                select(RawJob).where(
                    RawJob.catalog_company_id == company.id,
                    RawJob.job_id == job_id_str,
                )
            )).scalar_one_or_none()

            if existing_raw:
                existing_raw.last_seen_at = now
                existing_raw.is_active = True
                if sj.raw_description:
                    existing_raw.raw_description = sj.raw_description
            else:
                session.add(RawJob(
                    catalog_company_id=company.id,
                    job_id=job_id_str,
                    title=sj.title,
                    location=sj.location,
                    url=sj.url,
                    raw_description=sj.raw_description or "",
                    normalized_title=normalized_title,
                    normalized_location=normalized_location,
                    seniority=seniority,
                    is_active=True,
                ))

        company.last_scraped_at = now
        company.quarantine_count = 0
        await session.commit()
        counts[company.id] = len(scraped)

    return counts, failed_ids


async def _process_phase(
    run_id: int,
    user_id: int,
    is_preview: bool,
    is_seeding_run: bool,
    catalog_company_ids: list[int],
    settings: dict,
    session: AsyncSession,
) -> tuple[int, int, int, int, dict[int, tuple[int, int]]]:
    """Per-user heuristic + LLM phase. Returns (new_jobs, passed_heuristic, confirmed, notified, company_stats)."""
    from backend.llm.factory import get_filter_provider, get_summarize_provider
    from backend.llm.protocol import CriteriaConfig, FeedbackExample
    from backend.models.match import Match, MatchTier
    from backend.models.feedback import FeedbackExample as FBModel
    from backend.models.token_usage import TokenUsage
    from backend.discord import post_match_to_discord

    def _provider_name(provider) -> str:
        return type(provider).__name__.lower().replace("adapter", "")

    criteria = CriteriaConfig.from_dict(settings.get("criteria") or {})
    filter_provider = get_filter_provider(settings)
    summarize_provider = get_summarize_provider(settings)

    fb_rows = (await session.execute(
        select(FBModel)
        .where(FBModel.user_id == user_id)
        .order_by(FBModel.dismissed_at.desc())
        .limit(5)
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

    # Get raw_jobs for user's companies not yet processed (or preview-only) by this user
    if is_preview:
        freshness_filter = UserJob.id == None
    else:
        freshness_filter = or_(UserJob.id == None, UserJob.preview_only == True)

    new_raw_jobs = (await session.execute(
        select(RawJob, CompanyCatalog)
        .join(CompanyCatalog, RawJob.catalog_company_id == CompanyCatalog.id)
        .outerjoin(
            UserJob,
            and_(UserJob.raw_job_id == RawJob.id, UserJob.user_id == user_id),
        )
        .where(
            RawJob.catalog_company_id.in_(catalog_company_ids),
            RawJob.is_active == True,
            freshness_filter,
        )
    )).all()

    new_count = len(new_raw_jobs)
    passed_count = confirmed_count = notified_count = 0
    now = datetime.now(timezone.utc)
    company_stats: dict[int, list[int]] = {}  # catalog_company_id -> [passed, confirmed]

    for raw_job, catalog_company in new_raw_jobs:
        # Fix I1: check for cancellation inside the processing loop
        if run_id in _cancelled_runs:
            break

        cat_id = catalog_company.id
        if cat_id not in company_stats:
            company_stats[cat_id] = [0, 0]

        passed = passes_heuristic(raw_job, criteria.__dict__)

        # Fix C1: promote preview-only UserJob rows on real runs instead of creating duplicates
        existing_uj = (await session.execute(
            select(UserJob).where(UserJob.raw_job_id == raw_job.id, UserJob.user_id == user_id)
        )).scalar_one_or_none()

        if existing_uj:
            # Preview-indexed job being promoted by a real run
            existing_uj.preview_only = False
            existing_uj.run_id = run_id
            user_job = existing_uj
        else:
            user_job = UserJob(
                user_id=user_id,
                raw_job_id=raw_job.id,
                run_id=run_id,
                passed_heuristic=passed,
                preview_only=is_preview,
            )
            session.add(user_job)

        # Commit UserJob before any LLM calls so the write lock is released
        # during slow I/O. expire_on_commit=False keeps user_job.id accessible.
        await session.commit()

        if not passed:
            continue

        passed_count += 1
        company_stats[cat_id][0] += 1

        # Fix C1: if promoting a preview job that already has a confirmed match, just flip is_preview
        existing_match = (await session.execute(
            select(Match).where(Match.job_id == user_job.id)
        )).scalar_one_or_none()

        if existing_match and existing_match.is_preview and not is_preview:
            existing_match.is_preview = False
            await session.commit()
            confirmed_count += 1
            company_stats[cat_id][1] += 1
            continue

        # LLM filter -- write lock is NOT held during this call
        try:
            filter_result = await filter_provider.filter(
                title=raw_job.title,
                company_name=catalog_company.name,
                location=raw_job.location,
                description=raw_job.raw_description,
                criteria=criteria,
                negative_examples=negative_examples,
            )
        except Exception as llm_exc:
            logging.warning(
                "LLM filter failed for job %s (%s): %s: %s",
                raw_job.title, catalog_company.name, type(llm_exc).__name__, llm_exc
            )
            filter_result = None

        if hasattr(filter_provider, "last_usage") and filter_provider.last_usage.get("total_tokens", 0) > 0:
            session.add(TokenUsage(
                run_id=run_id, provider=_provider_name(filter_provider), call_type="filter",
                prompt_tokens=filter_provider.last_usage["prompt_tokens"],
                completion_tokens=filter_provider.last_usage["completion_tokens"],
                total_tokens=filter_provider.last_usage["total_tokens"],
            ))

        if not filter_result or filter_result.score < 0.4:
            await session.commit()  # persist TokenUsage before moving on
            continue

        tier = MatchTier.strong if filter_result.score >= 0.7 else MatchTier.borderline

        # LLM summarize -- write lock is NOT held during this call
        try:
            summary = await summarize_provider.summarize(
                title=raw_job.title, company_name=catalog_company.name,
                description=raw_job.raw_description, score=filter_result.score,
            )
        except Exception as llm_exc:
            logging.warning(
                "LLM summarize failed for job %s (%s): %s: %s",
                raw_job.title, catalog_company.name, type(llm_exc).__name__, llm_exc
            )
            summary = ""

        if hasattr(summarize_provider, "last_usage") and summarize_provider.last_usage.get("total_tokens", 0) > 0:
            session.add(TokenUsage(
                run_id=run_id, provider=_provider_name(summarize_provider), call_type="summarize",
                prompt_tokens=summarize_provider.last_usage["prompt_tokens"],
                completion_tokens=summarize_provider.last_usage["completion_tokens"],
                total_tokens=summarize_provider.last_usage["total_tokens"],
            ))

        if existing_match:
            if existing_match.is_preview:
                existing_match.is_preview = False
            match = existing_match
        else:
            match = Match(
                job_id=user_job.id,
                run_id=run_id,
                score=filter_result.score,
                tier=tier,
                summary=summary,
                filter_reasoning=filter_result.reasoning,
                is_preview=is_preview,
            )
            session.add(match)

        confirmed_count += 1
        company_stats[cat_id][1] += 1

        if not is_preview and not is_seeding_run and settings.get("discord_webhook_url"):
            try:
                await post_match_to_discord(
                    webhook_url=settings["discord_webhook_url"],
                    title=raw_job.title,
                    company_name=catalog_company.name,
                    location=raw_job.location,
                    score=filter_result.score,
                    tier=tier.value,
                    summary=summary,
                    job_url=raw_job.url,
                    mention_type=settings.get("discord_mention_type", "none"),
                    mention_id=settings.get("discord_mention_id", ""),
                )
                match.notified_at = now
                notified_count += 1
            except Exception:
                pass

        await session.commit()  # persist Match + TokenUsage for this job

    company_stats_tuples: dict[int, tuple[int, int]] = {k: (v[0], v[1]) for k, v in company_stats.items()}
    return new_count, passed_count, confirmed_count, notified_count, company_stats_tuples


async def execute_run(run_id: int, session: AsyncSession, is_manual: bool = True) -> None:
    run = await session.get(Run, run_id)
    if not run:
        return

    user_id = run.user_id
    settings = await get_all_settings(session, user_id=user_id)
    quarantine_threshold = int(settings.get("quarantine_threshold") or 3)
    is_preview = run.is_preview

    # Admin-configurable cache window; read from admin (user_id=1) settings
    try:
        cache_hours = int(await get_setting(session, "global_scrape_cache_hours", user_id=1) or 2)
    except Exception:
        cache_hours = 2

    # Resolve user's companies -> catalog entries
    stmt = (
        select(UserCompany, CompanyCatalog)
        .join(CompanyCatalog, UserCompany.catalog_id == CompanyCatalog.id)
        .where(
            UserCompany.user_id == user_id,
            UserCompany.is_active == True,
            CompanyCatalog.is_active == True,
            CompanyCatalog.quarantined_at == None,
        )
    )
    if run.company_ids:
        stmt = stmt.where(UserCompany.id.in_(run.company_ids))

    uc_rows = (await session.execute(stmt)).all()
    catalog_companies = [cat for _uc, cat in uc_rows]
    catalog_company_ids = [cat.id for cat in catalog_companies]

    # Seeding check: no existing user_jobs for this user
    from sqlalchemy import func as sa_func
    existing_count = (await session.execute(
        select(sa_func.count()).select_from(UserJob).where(UserJob.user_id == user_id)
    )).scalar() or 0
    is_seeding_run = existing_count == 0

    await _emit(run_id, "run_started", {
        "run_id": run_id, "company_count": len(catalog_companies), "seeding": is_seeding_run
    })

    # Phase 1: scrape
    scrape_counts, failed = await _scrape_phase(
        run_id=run_id,
        catalog_companies=catalog_companies,
        is_manual=is_manual,
        cache_hours=cache_hours,
        quarantine_threshold=quarantine_threshold,
        session=session,
    )

    if run_id in _cancelled_runs:
        _cancelled_runs.discard(run_id)
        run.status = RunStatus.cancelled
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await _emit(run_id, "run_done", {"run_id": run_id, "status": "cancelled", "total_confirmed": 0})
        _run_queues.pop(run_id, None)
        return

    total_found = sum(scrape_counts.values())

    # Phase 2: per-user process
    new_jobs, passed_heuristic, confirmed, notified, company_stats = await _process_phase(
        run_id=run_id,
        user_id=user_id,
        is_preview=is_preview,
        is_seeding_run=is_seeding_run,
        catalog_company_ids=catalog_company_ids,
        settings=settings,
        session=session,
    )

    # Fix I1: check for cancellation after the processing phase
    if run_id in _cancelled_runs:
        _cancelled_runs.discard(run_id)
        run.status = RunStatus.cancelled
        run.completed_at = datetime.now(timezone.utc)
        await session.commit()
        await _emit(run_id, "run_done", {"run_id": run_id, "status": "cancelled", "total_confirmed": confirmed})
        _run_queues.pop(run_id, None)
        return

    # Update run_company_results -- Fix C2: populate passed_heuristic and confirmed per company
    for cat in catalog_companies:
        if cat.id in failed:
            row_status = CompanyResultStatus.failed
            row_error = failed[cat.id]
        else:
            row_status = CompanyResultStatus.done
            row_error = None
        cat_passed, cat_confirmed = company_stats.get(cat.id, (0, 0))
        result_row = RunCompanyResult(
            run_id=run_id,
            company_id=cat.id,
            status=row_status,
            jobs_found=scrape_counts.get(cat.id, 0),
            passed_heuristic=cat_passed,
            confirmed=cat_confirmed,
            error_message=row_error,
        )
        session.add(result_row)
        await _emit(run_id, "company_done", {
            "company_id": cat.id, "jobs_found": scrape_counts.get(cat.id, 0),
        })

    if notified > 0:
        await _emit(run_id, "discord_posted", {"count": notified})

    run.total_jobs_found = total_found
    run.total_new_jobs = new_jobs
    run.total_passed_heuristic = passed_heuristic
    run.total_confirmed = confirmed
    run.total_notified = notified
    run.status = RunStatus.completed
    run.completed_at = datetime.now(timezone.utc)
    await session.commit()

    await _emit(run_id, "run_done", {
        "run_id": run_id, "status": "completed",
        "total_confirmed": confirmed, "seeding": is_seeding_run,
    })
    _run_queues.pop(run_id, None)
