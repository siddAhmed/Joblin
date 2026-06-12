import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
from backend.llm.factory import get_tailor_provider
from backend.models.job import Job
from backend.models.resume import Resume

router = APIRouter(prefix="/resume", tags=["resume"])
Session = Annotated[AsyncSession, Depends(get_session)]


class ResumeSave(BaseModel):
    tex_content: str


@router.get("")
async def get_resume(session: Session):
    result = await session.execute(select(Resume).where(Resume.id == 1))
    resume = result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="No resume found")
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}


@router.put("")
async def save_resume(body: ResumeSave, session: Session):
    result = await session.execute(select(Resume).where(Resume.id == 1))
    resume = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if resume is None:
        resume = Resume(id=1, tex_content=body.tex_content, updated_at=now)
        session.add(resume)
    else:
        resume.tex_content = body.tex_content
        resume.updated_at = now
    await session.commit()
    return {"tex_content": resume.tex_content, "updated_at": resume.updated_at.isoformat()}


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
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(
                status_code=422,
                detail=stderr.decode("utf-8", errors="replace"),
            )
        pdf_bytes = (Path(tmpdir) / "resume.pdf").read_bytes()
    return Response(content=pdf_bytes, media_type="application/pdf")


class TailorRequest(BaseModel):
    job_id: int


@router.post("/tailor")
async def tailor_resume_endpoint(body: TailorRequest, session: Session):
    resume_result = await session.execute(select(Resume).where(Resume.id == 1))
    resume = resume_result.scalar_one_or_none()
    if resume is None:
        raise HTTPException(status_code=404, detail="No reference resume found. Upload a .tex file first.")

    job = await session.get(Job, body.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    settings = await get_all_settings(session)
    provider = get_tailor_provider(settings)
    tailored_tex = await provider.tailor_resume(
        tex_content=resume.tex_content,
        job_description=job.raw_description or job.title,
    )
    return {"tex_content": tailored_tex}
