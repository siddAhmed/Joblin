# Onboarding & Company Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CSV company import in onboarding with a pre-selected default picker, add parallel ATS probing for performance, and add an agentic background discovery loop that finds a company's careers URL + ATS from just a name.

**Architecture:** A static catalog of 120+ companies seeds both onboarding (via `POST /companies/bulk`) and the agentic loop's fast path. The discovery loop uses crawl4ai + two Haiku LLM passes to find and validate careers URLs for unknown companies, running as `asyncio.create_task` background tasks. The frontend polls `GET /companies` every 4s while any company is in `discovering` state.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (Mapped/mapped_column), Alembic, asyncio, httpx, crawl4ai, anthropic SDK (new dep), React + TanStack Query, TypeScript.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/data/__init__.py` | Package init (empty) |
| Create | `backend/data/default_companies.py` | Static catalog of 120+ companies |
| Create | `backend/scrapers/discover.py` | Agentic discovery loop |
| Create | `backend/alembic/versions/b1c2d3e4f5a6_add_discovery_columns.py` | Migration: add discovery_status + discovery_message |
| Create | `tests/test_discover.py` | Tests for discovery loop |
| Modify | `backend/requirements.txt` | Add `anthropic>=0.40.0` |
| Modify | `backend/scrapers/probe.py` | Make all 6 ATS probes parallel |
| Modify | `backend/models/company.py` | Add discovery_status + discovery_message columns |
| Modify | `backend/routers/companies.py` | Add GET /defaults, POST /bulk, POST /discover, POST /{id}/resolve; update list response |
| Modify | `tests/test_companies.py` | Tests for new endpoints |
| Modify | `frontend/src/api/companies.ts` | Add Company fields + 4 new API functions |
| Modify | `frontend/src/pages/Onboarding.tsx` | Replace Step 3 with company picker |
| Modify | `frontend/src/pages/Companies.tsx` | Add By Name tab, discovering/failed row states, polling |

---

## Task 1: Default Company Catalog + GET /companies/defaults

**Files:**
- Create: `backend/data/__init__.py`
- Create: `backend/data/default_companies.py`
- Modify: `backend/routers/companies.py`
- Modify: `tests/test_companies.py`

- [ ] **Step 1: Create the data package**

```python
# backend/data/__init__.py
# (empty file)
```

- [ ] **Step 2: Create the catalog**

```python
# backend/data/default_companies.py
DEFAULT_COMPANIES = [
    {"name": "Adobe", "careers_url": "https://careers.adobe.com/us/en"},
    {"name": "Apple", "careers_url": "https://jobs.apple.com/en-us/search"},
    {"name": "Broadcom", "careers_url": "https://www.broadcom.com/company/careers"},
    {"name": "Citrix", "careers_url": "https://careers.cloud.com/"},
    {"name": "Expedia", "careers_url": "https://careers.expediagroup.com/"},
    {"name": "Google", "careers_url": "https://careers.google.com/"},
    {"name": "Indeed", "careers_url": "https://www.indeed.com/careers"},
    {"name": "InMobi", "careers_url": "https://www.inmobi.com/company/careers"},
    {"name": "Intuit", "careers_url": "https://jobs.intuit.com/"},
    {"name": "JP Morgan", "careers_url": "https://www.jpmorganchase.com/careers"},
    {"name": "LinkedIn", "careers_url": "https://careers.linkedin.com/"},
    {"name": "MathWorks", "careers_url": "https://www.mathworks.com/company/jobs/"},
    {"name": "Microsoft", "careers_url": "https://careers.microsoft.com/"},
    {"name": "Nutanix", "careers_url": "https://careers.nutanix.com/en/"},
    {"name": "Nvidia", "careers_url": "https://www.nvidia.com/en-us/about-nvidia/careers/"},
    {"name": "PhonePe", "careers_url": "https://www.phonepe.com/careers/"},
    {"name": "Salesforce", "careers_url": "https://careers.salesforce.com/en/jobs/"},
    {"name": "ServiceNow", "careers_url": "https://careers.servicenow.com/"},
    {"name": "Amazon", "careers_url": "https://www.amazon.jobs/en/"},
    {"name": "Arcesium", "careers_url": "https://www.arcesium.com/careers"},
    {"name": "Atlassian", "careers_url": "https://www.atlassian.com/company/careers"},
    {"name": "Coinbase", "careers_url": "https://www.coinbase.com/careers/positions"},
    {"name": "DE Shaw", "careers_url": "https://www.deshaw.com/careers"},
    {"name": "Flipkart", "careers_url": "https://www.flipkartcareers.com/"},
    {"name": "Goldman Sachs", "careers_url": "https://www.goldmansachs.com/careers"},
    {"name": "Harness", "careers_url": "https://www.harness.io/company/careers"},
    {"name": "Morgan Stanley", "careers_url": "https://www.morganstanley.com/careers/career-opportunities-search"},
    {"name": "Rippling", "careers_url": "https://www.rippling.com/careers"},
    {"name": "Sprinklr", "careers_url": "https://www.sprinklr.com/careers/"},
    {"name": "Tower Research Capital", "careers_url": "https://tower-research.com"},
    {"name": "Uber", "careers_url": "https://www.uber.com/us/en/careers/"},
    {"name": "Zepto", "careers_url": "https://www.zepto.com/s/careers"},
    {"name": "Zomato", "careers_url": "https://www.zomato.com/careers"},
    {"name": "AirBnB", "careers_url": "https://careers.airbnb.com/"},
    {"name": "Alphonso", "careers_url": "https://alphonso.tv/careers.html"},
    {"name": "AppDynamics", "careers_url": "https://www.appdynamics.com/company/careers"},
    {"name": "Aviso", "careers_url": "https://www.aviso.com/careers"},
    {"name": "Bloomreach", "careers_url": "https://www.bloomreach.com/en/careers"},
    {"name": "Cohesity", "careers_url": "https://www.cohesity.com/careers/"},
    {"name": "Compass", "careers_url": "https://www.compass.com/careers/jobs/"},
    {"name": "Cult.fit", "careers_url": "https://www.cult.fit/careers"},
    {"name": "Gojek", "careers_url": "https://www.gojek.io/careers"},
    {"name": "Grab", "careers_url": "https://www.grab.careers/en/"},
    {"name": "Hasura", "careers_url": "https://hasura.io/careers/"},
    {"name": "HealthifyMe", "careers_url": "https://www.healthifyme.com/careers/"},
    {"name": "Instabase", "careers_url": "https://www.instabase.com/careers"},
    {"name": "Palo Alto Networks", "careers_url": "https://jobs.paloaltonetworks.com/en"},
    {"name": "Postman", "careers_url": "https://www.postman.com/company/careers/"},
    {"name": "Practo", "careers_url": "https://www.practo.com/company/careers"},
    {"name": "Quadeye", "careers_url": "https://www.quadeye.com/careers/"},
    {"name": "Qubole", "careers_url": "https://www.qubole.com/company/careers"},
    {"name": "Rubrik", "careers_url": "https://www.rubrik.com/company/careers"},
    {"name": "ShareChat", "careers_url": "https://sharechat.com/careers"},
    {"name": "Stripe", "careers_url": "https://stripe.com/jobs"},
    {"name": "Sumo Logic", "careers_url": "https://www.sumologic.com/company/careers"},
    {"name": "Swiggy", "careers_url": "https://careers.swiggy.com/"},
    {"name": "Target", "careers_url": "https://corporate.target.com/careers"},
    {"name": "Udaan", "careers_url": "https://careers.udaan.com/"},
    {"name": "Whatfix", "careers_url": "https://whatfix.com/careers/"},
    {"name": "WorldQuant", "careers_url": "https://www.worldquant.com/careers/"},
    {"name": "ARM", "careers_url": "https://careers.arm.com/"},
    {"name": "Autodesk", "careers_url": "https://www.autodesk.com/careers"},
    {"name": "Blackbuck", "careers_url": "https://careers.blackbuck.com/"},
    {"name": "Cisco", "careers_url": "https://careers.cisco.com/"},
    {"name": "Datadog", "careers_url": "https://careers.datadoghq.com/"},
    {"name": "Directi", "careers_url": "https://careers.directi.com/"},
    {"name": "Freshworks", "careers_url": "https://www.freshworks.com/company/careers/"},
    {"name": "HashedIn by Deloitte", "careers_url": "https://hashedin.com/careers"},
    {"name": "Intel", "careers_url": "https://jobs.intel.com/en/us-jobs"},
    {"name": "MasterCard", "careers_url": "https://careers.mastercard.com/us/en"},
    {"name": "Mentor Graphics (Siemens EDA)", "careers_url": "https://jobs.sw.siemens.com/"},
    {"name": "Qualcomm", "careers_url": "https://www.qualcomm.com/company/careers"},
    {"name": "Red Hat", "careers_url": "https://www.redhat.com/en/jobs"},
    {"name": "SAP Labs", "careers_url": "https://jobs.sap.com/"},
    {"name": "Samsung", "careers_url": "https://www.samsung.com/us/careers/"},
    {"name": "Slack", "careers_url": "https://slack.com/careers"},
    {"name": "Smallcase", "careers_url": "https://smallcase.freshteam.com/jobs"},
    {"name": "Texas Instruments", "careers_url": "https://careers.ti.com/"},
    {"name": "Visa", "careers_url": "https://corporate.visa.com/en/careers.html"},
    {"name": "Zoho", "careers_url": "https://careers.zohocorp.com/jobs/careers"},
    {"name": "Box8", "careers_url": "https://box8.recruitee.com/"},
    {"name": "Cloudera", "careers_url": "https://www.cloudera.com/careers.html"},
    {"name": "Dunzo", "careers_url": "https://www.dunzo.com/careers"},
    {"name": "Jio", "careers_url": "https://careers.jio.com/"},
    {"name": "Juniper Networks", "careers_url": "https://careers.hpe.com/juniper"},
    {"name": "MakeMyTrip", "careers_url": "https://careers.makemytrip.com/"},
    {"name": "MyGate", "careers_url": "https://mygate.com/careers/"},
    {"name": "PayPal", "careers_url": "https://careers.pypl.com/home/"},
    {"name": "Razorpay", "careers_url": "https://razorpay.com/jobs/"},
    {"name": "SanDisk", "careers_url": "https://www.sandisk.com/careers/"},
    {"name": "Twilio", "careers_url": "https://jobs.twilio.com/careers"},
    {"name": "upGrad", "careers_url": "https://jobs.upgrad.com/"},
    {"name": "BigBasket", "careers_url": "https://careers.bigbasket.com/"},
    {"name": "CRED", "careers_url": "https://careers.cred.club/openings"},
    {"name": "Dream11", "careers_url": "https://www.dreamsports.group/careers"},
    {"name": "Hotstar", "careers_url": "https://www.disneycareers.com/en/hotstar-jobs/"},
    {"name": "Ola", "careers_url": "https://www.olacabs.com/careers"},
    {"name": "Paytm", "careers_url": "https://paytm.com/careers"},
    {"name": "Unacademy", "careers_url": "https://unacademy.com/careers"},
    {"name": "Walmart", "careers_url": "https://careers.walmart.com/"},
    {"name": "Wissen Technology", "careers_url": "https://careers.wissen.com/jobs/Careers"},
    {"name": "Zeta", "careers_url": "https://careers.zeta.tech/work-with-us/"},
    {"name": "Groupon", "careers_url": "https://www.grouponcareers.com/"},
    {"name": "Snowflake", "careers_url": "https://careers.snowflake.com/us/en"},
    {"name": "Truecaller", "careers_url": "https://job-boards.greenhouse.io/truecaller"},
    {"name": "Zoom", "careers_url": "https://careers.zoom.us/"},
    {"name": "Agoda", "careers_url": "https://careersatagoda.com/"},
    {"name": "Booking.com", "careers_url": "https://careers.booking.com/"},
    {"name": "ByteDance", "careers_url": "https://joinbytedance.com/"},
    {"name": "Databricks", "careers_url": "https://www.databricks.com/company/careers"},
    {"name": "Meta", "careers_url": "https://www.metacareers.com/"},
    {"name": "Spotify", "careers_url": "https://www.lifeatspotify.com/jobs"},
    {"name": "Yelp", "careers_url": "https://www.yelp.careers/us/en"},
    {"name": "Zalando", "careers_url": "https://jobs.zalando.com/en"},
    {"name": "Akamai", "careers_url": "https://jobs.akamai.com/"},
    {"name": "Auth0", "careers_url": "https://www.okta.com/company/careers/"},
    {"name": "BrowserStack", "careers_url": "https://www.browserstack.com/careers"},
    {"name": "Confluent", "careers_url": "https://careers.confluent.io/"},
    {"name": "GitHub", "careers_url": "https://www.github.careers/careers-home/jobs"},
    {"name": "GitLab", "careers_url": "https://about.gitlab.com/jobs/"},
    {"name": "Shopify", "careers_url": "https://www.shopify.com/careers"},
    {"name": "Square", "careers_url": "https://block.xyz/careers/jobs"},
    {"name": "Stack Overflow", "careers_url": "https://stackoverflow.co/company/careers/"},
    {"name": "Smallest AI", "careers_url": "https://jobs.ashbyhq.com/smallest"},
]
```

