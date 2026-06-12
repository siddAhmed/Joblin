import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.database import get_session
from backend.models.company import Company, AtsType
from backend.models.job import Job


async def test_get_resume_returns_404_when_none(client):
    response = await client.get("/api/resume")
    assert response.status_code == 404


async def test_save_resume_then_get(client):
    tex = r"\documentclass{article}\begin{document}Hello\end{document}"
    put = await client.put("/api/resume", json={"tex_content": tex})
    assert put.status_code == 200
    assert put.json()["tex_content"] == tex
    assert "updated_at" in put.json()

    get = await client.get("/api/resume")
    assert get.status_code == 200
    assert get.json()["tex_content"] == tex


async def test_save_resume_twice_overwrites(client):
    tex1 = r"\documentclass{article}\begin{document}v1\end{document}"
    tex2 = r"\documentclass{article}\begin{document}v2\end{document}"
    await client.put("/api/resume", json={"tex_content": tex1})
    await client.put("/api/resume", json={"tex_content": tex2})
    get = await client.get("/api/resume")
    assert get.json()["tex_content"] == tex2


async def test_compile_resume_success(client):
    fake_pdf = b"%PDF-1.4 fake content"

    async def fake_exec(*args, **kwargs):
        tex_path = Path(args[1])
        tex_path.with_suffix(".pdf").write_bytes(fake_pdf)
        proc = MagicMock()
        proc.returncode = 0
        proc.communicate = AsyncMock(return_value=(b"", b""))
        return proc

    with patch("backend.routers.resume.asyncio.create_subprocess_exec", side_effect=fake_exec):
        response = await client.post(
            "/api/resume/compile",
            json={"tex_content": r"\documentclass{article}\begin{document}Hi\end{document}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == fake_pdf


async def test_compile_resume_failure(client):
    async def fail_exec(*args, **kwargs):
        proc = MagicMock()
        proc.returncode = 1
        proc.communicate = AsyncMock(return_value=(b"", b"LaTeX Error: undefined control sequence"))
        return proc

    with patch("backend.routers.resume.asyncio.create_subprocess_exec", side_effect=fail_exec):
        response = await client.post("/api/resume/compile", json={"tex_content": r"\badcommand"})

    assert response.status_code == 422
    assert "undefined control sequence" in response.json()["detail"]


@pytest.fixture
async def seeded_job_id(app):
    override = app.dependency_overrides[get_session]
    async for session in override():
        company = Company(
            name="Stripe",
            careers_url="https://stripe.com/jobs",
            ats_type=AtsType.greenhouse,
        )
        session.add(company)
        await session.flush()
        job = Job(
            company_id=company.id,
            job_id="swe-123",
            title="Software Engineer",
            url="https://stripe.com/jobs/swe-123",
            raw_description="Python, distributed systems, REST APIs, PostgreSQL",
            normalized_title="software engineer",
        )
        session.add(job)
        await session.commit()
        return job.id


async def test_tailor_resume_404_no_resume(client):
    response = await client.post("/api/resume/tailor", json={"job_id": 999})
    assert response.status_code == 404
    assert "reference resume" in response.json()["detail"].lower()


async def test_tailor_resume_404_no_job(client):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})
    response = await client.post("/api/resume/tailor", json={"job_id": 999})
    assert response.status_code == 404
    assert "job" in response.json()["detail"].lower()


async def test_tailor_resume_success(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    tailored = r"\documentclass{article}\begin{document}Tailored resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})

    mock_provider = MagicMock()
    mock_provider.tailor_resume = AsyncMock(return_value=tailored)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    assert response.json()["tex_content"] == tailored
    mock_provider.tailor_resume.assert_called_once_with(
        tex_content=tex,
        job_description="Python, distributed systems, REST APIs, PostgreSQL",
    )
