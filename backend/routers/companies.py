import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.company import Company, AtsType
from backend.scrapers.probe import probe_ats

router = APIRouter(prefix="/companies", tags=["companies"])
Session = Annotated[AsyncSession, Depends(get_session)]


class CompanyCreate(BaseModel):
    name: str
    careers_url: str


class CompanyUpdate(BaseModel):
    css_selector: str | None = None
    custom_api_url: str | None = None
    is_active: bool | None = None
    ats_type: AtsType | None = None
    ats_identifier: str | None = None


class ProbeRequest(BaseModel):
    name: str
    careers_url: str


@router.get("")
async def list_companies(session: Session):
    rows = (await session.execute(select(Company).order_by(Company.name))).scalars().all()
    return [
        {
            "id": c.id, "name": c.name, "careers_url": c.careers_url,
            "ats_type": c.ats_type, "is_active": c.is_active,
            "quarantine_count": c.quarantine_count, "quarantined_at": c.quarantined_at,
            "quarantine_reason": c.quarantine_reason,
        }
        for c in rows
    ]


@router.post("/probe")
async def probe_company(req: ProbeRequest):
    result = await probe_ats(req.careers_url, req.name)
    return {
        "ats_type": result.ats_type,
        "identifier": result.identifier,
        "probe_attempts": [
            {"url": a.url, "status_code": a.status_code, "error": a.error}
            for a in result.probe_attempts
        ],
    }


@router.post("", status_code=201)
async def add_company(req: CompanyCreate, session: Session):
    probe = await probe_ats(req.careers_url, req.name)
    company = Company(
        name=req.name,
        careers_url=req.careers_url,
        ats_type=AtsType(probe.ats_type),
        ats_identifier=probe.identifier,
    )
    session.add(company)
    await session.commit()
    await session.refresh(company)
    return {"id": company.id, "ats_type": company.ats_type, "probe_attempts": [
        {"url": a.url, "status_code": a.status_code} for a in probe.probe_attempts
    ]}


@router.patch("/{company_id}")
async def update_company(company_id: int, req: CompanyUpdate, session: Session):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in req.model_dump(exclude_none=True).items():
        setattr(company, field, value)
    await session.commit()
    return {"id": company.id}


@router.delete("/{company_id}", status_code=204)
async def delete_company(company_id: int, session: Session):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    await session.delete(company)
    await session.commit()


@router.post("/{company_id}/retry")
async def retry_company(company_id: int, session: Session):
    company = await session.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.quarantine_count = 0
    company.quarantined_at = None
    company.quarantine_reason = None
    company.is_active = True
    await session.commit()
    return {"id": company.id, "status": "reactivated"}


@router.post("/import", status_code=201)
async def import_companies(file: UploadFile, session: Session):
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    created = []
    for row in reader:
        name = row.get("name", "").strip()
        url = row.get("careers_url", "").strip()
        if not name or not url:
            continue
        probe = await probe_ats(url, name)
        company = Company(
            name=name, careers_url=url,
            ats_type=AtsType(probe.ats_type), ats_identifier=probe.identifier,
        )
        session.add(company)
        created.append(name)
    await session.commit()
    return {"created": len(created), "names": created}
