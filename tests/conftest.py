import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from unittest.mock import patch

from backend.database import Base, get_session
from backend.main import create_app


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def app():
    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    test_session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    application = create_app()

    async def override_get_session():
        async with test_session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_get_session

    yield application

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
