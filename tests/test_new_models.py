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
