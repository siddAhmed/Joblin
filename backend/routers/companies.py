import asyncio

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.dependencies.auth import get_current_user
from backend.models.company_catalog import CompanyCatalog
from backend.models.user_company import UserCompany
from backend.models.user import User
from backend.scrapers.probe import probe_ats
from backend.utils.url import normalize_careers_url

router = APIRouter(prefix="/companies", tags=["companies"])


class CompanyCreate(BaseModel):
    name: str
    careers_url: str


class CompanyUpdate(BaseModel):
    css_selector: str | None = None
    custom_api_url: str | None = None
    is_active: bool | None = None
    ats_type: str | None = None
    ats_identifier: str | None = None


class BulkCompanyItem(BaseModel):
    name: str
    careers_url: str


class ProbeRequest(BaseModel):
    name: str
    careers_url: str


class DiscoverRequest(BaseModel):
    names: list[str]


class ResolveRequest(BaseModel):
    careers_url: str


def _catalog_to_dict(cat: CompanyCatalog, uc: UserCompany) -> dict:
    return {
        "id": uc.id,
        "catalog_id": cat.id,
        "name": cat.name,
        "careers_url": cat.careers_url,
        "ats_type": cat.ats_type.value if cat.ats_type else None,
        "ats_identifier": cat.ats_identifier,
        "custom_api_url": cat.custom_api_url,
        "css_selector": cat.css_selector,
        "is_active": uc.is_active,
        "quarantine_count": cat.quarantine_count,
        "quarantined_at": cat.quarantined_at.isoformat() if cat.quarantined_at else None,
        "quarantine_reason": cat.quarantine_reason,
        "discovery_status": cat.discovery_status,
        "discovery_message": cat.discovery_message,
        "source": cat.source,
    }


async def _find_catalog_by_url(url: str, session: AsyncSession) -> CompanyCatalog | None:
    normalized = normalize_careers_url(url)
    all_cats = (await session.execute(select(CompanyCatalog))).scalars().all()
    for cat in all_cats:
        if normalize_careers_url(cat.careers_url) == normalized:
            return cat
    return None


@router.get("")
async def list_companies(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(UserCompany, CompanyCatalog)
        .join(CompanyCatalog, UserCompany.catalog_id == CompanyCatalog.id)
        .where(UserCompany.user_id == current_user.id)
        .order_by(CompanyCatalog.name)
    )).all()
    return [_catalog_to_dict(cat, uc) for uc, cat in rows]


