import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

from backend.models.company import AtsType
from backend.models.company_catalog import CompanyCatalog
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models.match import Match, MatchTier
from backend.models.run import Run, RunStatus
from backend.models.job_skill import JobSkill
from backend.database import get_session


@pytest.mark.anyio
async def test_analyze_empty_match_ids(client: AsyncClient):
    resp = await client.post("/api/insights/analyze", json={"match_ids": []})
    assert resp.status_code == 200
    data = resp.json()
    assert data == {"analyzed": 0, "skipped": 0, "skills_found": 0}


@pytest.mark.anyio
async def test_list_skills_empty(client: AsyncClient):
    resp = await client.get("/api/insights/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert data["skills"] == []
    assert data["total_jobs_analyzed"] == 0


@pytest.mark.anyio
async def test_citations_empty(client: AsyncClient):
    resp = await client.get("/api/insights/skills/Python/citations")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.anyio
async def test_analyze_records_skills_and_deduplicates(client: AsyncClient, app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        catalog = CompanyCatalog(
            name="Acme",
            careers_url="https://acme.com/careers",
            ats_type=AtsType.greenhouse,
        )
        session.add(catalog)
        await session.flush()

        raw_job = RawJob(
            catalog_company_id=catalog.id,
            job_id="j1",
            title="Backend Engineer",
            url="https://acme.com/jobs/1",
            raw_description="Python, PostgreSQL, system design required.",
            normalized_title="backend engineer",
        )
        session.add(raw_job)
        await session.flush()

        run = Run(status=RunStatus.completed, user_id=1)
        session.add(run)
        await session.flush()

        user_job = UserJob(user_id=1, raw_job_id=raw_job.id, run_id=run.id)
        session.add(user_job)
        await session.flush()

        match = Match(job_id=user_job.id, run_id=run.id, score=0.85, tier=MatchTier.strong, summary="Good fit")
        session.add(match)
        await session.commit()

        match_id = match.id

    async def override():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_session] = override

    mock_provider = AsyncMock()
    mock_provider.extract_skills = AsyncMock(return_value=["Python", "PostgreSQL", "system design"])
    mock_provider.last_usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    with patch("backend.routers.insights.get_filter_provider", return_value=mock_provider):
        resp = await client.post("/api/insights/analyze", json={"match_ids": [match_id]})
    assert resp.status_code == 200
    data = resp.json()
    assert data["analyzed"] == 1
    assert data["skipped"] == 0
    assert data["skills_found"] == 3

    # Second call: same match should be skipped
    with patch("backend.routers.insights.get_filter_provider", return_value=mock_provider):
        resp2 = await client.post("/api/insights/analyze", json={"match_ids": [match_id]})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["analyzed"] == 0
    assert data2["skipped"] == 1

    # Skills list should show 3 skills
    resp3 = await client.get("/api/insights/skills")
    assert resp3.status_code == 200
    skills_data = resp3.json()
    skill_names = [s["name"] for s in skills_data["skills"]]
    assert "Python" in skill_names
    assert skills_data["total_jobs_analyzed"] == 1

    await engine.dispose()
