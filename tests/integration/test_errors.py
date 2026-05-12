def test_404_returns_structured_error(client):
    r = client.get("/api/v1/nonexistent-route")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body["error"]
