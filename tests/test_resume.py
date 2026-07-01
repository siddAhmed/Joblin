import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from backend.database import get_session
from backend.models.company import AtsType
from backend.models.company_catalog import CompanyCatalog
from backend.models.raw_job import RawJob
from backend.models.user_job import UserJob


async def test_activities_column_exists(client):
    # activities_content should be null before any PUT
    response = await client.get("/api/resume/activities")
    assert response.status_code == 200
    assert response.json()["activities_content"] is None


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
    user_job_id = None
    async for session in override():
        catalog = CompanyCatalog(
            name="Stripe",
            careers_url="https://stripe.com/jobs",
            ats_type=AtsType.greenhouse,
        )
        session.add(catalog)
        await session.flush()
        raw_job = RawJob(
            catalog_company_id=catalog.id,
            job_id="swe-123",
            title="Software Engineer",
            url="https://stripe.com/jobs/swe-123",
            raw_description="Python, distributed systems, REST APIs, PostgreSQL",
            normalized_title="software engineer",
        )
        session.add(raw_job)
        await session.flush()
        user_job = UserJob(user_id=1, raw_job_id=raw_job.id)
        session.add(user_job)
        await session.commit()
        user_job_id = user_job.id
    return user_job_id


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
    mock_provider.analyze_job = AsyncMock(return_value={"required_skills": ["Python"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []})
    mock_provider.select_activities = AsyncMock(return_value="1. Python")
    mock_provider.tailor_resume = AsyncMock(return_value=tailored)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    done = next(e for e in events if e.get("event") == "done")
    assert done["data"]["tex_content"] == tailored


async def test_get_activities_returns_null_when_no_resume(client):
    response = await client.get("/api/resume/activities")
    assert response.status_code == 200
    assert response.json()["activities_content"] is None
    assert response.json()["updated_at"] is None


async def test_save_activities_then_get(client):
    content = "# Work Experience\n- Built a thing\n"
    put = await client.put("/api/resume/activities", json={"activities_content": content})
    assert put.status_code == 200
    assert put.json()["activities_content"] == content
    assert "updated_at" in put.json()

    get = await client.get("/api/resume/activities")
    assert get.status_code == 200
    assert get.json()["activities_content"] == content


async def test_save_activities_twice_overwrites(client):
    await client.put("/api/resume/activities", json={"activities_content": "v1"})
    await client.put("/api/resume/activities", json={"activities_content": "v2"})
    get = await client.get("/api/resume/activities")
    assert get.json()["activities_content"] == "v2"


async def test_save_activities_does_not_change_tex_content(client):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})
    await client.put("/api/resume/activities", json={"activities_content": "# Activities"})
    get = await client.get("/api/resume")
    assert get.json()["tex_content"] == tex


def _parse_sse(text: str) -> list[dict]:
    events = []
    for chunk in text.split("\n\n"):
        if not chunk.strip():
            continue
        parts: dict = {}
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                parts["event"] = line[7:].strip()
            elif line.startswith("data: "):
                parts["data"] = json.loads(line[6:].strip())
        if parts:
            events.append(parts)
    return events


async def test_tailor_resume_success_sse(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    tailored = r"\documentclass{article}\begin{document}Tailored resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})

    mock_provider = MagicMock()
    mock_provider.analyze_job = AsyncMock(return_value={"required_skills": ["Python"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []})
    mock_provider.select_activities = AsyncMock(return_value="1. Python experience")
    mock_provider.tailor_resume = AsyncMock(return_value=tailored)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = _parse_sse(response.text)
    phase_events = [e for e in events if e.get("event") == "phase"]
    done_events = [e for e in events if e.get("event") == "done"]

    assert len(phase_events) == 3
    assert phase_events[0]["data"]["phase"] == 1
    assert phase_events[1]["data"]["phase"] == 2
    assert phase_events[2]["data"]["phase"] == 3
    assert len(done_events) == 1
    assert done_events[0]["data"]["tex_content"] == tailored

    mock_provider.analyze_job.assert_called_once_with(
        job_description="Python, distributed systems, REST APIs, PostgreSQL"
    )
    mock_provider.select_activities.assert_called_once_with(
        requirements={"required_skills": ["Python"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []},
        tex_content=tex,
        activities_content=None,
    )
    mock_provider.tailor_resume.assert_called_once_with(
        tex_content=tex,
        selected_items="1. Python experience",
    )


async def test_tailor_resume_sse_includes_activities_content(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    activities = "## Side Projects\n- Built a Go microservice"
    await client.put("/api/resume", json={"tex_content": tex})
    await client.put("/api/resume/activities", json={"activities_content": activities})

    mock_provider = MagicMock()
    mock_provider.analyze_job = AsyncMock(return_value={"required_skills": ["Go"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []})
    mock_provider.select_activities = AsyncMock(return_value="1. Go microservice")
    mock_provider.tailor_resume = AsyncMock(return_value=tex)

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    mock_provider.select_activities.assert_called_once_with(
        requirements={"required_skills": ["Go"], "preferred_skills": [], "key_themes": [], "seniority_signals": [], "keywords": []},
        tex_content=tex,
        activities_content=activities,
    )


async def test_tailor_resume_sse_error_event_on_provider_failure(client, seeded_job_id):
    tex = r"\documentclass{article}\begin{document}My resume\end{document}"
    await client.put("/api/resume", json={"tex_content": tex})

    mock_provider = MagicMock()
    mock_provider.analyze_job = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    with patch("backend.routers.resume.get_tailor_provider", return_value=mock_provider), \
         patch("backend.routers.resume.get_all_settings", return_value={}):
        response = await client.post("/api/resume/tailor", json={"job_id": seeded_job_id})

    assert response.status_code == 200
    events = _parse_sse(response.text)
    error_events = [e for e in events if e.get("event") == "error"]
    assert len(error_events) == 1
    assert "LLM unavailable" in error_events[0]["data"]["detail"]


async def test_get_resume_returns_404_when_only_activities_saved(client):
    await client.put("/api/resume/activities", json={"activities_content": "# Activities"})
    response = await client.get("/api/resume")
    assert response.status_code == 404