- [ ] **Step 3: Write the failing test**

Add to `tests/test_companies.py`:

```python
async def test_get_defaults_returns_catalog(client):
    response = await client.get("/api/companies/defaults")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 100
    assert all("name" in c and "careers_url" in c for c in data)
    names = [c["name"] for c in data]
    assert "Google" in names
    assert "Stripe" in names
```

- [ ] **Step 4: Run the test — expect failure**

```bash
cd C:/dev/joblin && python -m pytest tests/test_companies.py::test_get_defaults_returns_catalog -v
```

Expected: `FAILED` — 404 or AttributeError (endpoint doesn't exist yet).

- [ ] **Step 5: Add the endpoint**

At the top of `backend/routers/companies.py`, add the import after the existing imports:

```python
from backend.data.default_companies import DEFAULT_COMPANIES
```

Add the endpoint before the `@router.post("/probe")` route (keep fixed-segment routes before parameterized ones):

```python
@router.get("/defaults")
async def get_default_companies(current_user: CurrentUser):
    return DEFAULT_COMPANIES
```

- [ ] **Step 6: Run the test — expect pass**

```bash
python -m pytest tests/test_companies.py::test_get_defaults_returns_catalog -v
```

Expected: `PASSED`

- [ ] **Step 7: Commit**

```bash
git add backend/data/__init__.py backend/data/default_companies.py backend/routers/companies.py tests/test_companies.py
git commit -m "feat: add default company catalog and GET /companies/defaults"
```

---

## Task 2: Parallel ATS Probing in probe_ats()

**Files:**
- Modify: `backend/scrapers/probe.py`
- Modify: `tests/test_scrapers.py` (add new test; don't break existing)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scrapers.py` (create file if it doesn't exist, or append):

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from backend.scrapers.probe import probe_ats


async def test_probe_ats_fires_all_six_in_parallel():
    """All 6 ATS candidates are probed concurrently; greenhouse (index 0) wins."""
    called_urls = []

    async def fake_get(url, **kwargs):
        called_urls.append(url)
        m = MagicMock()
        m.status_code = 200 if "greenhouse" in url else 404
        return m

    mock_instance = MagicMock()
    mock_instance.get = fake_get
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.scrapers.probe.httpx.AsyncClient", return_value=mock_instance):
        result = await probe_ats("https://stripe.com/jobs", "stripe")

    assert len(called_urls) == 6, "All 6 ATS types must be probed"
    assert result.ats_type == "greenhouse"
    assert result.identifier == "stripe"
    assert len(result.probe_attempts) == 6


async def test_probe_ats_priority_order_respected():
    """When both greenhouse and lever return 200, greenhouse wins (lower index)."""
    async def fake_get(url, **kwargs):
        m = MagicMock()
        m.status_code = 200 if ("greenhouse" in url or "lever" in url) else 404
        return m

    mock_instance = MagicMock()
    mock_instance.get = fake_get
    mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("backend.scrapers.probe.httpx.AsyncClient", return_value=mock_instance):
        result = await probe_ats("https://example.com/careers", "example")

    assert result.ats_type == "greenhouse"
```

- [ ] **Step 2: Run the tests — expect failure**

```bash
python -m pytest tests/test_scrapers.py::test_probe_ats_fires_all_six_in_parallel tests/test_scrapers.py::test_probe_ats_priority_order_respected -v
```

Expected: `FAILED` — `AssertionError: assert len(called_urls) == 6` (sequential loop stops at first hit).

- [ ] **Step 3: Rewrite probe_ats() to use asyncio.gather**

Replace the entire `probe_ats` function in `backend/scrapers/probe.py`:

```python
import asyncio
import httpx
from dataclasses import dataclass, field


@dataclass
class ProbeAttempt:
    url: str
    status_code: int | None
    error: str | None = None


@dataclass
class ProbeResult:
    ats_type: str
    identifier: str | None
    probe_attempts: list[ProbeAttempt] = field(default_factory=list)


def _slug_from_url(url: str) -> str:
    from urllib.parse import urlparse
    parts = urlparse(url).path.strip("/").split("/")
    return parts[-1] if parts and parts[-1] else url.split("//")[-1].split(".")[0]


async def probe_ats(careers_url: str, name_hint: str) -> ProbeResult:
    url_slug = _slug_from_url(careers_url)
    generic_segments = {"jobs", "careers", "job", "career", "openings", "positions", ""}
    if url_slug and url_slug.lower() not in generic_segments:
        slug = url_slug
    else:
        slug = name_hint.lower().replace(" ", "-")

    candidates = [
        ("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"),
        ("lever", f"https://api.lever.co/v0/postings/{slug}"),
        ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}"),
        ("workable", f"https://{slug}.workable.com/spi/v3/jobs"),
        ("smartrecruiters", f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"),
        ("workday", careers_url),
    ]

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:

        async def try_one(ats_type: str, url: str) -> tuple[str, str, int | None, str | None]:
            try:
                resp = await client.get(url)
                return (ats_type, url, resp.status_code, None)
            except Exception as exc:
                return (ats_type, url, None, str(exc))

        results = await asyncio.gather(*[try_one(t, u) for t, u in candidates])

    attempts = [
        ProbeAttempt(url=url, status_code=status_code, error=error)
        for _, url, status_code, error in results
    ]

    for ats_type, _, status_code, _ in results:
        if status_code == 200:
            if ats_type == "workday":
                if "workday.com" in careers_url or "myworkdayjobs.com" in careers_url:
                    return ProbeResult(ats_type="workday", identifier=careers_url, probe_attempts=attempts)
            else:
                return ProbeResult(ats_type=ats_type, identifier=slug, probe_attempts=attempts)

    return ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=attempts)
