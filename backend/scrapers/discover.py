import asyncio
import json
import re
from urllib.parse import quote_plus

import anthropic
from sqlalchemy import select

try:
    from crawl4ai import AsyncWebCrawler as _AsyncWebCrawler
except ModuleNotFoundError:
    _AsyncWebCrawler = None  # type: ignore[assignment,misc]

from backend.data.default_companies import DEFAULT_COMPANIES
from backend.database import AsyncSessionLocal
from backend.models.company import AtsType, Company
from backend.scrapers.probe import ProbeResult, probe_ats


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _heuristic_candidates(name: str) -> list[str]:
    slug = _slugify(name)
    return [
        f"https://careers.{slug}.com/",
        f"https://jobs.{slug}.com/",
        f"https://{slug}.com/careers",
    ]


async def _search_web(name: str) -> list[str]:
    query = quote_plus(f"{name} careers jobs")
    url = f"https://html.duckduckgo.com/html/?q={query}"
    try:
        async with _AsyncWebCrawler(headless=True) as crawler:
            result = await crawler.arun(url=url)
            text = result.markdown or ""
            found = re.findall(r"https?://[^\s\)\"\'\]>]+", text)
            blocked = {"duckduckgo.com", "bing.com", "google.com", "w3.org"}
            filtered = [
                u for u in found
                if not any(d in u for d in blocked) and len(u) < 200
            ]
            return list(dict.fromkeys(filtered))[:7]
    except Exception:
        return []


async def _llm_filter(
    name: str, candidates: list[str], client: anthropic.AsyncAnthropic
) -> list[str]:
    prompt = (
        f"Company: {name}\n\nCandidate URLs:\n"
        + "\n".join(f"- {u}" for u in candidates)
        + f"\n\nReturn a JSON array of URLs that are most likely the official careers portal "
        f"for {name}. Exclude LinkedIn, Glassdoor, Indeed, Levels.fyi, news articles, "
        f'Wikipedia. Order by likelihood. Example: ["https://..."]\n'
        f"If none look right, return all of them unchanged."
    )
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        m = re.search(r"\[.*?\]", text, re.DOTALL)
        if m:
            urls = json.loads(m.group())
            result = [u for u in urls if isinstance(u, str)]
            return result[:10] if result else candidates
    except Exception:
        pass
    return candidates


async def _llm_analyze_page(
    name: str, markdown: str, client: anthropic.AsyncAnthropic
) -> dict | None:
    prompt = (
        f"You are analyzing a careers page for '{name}'.\n\n"
        f"Page content:\n{markdown[:3000]}\n\n"
        f"Identify the ATS or job board system. Options: "
        f"greenhouse, lever, ashby, workable, smartrecruiters, workday, crawl4ai.\n"
        f"Also identify the canonical jobs listing URL.\n\n"
        f'Respond ONLY as JSON: {{"ats_type": "...", "careers_url": "https://..."}}\n'
        f'If you cannot determine the ATS, use "crawl4ai".'
    )
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        m = re.search(r"\{.*?\}", text, re.DOTALL)
        if m:
            return json.loads(m.group())
    except Exception:
        pass
    return None


async def _update_status(company_id: int, message: str, status: str = "discovering") -> None:
    async with AsyncSessionLocal() as session:
        company = (await session.execute(
            select(Company).where(Company.id == company_id)
        )).scalar_one_or_none()
        if company:
            company.discovery_message = message
            company.discovery_status = status
            await session.commit()


async def _resolve(
    company_id: int, ats_type: str, identifier: str | None, careers_url: str
) -> None:
    async with AsyncSessionLocal() as session:
        company = (await session.execute(
            select(Company).where(Company.id == company_id)
        )).scalar_one_or_none()
        if company:
            company.ats_type = AtsType(ats_type)
            company.ats_identifier = identifier
            company.careers_url = careers_url
            company.discovery_status = "none"
            company.discovery_message = None
            company.is_active = True
            await session.commit()


async def _run_discovery(company_id: int, name: str) -> None:
    client = anthropic.AsyncAnthropic()

    # Step 1: Catalog fast path
    catalog_entry = next(
        (c for c in DEFAULT_COMPANIES if c["name"].lower() == name.lower()), None
    )
    if catalog_entry:
        await _update_status(company_id, "Probing known URL...")
        result = await probe_ats(catalog_entry["careers_url"], name)
        await _resolve(company_id, result.ats_type, result.identifier, catalog_entry["careers_url"])
        return

    # Step 2: Web search + heuristics (up to 10 candidates)
    await _update_status(company_id, "Searching web...")
    search_urls = await _search_web(name)
    heuristic_urls = _heuristic_candidates(name)
    all_candidates = list(dict.fromkeys(search_urls + heuristic_urls))[:10]

    if not all_candidates:
        await _update_status(company_id, "Could not find — paste URL manually", "failed")
        return

    # Step 3: LLM pass 1 -- filter/rank candidates
    await _update_status(company_id, "Filtering candidates...")
    filtered = await _llm_filter(name, all_candidates, client)

    # Step 4: Parallel ATS probe all candidates
    await _update_status(company_id, "Probing ATS APIs...")

    async def probe_candidate(url: str) -> tuple[str, ProbeResult] | None:
        try:
            result = await probe_ats(url, name)
            return (url, result)
        except Exception:
            return None

    probe_results = await asyncio.gather(*[probe_candidate(u) for u in filtered])

    best_crawl4ai_url: str | None = None
    for item in probe_results:
        if item is None:
            continue
        url, result = item
        if result.ats_type != "crawl4ai":
            await _resolve(company_id, result.ats_type, result.identifier, url)
            return
        if best_crawl4ai_url is None:
            best_crawl4ai_url = url

    # Step 5: LLM pass 2 -- analyze the top-ranked page
    top_url = filtered[0] if filtered else best_crawl4ai_url
    if top_url:
        await _update_status(company_id, "Analyzing careers page...")
        try:
            async with _AsyncWebCrawler(headless=True) as crawler:
                crawl_result = await crawler.arun(url=top_url)
                markdown = crawl_result.markdown or ""
            analysis = await _llm_analyze_page(name, markdown, client)
            if analysis and analysis.get("careers_url"):
                careers_url = analysis["careers_url"]
                reprobe = await probe_ats(careers_url, name)
                resolved_ats = (
                    reprobe.ats_type
                    if reprobe.ats_type != "crawl4ai"
                    else analysis.get("ats_type", "crawl4ai")
                )
                await _resolve(company_id, resolved_ats, reprobe.identifier, careers_url)
                return
        except Exception:
            pass

    # Step 6: Fallback
    fallback_url = best_crawl4ai_url or (filtered[0] if filtered else None)
    if fallback_url:
        await _resolve(company_id, "crawl4ai", None, fallback_url)
    else:
        await _update_status(company_id, "Could not find — paste URL manually", "failed")


async def discover_company(company_id: int, name: str) -> None:
    try:
        await asyncio.wait_for(_run_discovery(company_id, name), timeout=90.0)
    except (asyncio.TimeoutError, Exception):
        await _update_status(company_id, "Could not find — paste URL manually", "failed")
