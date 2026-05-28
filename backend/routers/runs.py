import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session, AsyncSessionLocal
from backend.models.run import Run, RunCompanyResult, RunStatus
from backend.pipeline import execute_run, get_run_queue, request_cancel_run

router = APIRouter(prefix="/runs", tags=["runs"])
Session = Annotated[AsyncSession, Depends(get_session)]


class RunCreate(BaseModel):
    company_ids: list[int] | None = None
    preview: bool = False


@router.post("", status_code=201)
async def start_run(req: RunCreate, background_tasks: BackgroundTasks, session: Session):
    run = Run(is_preview=req.preview, company_ids=req.company_ids)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    async def run_in_background(run_id: int):
        async with AsyncSessionLocal() as bg_session:
            await execute_run(run_id, bg_session)

    background_tasks.add_task(run_in_background, run.id)
    return {"id": run.id, "status": run.status}


@router.get("")
async def list_runs(session: Session):
    rows = (await session.execute(select(Run).order_by(Run.started_at.desc()).limit(50))).scalars().all()
    return [
        {
            "id": r.id, "status": r.status, "is_preview": r.is_preview,
            "started_at": r.started_at, "completed_at": r.completed_at,
            "total_jobs_found": r.total_jobs_found,
            "total_confirmed": r.total_confirmed,
            "total_notified": r.total_notified,
        }
        for r in rows
    ]


@router.get("/{run_id}")
async def get_run(run_id: int, session: Session):
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    results = (await session.execute(
        select(RunCompanyResult).where(RunCompanyResult.run_id == run_id)
    )).scalars().all()
    return {
        "id": run.id, "status": run.status, "started_at": run.started_at,
        "company_results": [
            {"company_id": r.company_id, "status": r.status,
             "jobs_found": r.jobs_found, "confirmed": r.confirmed}
            for r in results
        ],
    }


@router.post("/{run_id}/cancel")
async def cancel_run(run_id: int, session: Session):
    run = await session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != RunStatus.running:
        raise HTTPException(status_code=409, detail="Run is not running")
    request_cancel_run(run_id)
    return {"id": run_id, "status": "cancelling"}


@router.get("/{run_id}/stream")
async def stream_run(run_id: int):
    async def generator():
        q = get_run_queue(run_id)
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"
                continue
            yield f"event: {event['type']}\ndata: {json.dumps(event['data'])}\n\n"
            if event["type"] == "run_done":
                break

    return StreamingResponse(generator(), media_type="text/event-stream")