@router.get("/defaults")
async def get_default_companies():
    from backend.data.default_companies import DEFAULT_COMPANIES
    return DEFAULT_COMPANIES


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_company(
    body: CompanyCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    existing_cat = await _find_catalog_by_url(body.careers_url, session)

    if existing_cat:
        existing_uc = (await session.execute(
            select(UserCompany).where(
                UserCompany.user_id == current_user.id,
                UserCompany.catalog_id == existing_cat.id,
            )
        )).scalar_one_or_none()

        if existing_uc:
            return {
                "id": existing_uc.id,
                "catalog_id": existing_cat.id,
                "ats_type": existing_cat.ats_type.value if existing_cat.ats_type else None,
                "probe_attempts": [],
                "match_status": "already_in_your_list",
            }

        uc = UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True)
        session.add(uc)
        await session.commit()

        if existing_cat.quarantined_at:
            match_status = "linked_existing_quarantined"
        elif existing_cat.discovery_status == "success":
            match_status = "linked_existing_working"
        else:
            match_status = "linked_existing_pending"

        return {
            "id": uc.id,
            "catalog_id": existing_cat.id,
            "ats_type": existing_cat.ats_type.value if existing_cat.ats_type else None,
            "probe_attempts": [],
            "match_status": match_status,
        }

    # New catalog entry -- run ATS probe
    probe_result = await probe_ats(careers_url=body.careers_url, name_hint=body.name)

    from backend.models.company import AtsType
    try:
        ats_enum = AtsType(probe_result.ats_type)
    except ValueError:
        ats_enum = AtsType.crawl4ai

    cat = CompanyCatalog(
        name=body.name,
        careers_url=body.careers_url,
        ats_type=ats_enum,
        ats_identifier=probe_result.identifier,
        source="user_submitted",
        discovery_status="success" if probe_result.ats_type != "crawl4ai" else "none",
    )
    session.add(cat)
    await session.flush()

    uc = UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=True)
    session.add(uc)
    await session.commit()

    import dataclasses
    return {
        "id": uc.id,
        "catalog_id": cat.id,
        "ats_type": probe_result.ats_type,
        "probe_attempts": [dataclasses.asdict(a) for a in probe_result.probe_attempts],
        "match_status": "added_new",
    }


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
async def bulk_add_companies(
    items: list[BulkCompanyItem],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    created = 0
    for item in items:
        existing_cat = await _find_catalog_by_url(item.careers_url, session)
        if existing_cat:
            existing_uc = (await session.execute(
                select(UserCompany).where(
                    UserCompany.user_id == current_user.id,
                    UserCompany.catalog_id == existing_cat.id,
                )
            )).scalar_one_or_none()
            if not existing_uc:
                session.add(UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True))
                created += 1
            continue

        probe_result = await probe_ats(careers_url=item.careers_url, name_hint=item.name)
        from backend.models.company import AtsType
        try:
            ats_enum = AtsType(probe_result.ats_type)
        except ValueError:
            ats_enum = AtsType.crawl4ai

        cat = CompanyCatalog(
            name=item.name, careers_url=item.careers_url,
            ats_type=ats_enum, ats_identifier=probe_result.identifier,
            source="user_submitted",
        )
        session.add(cat)
        await session.flush()
        session.add(UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=True))
        created += 1

    await session.commit()
    return {"created": created}


