async def test_list_applications_empty(client):
    response = await client.get("/api/applications")
    assert response.status_code == 200
    assert response.json() == []
