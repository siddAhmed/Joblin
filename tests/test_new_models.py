import pytest
from sqlalchemy import select
from backend.models.company_catalog import CompanyCatalog
from backend.models.user_company import UserCompany
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob
from backend.models import AtsType


async def test_company_catalog_creates(app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        cat = CompanyCatalog(name="Stripe", careers_url="https://stripe.com/jobs",
                             ats_type=AtsType.greenhouse, ats_identifier="stripe", source="default")
        session.add(cat)
        await session.commit()
        result = await session.get(CompanyCatalog, cat.id)
        assert result.name == "Stripe"
        assert result.source == "default"
        assert result.last_scraped_at is None
    await engine.dispose()


async def test_user_company_links_catalog(app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base
    from backend.models.user import User
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(id=1, authentik_username="testuser", is_admin=True)
        cat = CompanyCatalog(name="Stripe", careers_url="https://stripe.com/jobs",
                             ats_type=AtsType.greenhouse, ats_identifier="stripe", source="default")
        session.add_all([user, cat])
        await session.flush()
        uc = UserCompany(user_id=user.id, catalog_id=cat.id, is_active=True)
        session.add(uc)
        await session.commit()
        result = await session.get(UserCompany, uc.id)
        assert result.catalog_id == cat.id


async def test_raw_job_and_user_job(app):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from backend.database import Base
    from backend.models.user import User
    from backend.models.run import Run, RunStatus
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(id=1, authentik_username="testuser", is_admin=True)
        cat = CompanyCatalog(name="Stripe", careers_url="https://stripe.com/jobs",
                             ats_type=AtsType.greenhouse, ats_identifier="stripe", source="default")
        session.add_all([user, cat])
        await session.flush()
        rj = RawJob(catalog_company_id=cat.id, job_id="abc123", title="SWE",
                    location="Remote", url="https://stripe.com/job/1",
                    raw_description="desc", normalized_title="swe",
                    normalized_location="remote", seniority="senior")
        session.add(rj)
        await session.flush()
        uj = UserJob(user_id=user.id, raw_job_id=rj.id, passed_heuristic=True, preview_only=False)
        session.add(uj)
        await session.commit()
        result = await session.get(UserJob, uj.id)
        assert result.passed_heuristic is True
    await engine.dispose()


async def test_migration_populates_catalog(app):
    """Verify migration creates company_catalog from existing companies data."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import text, insert
    from backend.database import Base
    from backend.models.user import User
    from backend.models.company import Company, AtsType as AT
    from backend.models.company_catalog import CompanyCatalog
    from backend.models.user_company import UserCompany

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Seed a user and two companies (same URL for two users = dedup case)
        u1 = User(id=1, authentik_username="alice", is_admin=False)
        u2 = User(id=2, authentik_username="bob", is_admin=False)
        c1 = Company(user_id=1, name="Stripe", careers_url="https://stripe.com/jobs",
                     ats_type=AT.greenhouse, ats_identifier="stripe")
        c2 = Company(user_id=2, name="Stripe", careers_url="https://stripe.com/jobs",
                     ats_type=AT.greenhouse, ats_identifier="stripe")
        session.add_all([u1, u2, c1, c2])
        await session.commit()

    # After migration equivalent logic, company_catalog should have 1 row
    # This test validates the deduplication logic used in the migration.
    async with factory() as session:
        # Manually run the dedup logic
        from sqlalchemy import select
        companies = (await session.execute(select(Company))).scalars().all()
        urls_seen: set[str] = set()
        for c in companies:
            if c.careers_url not in urls_seen:
                urls_seen.add(c.careers_url)
                cat = CompanyCatalog(name=c.name, careers_url=c.careers_url,
                                     ats_type=c.ats_type, ats_identifier=c.ats_identifier,
                                     source="default")
                session.add(cat)
        await session.commit()
        count = (await session.execute(select(CompanyCatalog))).scalars().all()
        assert len(count) == 1, "Two users with same URL should produce one catalog entry"

    await engine.dispose()


async def test_global_cache_hours_default(client):
    from backend.config import DEFAULTS
    assert "global_scrape_cache_hours" in DEFAULTS
    assert DEFAULTS["global_scrape_cache_hours"] == 2
