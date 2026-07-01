import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.dependencies.auth import CurrentUser
from backend.llm.factory import get_tailor_provider
from backend.models.user_job import UserJob
from backend.models.raw_job import RawJob
from backend.models.resume import Resume

router = APIRouter(prefix="/resume", tags=["resume"])
Session = Annotated[AsyncSession, Depends(get_session)]


class ResumeSave(BaseModel):
    tex_content: str


class ActivitiesSave(BaseModel):
    activities_content: str


@router.get("")
async def get_resume(session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None or not resume.tex_content:
        raise HTTPException(status_code=404, detail="No resume found")
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}


@router.put("")
async def save_resume(body: ResumeSave, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if resume is None:
        resume = Resume(user_id=current_user.id, tex_content=body.tex_content, updated_at=now)
        session.add(resume)
    else:
        resume.tex_content = body.tex_content
        resume.updated_at = now
    await session.commit()
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}


@router.get("/activities")
async def get_activities(session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None:
        return {"activities_content": None, "updated_at": None}
    return {
        "activities_content": resume.activities_content,
        "updated_at": resume.updated_at.isoformat() if resume.updated_at else None,
    }


@router.put("/activities")
async def save_activities(body: ActivitiesSave, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if resume is None:
        resume = Resume(
            user_id=current_user.id,
            tex_content="",
            activities_content=body.activities_content,
            updated_at=now,
        )
        session.add(resume)
    else:
        resume.activities_content = body.activities_content
    await session.commit()
    return {
        "activities_content": resume.activities_content,
        "updated_at": resume.updated_at.isoformat(),
    }


class CompileRequest(BaseModel):
    tex_content: str


@router.post("/compile")
async def compile_resume(body: CompileRequest):
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "resume.tex"
        tex_path.write_text(body.tex_content, encoding="utf-8")
        proc = await asyncio.create_subprocess_exec(
            "tectonic", str(tex_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tmpdir,
        )
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(status_code=422, detail="Compilation timed out after 60 seconds")
        if proc.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=stderr.decode("utf-8", errors="replace"),
            )
        pdf_bytes = (Path(tmpdir) / "resume.pdf").read_bytes()
    return Response(content=pdf_bytes, media_type="application/pdf")


class TailorRequest(BaseModel):
    job_id: int


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/tailor")
async def tailor_resume_endpoint(body: TailorRequest, session: Session, current_user: CurrentUser):
    resume = (await session.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )).scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="No reference resume found. Upload a .tex file first.")

    row = (await session.execute(
        select(UserJob, RawJob)
        .join(RawJob, UserJob.raw_job_id == RawJob.id)
        .where(UserJob.id == body.job_id, UserJob.user_id == current_user.id)
    )).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    uj, rj = row

    if not rj.raw_description:
        raise HTTPException(
            status_code=422,
            detail="This job has no description yet. Run a scan to fetch full job details first.",
        )

    settings = await get_all_settings(session, user_id=current_user.id)
    provider = get_tailor_provider(settings)
    tex_content = resume.tex_content
    activities_content = resume.activities_content
    job_description = rj.raw_description

    async def generate():
        try:
            yield _sse("phase", {"phase": 1, "label": "Analyzing job requirements..."})
            requirements = await provider.analyze_job(job_description=job_description)

            yield _sse("phase", {"phase": 2, "label": "Selecting relevant experiences..."})
            selected_items = await provider.select_activities(
                requirements=requirements,
                tex_content=tex_content,
                activities_content=activities_content,
            )

            yield _sse("phase", {"phase": 3, "label": "Tailoring resume..."})
            tailored_tex = await provider.tailor_resume(
                tex_content=tex_content,
                selected_items=selected_items,
            )

            yield _sse("done", {"tex_content": tailored_tex})
        except Exception as exc:
            yield _sse("error", {"detail": str(exc)})

    return StreamingResponse(generate(), media_type="text/event-stream")
