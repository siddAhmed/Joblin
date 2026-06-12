import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


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
