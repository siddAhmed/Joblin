from typing import Annotated
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session
from backend.models.application import ApplicationSource, ApplicationStatus, ApplicationTracking

router = APIRouter(prefix="/applications", tags=["applications"])
Session = Annotated[AsyncSession, Depends(get_session)]


# /stats and /bulk MUST come before /{app_id}

@router.get("/stats")
async def get_stats(session: Session):
    status_rows = (await session.execute(
        select(ApplicationTracking.status, func.count().label("count"))
        .group_by(ApplicationTracking.status)
    )).all()
    counts = {r.status: r.count for r in status_rows}

    source_rows = (await session.execute(
        select(ApplicationTracking.source, func.count().label("count"))
        .group_by(ApplicationTracking.source)
    )).all()
    source_counts = {r.source: r.count for r in source_rows}

    applied = counts.get(ApplicationStatus.applied, 0)
    offer = counts.get(ApplicationStatus.offer, 0)

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    daily_rows = (await session.execute(
        select(
            func.date(ApplicationTracking.created_at).label("day"),
            ApplicationTracking.status,
            func.count().label("count"),
        )
        .where(ApplicationTracking.created_at >= thirty_days_ago)
        .group_by(func.date(ApplicationTracking.created_at), ApplicationTracking.status)
        .order_by(func.date(ApplicationTracking.created_at))
    )).all()

    daily: dict[str, dict] = {}
    for r in daily_rows:
        day = str(r.day)
        if day not in daily:
            daily[day] = {}
        daily[day][r.status] = r.count

    return {
        "total": sum(counts.values()),
        "by_status": {
            "interested": counts.get(ApplicationStatus.interested, 0),
            "applied": applied,
            "rejected": counts.get(ApplicationStatus.rejected, 0),
            "offer": offer,
        },
        "response_rate": round(offer / applied * 100) if applied > 0 else 0,
        "by_source": {
            "joblin": source_counts.get(ApplicationSource.joblin, 0),
            "external": source_counts.get(ApplicationSource.external, 0),
        },
        "daily_series": [
            {"date": day, **statuses}
            for day, statuses in sorted(daily.items())
        ],
    }


class BulkActionRequest(BaseModel):
    ids: list[int]
    action: str  # "status_change" or "delete"
    status: ApplicationStatus | None = None


@router.post("/bulk")
async def bulk_action(req: BulkActionRequest, session: Session):
    apps = (await session.execute(
        select(ApplicationTracking).where(ApplicationTracking.id.in_(req.ids))
    )).scalars().all()

    if req.action == "status_change":
        if req.status is None:
            raise HTTPException(status_code=400, detail="status required for status_change")
        for app in apps:
            app.status = req.status
        await session.commit()
        return {"updated": len(apps)}
    elif req.action == "delete":
        for app in apps:
            await session.delete(app)
        await session.commit()
        return {"deleted": len(apps)}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")


@router.get("")
async def list_applications(
    session: Session,
    status: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
):
    stmt = select(ApplicationTracking).order_by(ApplicationTracking.created_at.desc())
    if status:
        stmt = stmt.where(ApplicationTracking.status == status)
    if source:
        stmt = stmt.where(ApplicationTracking.source == source)
    if search:
        term = f"%{search}%"
        stmt = stmt.where(or_(
            ApplicationTracking.company_name.ilike(term),
            ApplicationTracking.job_title.ilike(term),
        ))
    rows = (await session.execute(stmt.offset(offset).limit(limit))).scalars().all()
    return [_serialize(r) for r in rows]


class CreateApplicationRequest(BaseModel):
    job_id: int | None = None
    company_name: str
    job_title: str
    url: str | None = None
    applied_date: date | None = None
    notes: str | None = None
    status: ApplicationStatus
    source: ApplicationSource
    score: float | None = None


@router.post("", status_code=201)
async def create_application(req: CreateApplicationRequest, session: Session):
    if req.job_id is not None:
        existing = (await session.execute(
            select(ApplicationTracking).where(ApplicationTracking.job_id == req.job_id)
        )).scalar_one_or_none()
        if existing:
            existing.status = req.status
            await session.commit()
            await session.refresh(existing)
            return _serialize(existing)

    app = ApplicationTracking(
        job_id=req.job_id,
        company_name=req.company_name,
        job_title=req.job_title,
        url=req.url,
        applied_date=req.applied_date,
        notes=req.notes,
        status=req.status,
        source=req.source,
        score=req.score,
    )
    session.add(app)
    await session.commit()
    await session.refresh(app)
    return _serialize(app)


class UpdateApplicationRequest(BaseModel):
    status: ApplicationStatus | None = None
    notes: str | None = None
    applied_date: date | None = None


@router.patch("/{app_id}")
async def update_application(app_id: int, req: UpdateApplicationRequest, session: Session):
    app = (await session.execute(
        select(ApplicationTracking).where(ApplicationTracking.id == app_id)
    )).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if req.status is not None:
        app.status = req.status
    if req.notes is not None:
        app.notes = req.notes
    if req.applied_date is not None:
        app.applied_date = req.applied_date
    await session.commit()
    await session.refresh(app)
    return _serialize(app)


@router.delete("/{app_id}", status_code=204)
async def delete_application(app_id: int, session: Session):
    app = (await session.execute(
        select(ApplicationTracking).where(ApplicationTracking.id == app_id)
    )).scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await session.delete(app)
    await session.commit()


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
