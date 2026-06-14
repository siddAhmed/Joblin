def test_user_model_columns():
    from backend.models.user import User
    assert User.__tablename__ == "users"
    assert hasattr(User, "id")
    assert hasattr(User, "authentik_username")
    assert hasattr(User, "is_admin")
    assert hasattr(User, "created_at")


def test_setting_model_has_user_id():
    from backend.models.setting import Setting
    assert hasattr(Setting, "id")
    assert hasattr(Setting, "user_id")
    assert hasattr(Setting, "key")
    assert hasattr(Setting, "value")


def test_owned_models_have_user_id():
    from backend.models.company import Company
    from backend.models.job import Job
    from backend.models.run import Run
    from backend.models.application import ApplicationTracking
    from backend.models.feedback import FeedbackExample
    from backend.models.resume import Resume
    for model in [Company, Job, Run, ApplicationTracking, FeedbackExample, Resume]:
        assert hasattr(model, "user_id"), f"{model.__name__} missing user_id"


import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.database import Base, get_session
from backend.main import create_app


@pytest.mark.anyio
async def test_get_current_user_missing_header():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    async def override():
        async with factory() as s:
            yield s
    app.dependency_overrides[get_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/companies")
    assert resp.status_code == 401
    await engine.dispose()


@pytest.mark.anyio
async def test_get_current_user_auto_provisions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = create_app()
    async def override():
        async with factory() as s:
            yield s
    app.dependency_overrides[get_session] = override

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/api/companies", headers={"X-authentik-username": "alice"})
    assert resp.status_code == 200

    from sqlalchemy import select
    from backend.models.user import User
    async with factory() as s:
        user = (await s.execute(select(User).where(User.authentik_username == "alice"))).scalar_one()
        assert user.is_admin is True  # first user provisioned is admin
    await engine.dispose()
