async def test_list_applications_empty(client):
    response = await client.get("/api/applications")
    assert response.status_code == 200
    assert response.json() == []


# ── create ─────────────────────────────────────────────────────────────

async def test_create_external_application(client):
    resp = await client.post("/api/applications", json={
        "company_name": "Acme",
        "job_title": "Engineer",
        "status": "applied",
        "source": "external",
        "url": "https://acme.com/jobs/1",
        "applied_date": "2026-06-14",
        "notes": "Found on HN",
    })
    assert resp.status_code == 201
    d = resp.json()
    assert d["company_name"] == "Acme"
    assert d["status"] == "applied"
    assert d["source"] == "external"
    assert d["job_id"] is None
    assert d["applied_date"] == "2026-06-14"


async def test_create_joblin_application_upserts(client):
    payload = {
        "job_id": 99,
        "company_name": "Stripe",
        "job_title": "SWE",
        "status": "interested",
        "source": "joblin",
    }
    r1 = await client.post("/api/applications", json=payload)
    assert r1.status_code == 201
    assert r1.json()["status"] == "interested"

    r2 = await client.post("/api/applications", json={**payload, "status": "applied"})
    assert r2.status_code == 201
    assert r2.json()["id"] == r1.json()["id"]
    assert r2.json()["status"] == "applied"

    list_resp = await client.get("/api/applications")
    assert len(list_resp.json()) == 1


# ── list filters ────────────────────────────────────────────────────────

async def test_list_filter_by_status(client):
    await client.post("/api/applications", json={"company_name": "A", "job_title": "E", "status": "interested", "source": "external"})
    await client.post("/api/applications", json={"company_name": "B", "job_title": "E", "status": "applied", "source": "external"})
    resp = await client.get("/api/applications?status=interested")
    assert len(resp.json()) == 1
    assert resp.json()[0]["company_name"] == "A"


async def test_list_search(client):
    await client.post("/api/applications", json={"company_name": "Stripe", "job_title": "SWE", "status": "applied", "source": "external"})
    await client.post("/api/applications", json={"company_name": "Linear", "job_title": "Designer", "status": "applied", "source": "external"})
    resp = await client.get("/api/applications?search=stripe")
    assert len(resp.json()) == 1
    assert resp.json()[0]["company_name"] == "Stripe"


# ── update ──────────────────────────────────────────────────────────────

async def test_update_application(client):
    create = await client.post("/api/applications", json={"company_name": "X", "job_title": "Y", "status": "interested", "source": "external"})
    app_id = create.json()["id"]
    resp = await client.patch(f"/api/applications/{app_id}", json={"status": "applied", "notes": "Submitted"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"
    assert resp.json()["notes"] == "Submitted"


async def test_update_not_found(client):
    resp = await client.patch("/api/applications/9999", json={"status": "applied"})
    assert resp.status_code == 404


# ── delete ──────────────────────────────────────────────────────────────

async def test_delete_application(client):
    create = await client.post("/api/applications", json={"company_name": "X", "job_title": "Y", "status": "interested", "source": "external"})
    app_id = create.json()["id"]
    assert (await client.delete(f"/api/applications/{app_id}")).status_code == 204
    assert (await client.get("/api/applications")).json() == []


async def test_delete_not_found(client):
    assert (await client.delete("/api/applications/9999")).status_code == 404


# ── bulk ────────────────────────────────────────────────────────────────

async def test_bulk_status_change(client):
    r1 = await client.post("/api/applications", json={"company_name": "A", "job_title": "E", "status": "interested", "source": "external"})
    r2 = await client.post("/api/applications", json={"company_name": "B", "job_title": "E", "status": "interested", "source": "external"})
    ids = [r1.json()["id"], r2.json()["id"]]
    resp = await client.post("/api/applications/bulk", json={"ids": ids, "action": "status_change", "status": "applied"})
    assert resp.json()["updated"] == 2
    assert all(a["status"] == "applied" for a in (await client.get("/api/applications")).json())


async def test_bulk_delete(client):
    r1 = await client.post("/api/applications", json={"company_name": "A", "job_title": "E", "status": "interested", "source": "external"})
    r2 = await client.post("/api/applications", json={"company_name": "B", "job_title": "E", "status": "interested", "source": "external"})
    ids = [r1.json()["id"], r2.json()["id"]]
    resp = await client.post("/api/applications/bulk", json={"ids": ids, "action": "delete"})
    assert resp.json()["deleted"] == 2
    assert (await client.get("/api/applications")).json() == []


# ── stats ────────────────────────────────────────────────────────────────

async def test_stats_empty(client):
    resp = await client.get("/api/applications/stats")
    assert resp.status_code == 200
    d = resp.json()
    assert d["total"] == 0
    assert d["response_rate"] == 0


async def test_stats_counts(client):
    for _ in range(3):
        await client.post("/api/applications", json={"company_name": "X", "job_title": "Y", "status": "applied", "source": "joblin"})
    await client.post("/api/applications", json={"company_name": "Z", "job_title": "W", "status": "offer", "source": "external"})
    d = (await client.get("/api/applications/stats")).json()
    assert d["total"] == 4
    assert d["by_status"]["applied"] == 3
    assert d["by_status"]["offer"] == 1
    assert d["response_rate"] == 33
    assert d["by_source"]["joblin"] == 3
    assert d["by_source"]["external"] == 1
