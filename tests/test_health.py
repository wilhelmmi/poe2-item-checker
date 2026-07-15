import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import app


async def get(path: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get(path)


def test_health() -> None:
    response = asyncio.run(get("/api/health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_api_is_not_frontend_fallback() -> None:
    response = asyncio.run(get("/api/not-a-route"))
    assert response.status_code == 404
