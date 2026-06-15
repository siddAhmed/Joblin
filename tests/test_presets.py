async def test_list_presets_returns_group_and_label(client):
    response = await client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    for preset in data:
        assert "group" in preset, f"preset {preset['name']} missing 'group'"
        assert preset["group"] in ("experienced", "intern"), f"preset {preset['name']} has invalid group: {preset['group']}"
        assert "label" in preset, f"preset {preset['name']} missing 'label'"
        assert isinstance(preset["label"], str) and len(preset["label"]) > 0


async def test_list_presets_has_both_groups(client):
    response = await client.get("/api/presets")
    data = response.json()
    groups = {p["group"] for p in data}
    assert "experienced" in groups
    assert "intern" in groups


async def test_list_presets_intern_count(client):
    response = await client.get("/api/presets")
    data = response.json()
    intern_presets = [p for p in data if p["group"] == "intern"]
    assert len(intern_presets) == 5


async def test_list_presets_experienced_count(client):
    response = await client.get("/api/presets")
    data = response.json()
    experienced_presets = [p for p in data if p["group"] == "experienced"]
    assert len(experienced_presets) == 4  # backend-generalist, frontend, python-ml, vlsi