@router.patch("/{company_id}", status_code=status.HTTP_200_OK)
async def update_company(
    company_id: int,
    body: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    cat = await session.get(CompanyCatalog, uc.catalog_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catalog entry not found")

    if body.is_active is not None:
        uc.is_active = body.is_active
    if body.css_selector is not None:
        cat.css_selector = body.css_selector
    if body.custom_api_url is not None:
        cat.custom_api_url = body.custom_api_url
    if body.ats_type is not None:
        from backend.models.company import AtsType
        cat.ats_type = AtsType(body.ats_type)
    if body.ats_identifier is not None:
        cat.ats_identifier = body.ats_identifier

    await session.commit()
    return {"id": uc.id}


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    catalog_id = uc.catalog_id
    await session.delete(uc)
    await session.flush()

    # Drop catalog entry if no other users reference it
    remaining = (await session.execute(
        select(sa_func.count()).select_from(UserCompany).where(UserCompany.catalog_id == catalog_id)
    )).scalar()
    if remaining == 0:
        cat = await session.get(CompanyCatalog, catalog_id)
        if cat:
            await session.delete(cat)

    await session.commit()


@router.post("/{company_id}/retry", status_code=status.HTTP_200_OK)
async def retry_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    cat = await session.get(CompanyCatalog, uc.catalog_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catalog entry not found")

    cat.quarantine_count = 0
    cat.quarantined_at = None
    cat.quarantine_reason = None
    uc.is_active = True
    await session.commit()
    return {"id": uc.id, "status": "reactivated"}


@router.post("/{company_id}/resolve", status_code=status.HTTP_200_OK)
async def resolve_company(
    company_id: int,
    body: ResolveRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uc = (await session.execute(
        select(UserCompany).where(
            UserCompany.id == company_id, UserCompany.user_id == current_user.id
        )
    )).scalar_one_or_none()
    if not uc:
        raise HTTPException(status_code=404, detail="Company not found")

    cat = await session.get(CompanyCatalog, uc.catalog_id)
    if not cat:
        raise HTTPException(status_code=404, detail="Catalog entry not found")

    probe_result = await probe_ats(careers_url=body.careers_url, name_hint=cat.name)
    from backend.models.company import AtsType
    try:
        cat.ats_type = AtsType(probe_result.ats_type)
    except ValueError:
        cat.ats_type = AtsType.crawl4ai
    cat.ats_identifier = probe_result.identifier
    cat.discovery_status = "success"
    await session.commit()
    return {"id": uc.id, "ats_type": probe_result.ats_type}


@router.post("/probe", status_code=status.HTTP_200_OK)
async def probe_company(
    body: ProbeRequest,
    current_user: User = Depends(get_current_user),
):
    import dataclasses
    result = await probe_ats(careers_url=body.careers_url, name_hint=body.name)
    return {
        "ats_type": result.ats_type,
        "identifier": result.identifier,
        "probe_attempts": [dataclasses.asdict(a) for a in result.probe_attempts],
    }


@router.post("/discover", status_code=status.HTTP_202_ACCEPTED)
async def discover_companies(
    body: DiscoverRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    from backend.scrapers.discover import discover_company
    from backend.models.company import AtsType

    created = 0
    ids = []
    for name in body.names:
        name = name.strip()
        if not name:
            continue

        # If already in catalog, just link or skip
        existing_cat = (await session.execute(
            select(CompanyCatalog).where(
                CompanyCatalog.name.ilike(name)
            )
        )).scalar_one_or_none()

        if existing_cat:
            existing_uc = (await session.execute(
                select(UserCompany).where(
                    UserCompany.user_id == current_user.id,
                    UserCompany.catalog_id == existing_cat.id,
                )
            )).scalar_one_or_none()
            if not existing_uc:
                uc = UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True)
                session.add(uc)
                await session.flush()
                ids.append(uc.id)
                created += 1
            continue

        # New company: create catalog entry in "discovering" state, fire background task
        cat = CompanyCatalog(
            name=name,
            careers_url="",
            ats_type=AtsType.crawl4ai,
            source="user_submitted",
            discovery_status="discovering",
            discovery_message="Starting discovery...",
        )
        session.add(cat)
        await session.flush()

        uc = UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=False)
        session.add(uc)
        await session.flush()
        ids.append(uc.id)
        created += 1

        catalog_id = cat.id
        asyncio.create_task(discover_company(catalog_id, name))

    await session.commit()
    return {"created": created, "ids": ids}


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def import_companies(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import csv, io
    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))
    created = 0
    names = []
    for row in reader:
        name = row.get("name", "").strip()
        careers_url = row.get("careers_url", "").strip()
        if not name or not careers_url:
            continue
        existing_cat = await _find_catalog_by_url(careers_url, session)
        if existing_cat:
            existing_uc = (await session.execute(
                select(UserCompany).where(
                    UserCompany.user_id == current_user.id,
                    UserCompany.catalog_id == existing_cat.id,
                )
            )).scalar_one_or_none()
            if not existing_uc:
                session.add(UserCompany(user_id=current_user.id, catalog_id=existing_cat.id, is_active=True))
                created += 1
                names.append(name)
            continue
        probe_result = await probe_ats(careers_url=careers_url, name_hint=name)
        from backend.models.company import AtsType
        try:
            ats_enum = AtsType(probe_result.ats_type)
        except ValueError:
            ats_enum = AtsType.crawl4ai
        cat = CompanyCatalog(name=name, careers_url=careers_url, ats_type=ats_enum,
                             ats_identifier=probe_result.identifier, source="user_submitted")
        session.add(cat)
        await session.flush()
        session.add(UserCompany(user_id=current_user.id, catalog_id=cat.id, is_active=True))
        created += 1
        names.append(name)

    await session.commit()
    return {"created": created, "names": names}
