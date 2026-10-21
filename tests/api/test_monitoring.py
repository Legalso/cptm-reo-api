from httpx import AsyncClient


async def test_status_ok_without_auth(client: AsyncClient) -> None:
    resp = await client.get("/monitoramento/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["environment"] == "test"


async def test_unknown_route_uses_standard_error(client: AsyncClient) -> None:
    resp = await client.get("/nao-existe")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Not Found", "code": "not_found"}