```

- [ ] **Step 4: Run the new tests — expect pass**

```bash
python -m pytest tests/test_scrapers.py::test_probe_ats_fires_all_six_in_parallel tests/test_scrapers.py::test_probe_ats_priority_order_respected -v
```

Expected: `PASSED`

- [ ] **Step 5: Run existing companies tests to confirm no regression**

```bash
python -m pytest tests/test_companies.py -v
```

Expected: all `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/scrapers/probe.py tests/test_scrapers.py
git commit -m "perf: probe all 6 ATS types in parallel in probe_ats()"
```

---

## Task 3: POST /companies/bulk Endpoint

**Files:**
- Modify: `backend/routers/companies.py`
- Modify: `tests/test_companies.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_companies.py`:

```python
async def test_bulk_add_companies(client):
    mock_gh = ProbeResult(ats_type="greenhouse", identifier="stripe", probe_attempts=[])
    mock_crawl = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])

    with patch("backend.routers.companies.probe_ats", side_effect=[mock_gh, mock_crawl]):
        response = await client.post("/api/companies/bulk", json=[
            {"name": "Stripe", "careers_url": "https://stripe.com/jobs"},
            {"name": "Acme", "careers_url": "https://acme.com/careers"},
        ])

    assert response.status_code == 201
    assert response.json()["created"] == 2

    list_resp = await client.get("/api/companies")
    names = [c["name"] for c in list_resp.json()]
    assert "Stripe" in names
    assert "Acme" in names


async def test_bulk_add_empty_list(client):
    response = await client.post("/api/companies/bulk", json=[])
    assert response.status_code == 201
    assert response.json()["created"] == 0
```

- [ ] **Step 2: Run — expect failure**

```bash
python -m pytest tests/test_companies.py::test_bulk_add_companies tests/test_companies.py::test_bulk_add_empty_list -v
```

Expected: `FAILED` — 404 (endpoint not found).

- [ ] **Step 3: Add the bulk endpoint and update the list response**

In `backend/routers/companies.py`, add the `BulkCompanyItem` model after `ProbeRequest`:

```python
class BulkCompanyItem(BaseModel):
    name: str
    careers_url: str
```

Add the `asyncio` import at the top (after existing imports):

```python
import asyncio
```

Add the bulk endpoint (after the `/defaults` route):

```python
@router.post("/bulk", status_code=201)
async def bulk_add_companies(
    items: list[BulkCompanyItem],
    session: Session,
    current_user: CurrentUser,
):
    sem = asyncio.Semaphore(20)

    async def probe_and_build(item: BulkCompanyItem) -> Company:
        async with sem:
            probe = await probe_ats(item.careers_url, item.name)
            return Company(
                name=item.name,
                careers_url=item.careers_url,
                ats_type=AtsType(probe.ats_type),
                ats_identifier=probe.identifier,
                user_id=current_user.id,
            )

    companies = await asyncio.gather(*[probe_and_build(item) for item in items])
    for company in companies:
        session.add(company)
    await session.commit()
    return {"created": len(companies)}
```

Also update `GET /companies` to include the new fields (add `discovery_status` and `discovery_message` to the return dict — these will be `None` / `"none"` until Task 4's migration runs, but adding them to the response now keeps the router and model in sync):

```python
@router.get("")
async def list_companies(session: Session, current_user: CurrentUser):
    rows = (await session.execute(
        select(Company).where(Company.user_id == current_user.id).order_by(Company.name)
    )).scalars().all()
    return [
        {
            "id": c.id, "name": c.name, "careers_url": c.careers_url,
            "ats_type": c.ats_type, "is_active": c.is_active,
            "quarantine_count": c.quarantine_count, "quarantined_at": c.quarantined_at,
            "quarantine_reason": c.quarantine_reason,
            "discovery_status": getattr(c, "discovery_status", "none"),
            "discovery_message": getattr(c, "discovery_message", None),
        }
        for c in rows
    ]
