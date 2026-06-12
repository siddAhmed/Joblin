from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_all_settings
from backend.database import get_session
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
