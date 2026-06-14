from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session
from backend.models.application import ApplicationTracking

router = APIRouter(prefix="/applications", tags=["applications"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_applications(session: Session):
    rows = (await session.execute(select(ApplicationTracking))).scalars().all()
    return [_serialize(r) for r in rows]


def _serialize(app: ApplicationTracking) -> dict:
    return {
        "id": app.id,
        "job_id": app.job_id,
        "company_name": app.company_name,
        "job_title": app.job_title,
        "url": app.url,
        "applied_date": app.applied_date.isoformat() if app.applied_date else None,
        "notes": app.notes,
        "status": app.status,
        "source": app.source,
        "score": app.score,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "updated_at": app.updated_at.isoformat() if app.updated_at else None,
    }