```

(`getattr` with default is used so the code works before the migration runs. Remove the defaults after Task 4.)

- [ ] **Step 4: Run — expect pass**

```bash
python -m pytest tests/test_companies.py::test_bulk_add_companies tests/test_companies.py::test_bulk_add_empty_list -v
```

Expected: `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/test_companies.py -v
```

Expected: all `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/companies.py tests/test_companies.py
git commit -m "feat: add POST /companies/bulk with parallel probing"
```

---

## Task 4: Discovery Columns Migration

**Files:**
- Create: `backend/alembic/versions/b1c2d3e4f5a6_add_discovery_columns.py`
- Modify: `backend/models/company.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/b1c2d3e4f5a6_add_discovery_columns.py
"""add discovery columns

Revision ID: b1c2d3e4f5a6
Revises: 7cd1193b651b
Create Date: 2026-06-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "7cd1193b651b"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("discovery_status", sa.String(), nullable=False, server_default="none"),
    )
    op.add_column(
        "companies",
        sa.Column("discovery_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "discovery_message")
    op.drop_column("companies", "discovery_status")
```

- [ ] **Step 2: Add the columns to the Company model**

In `backend/models/company.py`, add `Text` to the sqlalchemy imports:

```python
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
```

Add the two new fields at the end of the `Company` class (before the closing of the class, after `user_id`):

```python
    discovery_status: Mapped[str] = mapped_column(
        String, nullable=False, default="none", server_default="none"
    )
    discovery_message: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 3: Run the migration against the dev database**

```bash
cd C:/dev/joblin && python -m alembic -c backend/alembic.ini upgrade head
```

Expected output includes: `Running upgrade 7cd1193b651b -> b1c2d3e4f5a6, add discovery columns`

If `alembic.ini` is at the project root, use `alembic upgrade head` instead. Check where `alembic.ini` lives:

```bash
ls backend/alembic.ini 2>/dev/null || ls alembic.ini 2>/dev/null
```

- [ ] **Step 4: Update the list endpoint to remove the getattr guards**

Now that the migration has run and the model has the columns, update the `GET /companies` list in `backend/routers/companies.py` to access the attributes directly:

```python
            "discovery_status": c.discovery_status,
            "discovery_message": c.discovery_message,
```

(Replace the two `getattr(...)` lines from Task 3.)

- [ ] **Step 5: Run the full test suite**

The in-memory SQLite test DB is created fresh each test run using `Base.metadata.create_all`, which picks up the new model columns automatically — no migration needed in tests.

```bash
python -m pytest tests/test_companies.py -v
```

Expected: all `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/b1c2d3e4f5a6_add_discovery_columns.py backend/models/company.py backend/routers/companies.py
git commit -m "feat: add discovery_status and discovery_message columns to companies"
```

---

## Task 5: Agentic Discovery Loop

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/scrapers/discover.py`
- Create: `tests/test_discover.py`

- [ ] **Step 1: Add anthropic to requirements**

In `backend/requirements.txt`, add after the `groq` line:

```
anthropic>=0.40.0
```

Install it:

```bash
pip install anthropic
```

- [ ] **Step 2: Write the catalog fast-path test**

Create `tests/test_discover.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.scrapers.discover import discover_company
from backend.scrapers.probe import ProbeResult


async def test_catalog_fastpath_skips_web_search():
    """When name matches catalog, web search is skipped and probe_ats is called with the known URL."""
    mock_probe = ProbeResult(ats_type="greenhouse", identifier="google", probe_attempts=[])

    with (
        patch("backend.scrapers.discover.probe_ats", return_value=mock_probe) as mock_pa,
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock),
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock) as mock_resolve,
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock) as mock_search,
    ):
        await discover_company(1, "Google")

    mock_search.assert_not_called()
    mock_resolve.assert_awaited_once_with(1, "greenhouse", "google", "https://careers.google.com/")


async def test_catalog_lookup_case_insensitive():
    """Catalog lookup is case-insensitive ('google' matches 'Google')."""
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])

    with (
        patch("backend.scrapers.discover.probe_ats", return_value=mock_probe),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock),
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock) as mock_resolve,
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock) as mock_search,
    ):
        await discover_company(1, "google")

    mock_search.assert_not_called()
    mock_resolve.assert_awaited_once()
```

- [ ] **Step 3: Run catalog tests — expect failure**

```bash
python -m pytest tests/test_discover.py::test_catalog_fastpath_skips_web_search tests/test_discover.py::test_catalog_lookup_case_insensitive -v
```

Expected: `FAILED` — `ModuleNotFoundError` (discover.py doesn't exist).

- [ ] **Step 4: Create backend/scrapers/discover.py**

```python
import asyncio
import json
import re
from urllib.parse import quote_plus

import anthropic
from crawl4ai import AsyncWebCrawler
from sqlalchemy import select

from backend.data.default_companies import DEFAULT_COMPANIES
from backend.database import AsyncSessionLocal
from backend.models.company import AtsType, Company
from backend.scrapers.probe import ProbeResult, probe_ats


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _heuristic_candidates(name: str) -> list[str]:
    slug = _slugify(name)
    return [
        f"https://careers.{slug}.com/",
        f"https://jobs.{slug}.com/",
        f"https://{slug}.com/careers",
    ]


async def _search_web(name: str) -> list[str]:
    query = quote_plus(f"{name} careers jobs")
    url = f"https://html.duckduckgo.com/html/?q={query}"
    try:
        async with AsyncWebCrawler(headless=True) as crawler:
            result = await crawler.arun(url=url)
            text = result.markdown or ""
            found = re.findall(r"https?://[^\s\)\"\'\]>]+", text)
            blocked = {"duckduckgo.com", "bing.com", "google.com", "w3.org"}
            filtered = [
                u for u in found
                if not any(d in u for d in blocked) and len(u) < 200
            ]
            return list(dict.fromkeys(filtered))[:7]
    except Exception:
        return []


async def _llm_filter(
    name: str, candidates: list[str], client: anthropic.AsyncAnthropic
) -> list[str]:
    prompt = (
        f"Company: {name}\n\nCandidate URLs:\n"
        + "\n".join(f"- {u}" for u in candidates)
        + f"\n\nReturn a JSON array of URLs that are most likely the official careers portal "
        f"for {name}. Exclude LinkedIn, Glassdoor, Indeed, Levels.fyi, news articles, "
        f'Wikipedia. Order by likelihood. Example: ["https://..."]\n'
        f"If none look right, return all of them unchanged."
    )
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text
    m = re.search(r"\[.*?\]", text, re.DOTALL)
    if m:
        try:
            urls = json.loads(m.group())
            result = [u for u in urls if isinstance(u, str)]
            return result[:10] if result else candidates
        except Exception:
            pass
    return candidates


async def _llm_analyze_page(
    name: str, markdown: str, client: anthropic.AsyncAnthropic
) -> dict | None:
    prompt = (
        f"You are analyzing a careers page for '{name}'.\n\n"
        f"Page content:\n{markdown[:3000]}\n\n"
        f"Identify the ATS or job board system. Options: "
        f"greenhouse, lever, ashby, workable, smartrecruiters, workday, crawl4ai.\n"
        f"Also identify the canonical jobs listing URL.\n\n"
        f'Respond ONLY as JSON: {{"ats_type": "...", "careers_url": "https://..."}}\n'
        f'If you cannot determine the ATS, use "crawl4ai".'
    )
    msg = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text
    m = re.search(r"\{.*?\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None


async def _update_status(company_id: int, message: str, status: str = "discovering") -> None:
    async with AsyncSessionLocal() as session:
        company = (await session.execute(
            select(Company).where(Company.id == company_id)
        )).scalar_one_or_none()
        if company:
            company.discovery_message = message
            company.discovery_status = status
            await session.commit()


async def _resolve(
    company_id: int, ats_type: str, identifier: str | None, careers_url: str
) -> None:
    async with AsyncSessionLocal() as session:
        company = (await session.execute(
            select(Company).where(Company.id == company_id)
        )).scalar_one_or_none()
        if company:
            company.ats_type = AtsType(ats_type)
            company.ats_identifier = identifier
            company.careers_url = careers_url
            company.discovery_status = "none"
            company.discovery_message = None
            company.is_active = True
            await session.commit()


async def _run_discovery(company_id: int, name: str) -> None:
    client = anthropic.AsyncAnthropic()

    # Step 1: Catalog fast path
    catalog_entry = next(
        (c for c in DEFAULT_COMPANIES if c["name"].lower() == name.lower()), None
    )
    if catalog_entry:
        await _update_status(company_id, "Probing known URL...")
        result = await probe_ats(catalog_entry["careers_url"], name)
        await _resolve(company_id, result.ats_type, result.identifier, catalog_entry["careers_url"])
        return

    # Step 2: Web search + heuristics (up to 10 candidates)
    await _update_status(company_id, "Searching web...")
    search_urls = await _search_web(name)
    heuristic_urls = _heuristic_candidates(name)
    all_candidates = list(dict.fromkeys(search_urls + heuristic_urls))[:10]

    if not all_candidates:
        await _update_status(company_id, "Could not find — paste URL manually", "failed")
        return

    # Step 3: LLM pass 1 — filter/rank candidates
    await _update_status(company_id, "Filtering candidates...")
    filtered = await _llm_filter(name, all_candidates, client)

    # Step 4: Parallel ATS probe all candidates
    await _update_status(company_id, "Probing ATS APIs...")

    async def probe_candidate(url: str) -> tuple[str, ProbeResult] | None:
        try:
            result = await probe_ats(url, name)
            return (url, result)
        except Exception:
            return None

    probe_results = await asyncio.gather(*[probe_candidate(u) for u in filtered])

    best_crawl4ai_url: str | None = None
    for item in probe_results:
        if item is None:
            continue
        url, result = item
        if result.ats_type != "crawl4ai":
            await _resolve(company_id, result.ats_type, result.identifier, url)
            return
        if best_crawl4ai_url is None:
            best_crawl4ai_url = url

    # Step 5: LLM pass 2 — analyze the top-ranked page
    top_url = filtered[0] if filtered else best_crawl4ai_url
    if top_url:
        await _update_status(company_id, "Analyzing careers page...")
        try:
            async with AsyncWebCrawler(headless=True) as crawler:
                crawl_result = await crawler.arun(url=top_url)
                markdown = crawl_result.markdown or ""
            analysis = await _llm_analyze_page(name, markdown, client)
            if analysis and analysis.get("careers_url"):
                careers_url = analysis["careers_url"]
                reprobe = await probe_ats(careers_url, name)
                resolved_ats = (
                    reprobe.ats_type
                    if reprobe.ats_type != "crawl4ai"
                    else analysis.get("ats_type", "crawl4ai")
                )
                await _resolve(company_id, resolved_ats, reprobe.identifier, careers_url)
                return
        except Exception:
            pass

    # Step 6: Fallback
    fallback_url = best_crawl4ai_url or (filtered[0] if filtered else None)
    if fallback_url:
        await _resolve(company_id, "crawl4ai", None, fallback_url)
    else:
        await _update_status(company_id, "Could not find — paste URL manually", "failed")


async def discover_company(company_id: int, name: str) -> None:
    try:
        await asyncio.wait_for(_run_discovery(company_id, name), timeout=90.0)
    except (asyncio.TimeoutError, Exception):
        await _update_status(company_id, "Could not find — paste URL manually", "failed")
```

- [ ] **Step 5: Run catalog tests — expect pass**

```bash
python -m pytest tests/test_discover.py::test_catalog_fastpath_skips_web_search tests/test_discover.py::test_catalog_lookup_case_insensitive -v
```

Expected: `PASSED`

- [ ] **Step 6: Write web-search + ATS-probe path tests**

Add to `tests/test_discover.py`:

```python
async def test_unknown_company_probes_candidates():
    """Unknown company triggers web search, LLM filter, and ATS probe."""
    mock_probe_crawl = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    mock_probe_ashby = ProbeResult(ats_type="ashby", identifier="acmecorp", probe_attempts=[])

    # probe_ats is called multiple times: first returns crawl4ai (for web candidates),
    # then returns ashby (for one of the heuristic candidates)
    with (
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock,
              return_value=["https://acmecorp.io/jobs"]),
        patch("backend.scrapers.discover._llm_filter", new_callable=AsyncMock,
              side_effect=lambda name, candidates, client: candidates),
        patch("backend.scrapers.discover.probe_ats",
              side_effect=[mock_probe_crawl, mock_probe_ashby, mock_probe_crawl]),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock),
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock) as mock_resolve,
        patch("backend.scrapers.discover.anthropic.AsyncAnthropic"),
    ):
        await discover_company(42, "Acme Corp")

    mock_resolve.assert_awaited_once()
    call_args = mock_resolve.call_args[0]
    assert call_args[0] == 42
    assert call_args[1] == "ashby"


async def test_timeout_marks_company_failed():
    """When discovery exceeds 90s, company is marked failed."""
    async def slow(*args, **kwargs):
        raise asyncio.TimeoutError()

    with (
        patch("backend.scrapers.discover._run_discovery", side_effect=slow),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock) as mock_status,
    ):
        await discover_company(99, "Slow Corp")

    mock_status.assert_awaited_with(99, "Could not find — paste URL manually", "failed")


async def test_no_candidates_marks_failed():
    """When web search returns nothing and heuristics fail probing, mark failed."""
    mock_probe = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])

    with (
        patch("backend.scrapers.discover._search_web", new_callable=AsyncMock, return_value=[]),
        patch("backend.scrapers.discover._heuristic_candidates", return_value=[]),
        patch("backend.scrapers.discover._update_status", new_callable=AsyncMock) as mock_status,
        patch("backend.scrapers.discover._resolve", new_callable=AsyncMock),
        patch("backend.scrapers.discover.anthropic.AsyncAnthropic"),
    ):
        await discover_company(7, "Nonexistent Co")

    mock_status.assert_awaited_with(7, "Could not find — paste URL manually", "failed")
```

- [ ] **Step 7: Run all discover tests — expect pass**

```bash
python -m pytest tests/test_discover.py -v
```

Expected: all `PASSED`

- [ ] **Step 8: Commit**

```bash
git add backend/requirements.txt backend/scrapers/discover.py tests/test_discover.py
git commit -m "feat: agentic company discovery loop with web search + dual LLM passes"
```

---

## Task 6: POST /companies/discover + POST /companies/{id}/resolve

**Files:**
- Modify: `backend/routers/companies.py`
- Modify: `tests/test_companies.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_companies.py`:

```python
async def test_discover_creates_companies_in_discovering_state(client):
    with patch("backend.routers.companies.asyncio.create_task") as mock_task, \
         patch("backend.routers.companies.discover_company", new_callable=AsyncMock):
        response = await client.post("/api/companies/discover", json={"names": ["Anthropic", "Mistral"]})

    assert response.status_code == 202
    data = response.json()
    assert data["created"] == 2
    assert len(data["ids"]) == 2

    list_resp = await client.get("/api/companies")
    companies = list_resp.json()
    statuses = {c["name"]: c["discovery_status"] for c in companies}
    assert statuses["Anthropic"] == "discovering"
    assert statuses["Mistral"] == "discovering"


async def test_resolve_company_runs_probe_and_clears_status(client):
    mock_crawl = ProbeResult(ats_type="crawl4ai", identifier=None, probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_crawl):
        create_resp = await client.post(
            "/api/companies",
            json={"name": "SomeCo", "careers_url": "https://some.co/jobs"},
        )
    company_id = create_resp.json()["id"]

    # Manually set it to failed state
    # (in production this would happen via the discover loop)

    mock_gh = ProbeResult(ats_type="greenhouse", identifier="someco", probe_attempts=[])
    with patch("backend.routers.companies.probe_ats", return_value=mock_gh):
        resolve_resp = await client.post(
            f"/api/companies/{company_id}/resolve",
            json={"careers_url": "https://someco.greenhouse.io/"},
        )

    assert resolve_resp.status_code == 200
    assert resolve_resp.json()["ats_type"] == "greenhouse"

    list_resp = await client.get("/api/companies")
    company = next(c for c in list_resp.json() if c["id"] == company_id)
    assert company["discovery_status"] == "none"
```

- [ ] **Step 2: Run — expect failure**

```bash
python -m pytest tests/test_companies.py::test_discover_creates_companies_in_discovering_state tests/test_companies.py::test_resolve_company_runs_probe_and_clears_status -v
```

Expected: `FAILED` — 404 (endpoints not found).

- [ ] **Step 3: Add the two new endpoints to backend/routers/companies.py**

Add the import at the top:

```python
import asyncio
from backend.scrapers.discover import discover_company
```

(If `asyncio` is already imported from Task 3, skip the duplicate.)

Add the `DiscoverRequest` and `ResolveRequest` models after `BulkCompanyItem`:

```python
class DiscoverRequest(BaseModel):
    names: list[str]


class ResolveRequest(BaseModel):
    careers_url: str
```

Add the `/discover` endpoint after `/bulk`:

```python
@router.post("/discover", status_code=202)
async def discover_companies(
    req: DiscoverRequest,
    session: Session,
    current_user: CurrentUser,
):
    companies = []
    for name in req.names:
        name = name.strip()
        if not name:
            continue
        company = Company(
            name=name,
            careers_url="",
            ats_type=AtsType.crawl4ai,
            is_active=False,
            discovery_status="discovering",
            discovery_message="Queued...",
            user_id=current_user.id,
        )
        session.add(company)
        companies.append((company, name))

    await session.flush()   # assigns IDs without committing
    await session.commit()  # rows now visible to background tasks

    for company, name in companies:
        asyncio.create_task(discover_company(company.id, name))

    return {"created": len(companies), "ids": [c.id for c, _ in companies]}
```

Add the `/resolve` endpoint after the existing `/{company_id}/retry`:

```python
@router.post("/{company_id}/resolve")
async def resolve_company(
    company_id: int,
    req: ResolveRequest,
    session: Session,
    current_user: CurrentUser,
):
    company = (await session.execute(
        select(Company).where(Company.id == company_id, Company.user_id == current_user.id)
    )).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    probe = await probe_ats(req.careers_url, company.name)
    company.careers_url = req.careers_url
    company.ats_type = AtsType(probe.ats_type)
    company.ats_identifier = probe.identifier
    company.discovery_status = "none"
    company.discovery_message = None
    company.is_active = True
    await session.commit()
    return {"id": company.id, "ats_type": company.ats_type}
```

- [ ] **Step 4: Run — expect pass**

```bash
python -m pytest tests/test_companies.py::test_discover_creates_companies_in_discovering_state tests/test_companies.py::test_resolve_company_runs_probe_and_clears_status -v
```

Expected: `PASSED`

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all `PASSED`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/companies.py tests/test_companies.py
git commit -m "feat: add POST /companies/discover and POST /companies/{id}/resolve"
```

---

## Task 7: Frontend API Layer

**Files:**
- Modify: `frontend/src/api/companies.ts`

- [ ] **Step 1: Update the Company interface and add new API functions**

Replace the entire content of `frontend/src/api/companies.ts`:

```typescript
import { api } from "./client";

export interface Company {
  id: number;
  name: string;
  careers_url: string;
  ats_type: string;
  is_active: boolean;
  quarantine_count: number;
  quarantined_at: string | null;
  quarantine_reason: string | null;
  discovery_status: "none" | "discovering" | "failed";
  discovery_message: string | null;
}

export interface ProbeResult {
  ats_type: string;
  identifier: string | null;
  probe_attempts: Array<{ url: string; status_code: number | null; error: string | null }>;
}

export interface DefaultCompany {
  name: string;
  careers_url: string;
}

export const companiesApi = {
  list: () => api.get<Company[]>("/companies").then((r) => r.data),
  defaults: () => api.get<DefaultCompany[]>("/companies/defaults").then((r) => r.data),
  probe: (name: string, careers_url: string) =>
    api.post<ProbeResult>("/companies/probe", { name, careers_url }).then((r) => r.data),
  add: (name: string, careers_url: string) =>
    api.post("/companies", { name, careers_url }).then((r) => r.data),
  bulk: (items: DefaultCompany[]) =>
    api.post<{ created: number }>("/companies/bulk", items).then((r) => r.data),
  discover: (names: string[]) =>
    api.post<{ created: number; ids: number[] }>("/companies/discover", { names }).then((r) => r.data),
  resolve: (id: number, careers_url: string) =>
    api.post(`/companies/${id}/resolve`, { careers_url }).then((r) => r.data),
  update: (
    id: number,
    data: Partial<{ css_selector: string; is_active: boolean; ats_type: string; ats_identifier: string }>
  ) => api.patch(`/companies/${id}`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/companies/${id}`),
  retry: (id: number) => api.post(`/companies/${id}/retry`).then((r) => r.data),
  importCsv: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api
      .post("/companies/import", form, { headers: { "Content-Type": "multipart/form-data" } })
      .then((r) => r.data);
  },
};
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
cd C:/dev/joblin/frontend && npx tsc --noEmit
```

Expected: no errors related to `companies.ts`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/companies.ts
git commit -m "feat: extend companies API client with bulk, discover, resolve, defaults"
```

---

## Task 8: Onboarding Step 3 Replacement

**Files:**
- Modify: `frontend/src/pages/Onboarding.tsx`

- [ ] **Step 1: Replace step 3 in Onboarding.tsx**

Replace the entire file content:

```tsx
import { useState, useEffect } from "react";
import { useQueryClient, useMutation, useQuery } from "@tanstack/react-query";
import { settingsApi } from "@/api/settings";
import { companiesApi } from "@/api/companies";
import type { DefaultCompany } from "@/api/companies";
import { runsApi } from "@/api/runs";

type Step = 1 | 2 | 3 | 4;

export function Onboarding({ onComplete }: { onComplete: () => void }) {
  const [step, setStep] = useState<Step>(1);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [testRunId, setTestRunId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [deselected, setDeselected] = useState<Set<string>>(new Set());
  const qc = useQueryClient();

  const { data: defaultCompanies = [] } = useQuery<DefaultCompany[]>({
    queryKey: ["companies-defaults"],
    queryFn: companiesApi.defaults,
    enabled: step === 3,
  });

  const filteredCompanies = defaultCompanies.filter((c) =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const selectedCount = defaultCompanies.length - deselected.size;

  const toggleCompany = (name: string) => {
    setDeselected((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const selectAll = () => setDeselected(new Set());
  const deselectAll = () =>
    setDeselected(new Set(defaultCompanies.map((c) => c.name)));

  const saveWebhook = useMutation({
    mutationFn: () => settingsApi.update({ discord_webhook_url: webhookUrl }),
    onSuccess: () => setStep(2),
  });

  const applyPreset = useMutation({
    mutationFn: () => settingsApi.applyPreset(selectedPreset!),
    onSuccess: () => setStep(3),
  });

  const importCompanies = useMutation({
    mutationFn: async () => {
      const selected = defaultCompanies.filter((c) => !deselected.has(c.name));
      await companiesApi.bulk(selected);
    },
    onSuccess: () => setStep(4),
  });

  const startTestRun = useMutation({
    mutationFn: () => runsApi.start({ preview: true }),
    onSuccess: (data) => setTestRunId(data.id),
  });

  const finish = () => {
    qc.invalidateQueries({ queryKey: ["companies"] });
    qc.invalidateQueries({ queryKey: ["onboarding-status"] });
    onComplete();
  };

  const stepLabels = ["Discord", "Criteria", "Companies", "Test run"];

  return (
    <div className="min-h-screen bg-[#0d0d0d] flex items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-[#e5e5e5]">
            Welcome to Job<span className="text-[#4e9eff]">lin</span>
          </h1>
          <p className="text-sm text-[#666] mt-1">Let's get you set up in 4 steps.</p>
        </div>

        <div className="flex gap-1 mb-6">
          {stepLabels.map((label, i) => (
            <div key={label} className="flex-1 text-center">
              <div className={`h-1 rounded mb-1 ${i + 1 <= step ? "bg-[#4e9eff]" : "bg-[#222]"}`} />
              <span className={`text-[10px] ${i + 1 === step ? "text-[#4e9eff]" : "text-[#555]"}`}>
                {label}
              </span>
            </div>
          ))}
        </div>

        <div className="border border-[#2a2a2a] rounded-xl p-6 bg-[#111]">
          {step === 1 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 1: Discord webhook</h2>
              <p className="text-xs text-[#666] mb-3">
                Create a webhook in your Discord server settings and paste the URL below.
                Joblin will notify you when strong matches are found.
              </p>
              <input
                value={webhookUrl}
                onChange={(e) => setWebhookUrl(e.target.value)}
                placeholder="https://discord.com/api/webhooks/..."
                className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] mb-3"
              />
              <div className="flex gap-2">
                <button
                  onClick={() => saveWebhook.mutate()}
                  disabled={saveWebhook.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]"
                >
                  {saveWebhook.isPending ? "Saving..." : "Save and continue"}
                </button>
                <button onClick={() => setStep(2)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip for now
                </button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 2: Choose a job criteria preset</h2>
              <div className="space-y-2 mb-4">
                {[
                  { name: "backend-generalist", label: "Backend generalist", desc: "Python, distributed systems, infrastructure" },
                  { name: "python-ml", label: "Python ML engineer", desc: "ML platform, MLOps, data science" },
                  { name: "frontend", label: "Frontend engineer", desc: "React, TypeScript, product UI" },
                ].map((p) => (
                  <button
                    key={p.name}
                    onClick={() => setSelectedPreset(p.name)}
                    className={`w-full text-left border rounded-lg px-4 py-3 transition-colors ${
                      selectedPreset === p.name
                        ? "border-[#4e9eff] bg-[#0e2040]"
                        : "border-[#2a2a2a] bg-[#0a0a0a] hover:bg-[#111]"
                    }`}
                  >
                    <div className="text-sm text-[#e5e5e5]">{p.label}</div>
                    <div className="text-[11px] text-[#666]">{p.desc}</div>
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => applyPreset.mutate()}
                  disabled={!selectedPreset || applyPreset.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                >
                  {applyPreset.isPending ? "Applying..." : "Apply and continue"}
                </button>
                <button onClick={() => setStep(3)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div>
              <h2 className="text-sm font-semibold mb-1">Step 3: Choose companies to track</h2>
              <p className="text-xs text-[#666] mb-3">
                All companies are pre-selected. Deselect any you don't want.
              </p>

              {/* Controls */}
              <div className="flex items-center gap-2 mb-2">
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Filter companies..."
                  className="flex-1 bg-[#0d0d0d] border border-[#2a2a2a] rounded px-2 py-1.5 text-xs text-[#e5e5e5]"
                />
                <span className="text-[10px] text-[#555]">{selectedCount} selected</span>
                <button onClick={selectAll} className="text-[10px] text-[#4e9eff] hover:underline">
                  All
                </button>
                <button onClick={deselectAll} className="text-[10px] text-[#555] hover:underline">
                  None
                </button>
              </div>

              {/* Scrollable company list */}
              <div className="h-64 overflow-y-auto border border-[#1e1e1e] rounded bg-[#0a0a0a] p-2 mb-3">
                {defaultCompanies.length === 0 ? (
                  <p className="text-[#555] text-xs text-center mt-8">Loading...</p>
                ) : filteredCompanies.length === 0 ? (
                  <p className="text-[#555] text-xs text-center mt-8">No matches</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {filteredCompanies.map((c) => {
                      const selected = !deselected.has(c.name);
                      return (
                        <button
                          key={c.name}
                          onClick={() => toggleCompany(c.name)}
                          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${
                            selected
                              ? "border-[#4e9eff] bg-[#0e2040] text-[#4e9eff]"
                              : "border-[#2a2a2a] bg-transparent text-[#555]"
                          }`}
                        >
                          {c.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => importCompanies.mutate()}
                  disabled={selectedCount === 0 || importCompanies.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                >
                  {importCompanies.isPending
                    ? "Adding companies..."
                    : `Add ${selectedCount} companies and continue`}
                </button>
                <button onClick={() => setStep(4)} className="text-xs text-[#555] hover:text-[#888]">
                  Skip
                </button>
              </div>
            </div>
          )}

          {step === 4 && (
            <div>
              <h2 className="text-sm font-semibold mb-3">Step 4: Test run</h2>
              <p className="text-xs text-[#666] mb-4">
                Run a preview scrape to see results before enabling the scheduler. No Discord
                messages will be sent.
              </p>
              {!testRunId ? (
                <button
                  onClick={() => startTestRun.mutate()}
                  disabled={startTestRun.isPending}
                  className="text-xs border border-[#4e9eff] rounded px-4 py-2 text-[#4e9eff] bg-[#0e2040]"
                >
                  {startTestRun.isPending ? "Starting..." : "Start preview run"}
                </button>
              ) : (
                <div className="text-xs text-[#888] mb-4">
                  Preview run #{testRunId} started. Check the Runs screen for results.
                </div>
              )}
              <div className="mt-4">
                <button
                  onClick={finish}
                  className="text-xs border border-[#34d399] rounded px-4 py-2 text-[#34d399] bg-[#0d2018]"
                >
                  Finish setup and go to Dashboard
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
cd C:/dev/joblin/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Onboarding.tsx
git commit -m "feat: replace onboarding CSV import with pre-selected company picker"
```

---

## Task 9: Companies Page — By Name Modal + Discovering/Failed Row States

**Files:**
- Modify: `frontend/src/pages/Companies.tsx`

- [ ] **Step 1: Replace Companies.tsx**

```tsx
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { companiesApi } from "@/api/companies";
import type { Company, ProbeResult } from "@/api/companies";

function AddModal({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<"url" | "name">("url");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [probe, setProbe] = useState<ProbeResult | null>(null);
  const [probing, setProbing] = useState(false);
  const [nameInput, setNameInput] = useState("");
  const qc = useQueryClient();

  const add = useMutation({
    mutationFn: () => companiesApi.add(name, url),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      onClose();
    },
  });

  const discoverByName = useMutation({
    mutationFn: () =>
      companiesApi.discover(
        nameInput
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean)
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["companies"] });
      onClose();
    },
  });

  const handleProbe = async () => {
    setProbing(true);
    try {
      setProbe(await companiesApi.probe(name, url));
    } finally {
      setProbing(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#111] border border-[#2a2a2a] rounded-xl p-6 w-full max-w-md">
        <h2 className="text-sm font-semibold mb-3">Add Company</h2>

        {/* Tab toggle */}
        <div className="flex gap-1 mb-4 border border-[#2a2a2a] rounded-lg p-0.5 w-fit">
          <button
            onClick={() => setTab("url")}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              tab === "url" ? "bg-[#1e2a3a] text-[#4e9eff]" : "text-[#555] hover:text-[#888]"
            }`}
          >
            By URL
          </button>
          <button
            onClick={() => setTab("name")}
            className={`text-xs px-3 py-1.5 rounded-md transition-colors ${
              tab === "name" ? "bg-[#1e2a3a] text-[#4e9eff]" : "text-[#555] hover:text-[#888]"
            }`}
          >
            By Name
          </button>
        </div>

        {tab === "url" && (
          <>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Company name"
              className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm mb-2 text-[#e5e5e5]"
            />
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Careers URL"
              className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm mb-3 text-[#e5e5e5]"
            />
            {probe && (
              <div className="mb-3 text-xs border border-[#2a2a2a] rounded p-2 bg-[#0a0a0a]">
                <div className="text-[#888]">
                  Detected: <span className="text-[#4e9eff]">{probe.ats_type}</span>
                </div>
                {probe.probe_attempts.map((a, i) => (
                  <div key={i} className="text-[#555] mt-0.5">
                    {a.url} -- {a.status_code ?? a.error}
                  </div>
                ))}
              </div>
            )}
            <div className="flex gap-2">
              <button
                onClick={handleProbe}
                disabled={!name || !url || probing}
                className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888]"
              >
                {probing ? "Probing..." : "Probe ATS"}
              </button>
              <button
                onClick={() => add.mutate()}
                disabled={!name || !url || add.isPending}
                className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]"
              >
                {add.isPending ? "Adding..." : "Add"}
              </button>
              <button
                onClick={onClose}
                className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888] ml-auto"
              >
                Cancel
              </button>
            </div>
          </>
        )}

        {tab === "name" && (
          <>
            <p className="text-xs text-[#666] mb-2">
              One company name per line. Joblin will search for their careers page automatically.
            </p>
            <textarea
              value={nameInput}
              onChange={(e) => setNameInput(e.target.value)}
              rows={5}
              placeholder={"Anthropic\nMistral AI\nCohere"}
              className="w-full bg-[#0d0d0d] border border-[#2a2a2a] rounded px-3 py-2 text-sm text-[#e5e5e5] font-mono mb-3"
            />
            <div className="flex gap-2">
              <button
                onClick={() => discoverByName.mutate()}
                disabled={!nameInput.trim() || discoverByName.isPending}
                className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
              >
                {discoverByName.isPending ? "Queuing..." : "Discover & Add"}
              </button>
              <button
                onClick={onClose}
                className="text-xs border border-[#2a2a2a] rounded px-3 py-1.5 text-[#888] ml-auto"
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function Companies() {
  const [showAdd, setShowAdd] = useState(false);
  const [resolveUrls, setResolveUrls] = useState<Record<number, string>>({});
  const qc = useQueryClient();

  const { data: companies = [], isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: companiesApi.list,
  });

  const isDiscovering = companies.some((c: Company) => c.discovery_status === "discovering");

  useEffect(() => {
    if (!isDiscovering) return;
    const id = setInterval(() => {
      qc.invalidateQueries({ queryKey: ["companies"] });
    }, 4000);
    return () => clearInterval(id);
  }, [isDiscovering, qc]);

  const remove = useMutation({
    mutationFn: (id: number) => companiesApi.remove(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  const retry = useMutation({
    mutationFn: (id: number) => companiesApi.retry(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  const resolve = useMutation({
    mutationFn: ({ id, url }: { id: number; url: string }) => companiesApi.resolve(id, url),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });

  return (
    <div>
      {showAdd && <AddModal onClose={() => setShowAdd(false)} />}
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={() => setShowAdd(true)}
          className="text-xs border border-[#4e9eff] rounded px-3 py-1.5 text-[#4e9eff] bg-[#0e2040]"
        >
          Add company
        </button>
      </div>
      {isLoading && <p className="text-[#555] text-sm">Loading...</p>}
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[#1e1e1e] text-[#555] text-left">
            <th className="py-2 pr-4">Company</th>
            <th className="py-2 pr-4">ATS</th>
            <th className="py-2 pr-4">Status</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {companies.map((c: Company) => {
            if (c.discovery_status === "discovering") {
              return (
                <tr key={c.id} className="border-b border-[#111]">
                  <td className="py-2 pr-4 text-[#e5e5e5]">
                    <span className="mr-1.5 inline-block w-1.5 h-1.5 rounded-full bg-[#4e9eff] animate-pulse" />
                    {c.name}
                  </td>
                  <td className="py-2 pr-4 text-[#555] italic text-[10px]">
                    {c.discovery_message ?? "Discovering..."}
                  </td>
                  <td className="py-2 pr-4">
                    <span className="bg-[#1e1b4b] text-[#818cf8] px-1.5 rounded text-[10px]">
                      Discovering
                    </span>
                  </td>
                  <td className="py-2 text-[#333]">—</td>
                </tr>
              );
            }

            if (c.discovery_status === "failed") {
              return (
                <tr key={c.id} className="border-b border-[#111]">
                  <td className="py-2 pr-4 text-[#e5e5e5]">{c.name}</td>
                  <td className="py-2 pr-4" colSpan={2}>
                    <div className="flex items-center gap-2">
                      <span className="text-red-500 text-[10px]">Discovery failed</span>
                      <input
                        value={resolveUrls[c.id] ?? ""}
                        onChange={(e) =>
                          setResolveUrls((prev) => ({ ...prev, [c.id]: e.target.value }))
                        }
                        placeholder="Paste careers URL..."
                        className="bg-[#0d0d0d] border border-[#2a2a2a] rounded px-2 py-1 text-[11px] text-[#e5e5e5] w-52"
                      />
                      <button
                        onClick={() =>
                          resolve.mutate({ id: c.id, url: resolveUrls[c.id] ?? "" })
                        }
                        disabled={!resolveUrls[c.id]?.trim() || resolve.isPending}
                        className="text-[10px] border border-[#4e9eff] rounded px-2 py-1 text-[#4e9eff] bg-[#0e2040] disabled:opacity-40"
                      >
                        Save
                      </button>
                    </div>
                  </td>
                  <td className="py-2">
                    <button
                      onClick={() => remove.mutate(c.id)}
                      className="text-red-500 hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            }

            return (
              <tr key={c.id} className="border-b border-[#111] hover:bg-[#0f0f0f]">
                <td className="py-2 pr-4 text-[#e5e5e5]">{c.name}</td>
                <td className="py-2 pr-4">
                  <span className="bg-[#1e2a3a] text-[#4e9eff] px-1.5 rounded text-[10px]">
                    {c.ats_type}
                  </span>
                </td>
                <td className="py-2 pr-4">
                  {c.quarantined_at ? (
                    <span className="text-orange-400">Quarantined</span>
                  ) : (
                    <span className="text-emerald-500">Active</span>
                  )}
                </td>
                <td className="py-2 flex gap-2">
                  {c.quarantined_at && (
                    <button
                      onClick={() => retry.mutate(c.id)}
                      className="text-[#4e9eff] hover:underline"
                    >
                      Retry
                    </button>
                  )}
                  <button
                    onClick={() => remove.mutate(c.id)}
                    className="text-red-500 hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Check TypeScript compiles**

```bash
cd C:/dev/joblin/frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Run full backend test suite for final check**

```bash
cd C:/dev/joblin && python -m pytest tests/ -v
```

Expected: all `PASSED`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Companies.tsx
git commit -m "feat: add By Name discovery tab and discovering/failed row states to Companies page"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Default company catalog (`backend/data/default_companies.py`) — Task 1
- [x] `GET /companies/defaults` — Task 1
- [x] Parallel `probe_ats()` — Task 2
- [x] `POST /companies/bulk` — Task 3
- [x] Discovery columns migration (safe, nullable, server_default) — Task 4
- [x] `discover.py` with all 6 steps from spec — Task 5
- [x] `POST /companies/discover` (background tasks, immediate return) — Task 6
- [x] `POST /companies/{id}/resolve` — Task 6
- [x] Frontend API additions — Task 7
- [x] Onboarding Step 3 replacement with chip picker — Task 8
- [x] Companies page polling (4s, stops when done) — Task 9
- [x] Companies page discovering row (pulsing dot, discovery_message, Discovering badge) — Task 9
- [x] Companies page failed row (inline URL input + Save button) — Task 9
- [x] Companies page By Name modal tab — Task 9
- [x] No data loss on migration (nullable columns with server_default) — Task 4

**Migration safety:** Both new columns use `nullable=False, server_default="none"` (discovery_status) and `nullable=True` (discovery_message). Existing rows get `"none"` / `NULL` automatically. No backfill, no locks beyond the column addition.

**Type consistency:** `discover_company(company_id: int, name: str)` is consistent across discover.py (definition), companies.py (call site), and test mocks. `_resolve(company_id, ats_type, identifier, careers_url)` signature is consistent across definition and all call sites.
