from pathlib import Path
from collections.abc import AsyncIterator

import httpx
import pytest

from app.main import app
from app.parser.service import parse_with_warnings

ROOT = Path(__file__).parents[1]


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as value:
        yield value


@pytest.mark.anyio
async def test_multiline_regression_fixture_is_parsed(client: httpx.AsyncClient) -> None:
    raw = (ROOT / "tests/fixtures/example_staff_multiline.txt").read_text()
    response = await client.post("/api/items/parse", json={"raw_text": raw})
    assert response.status_code == 200
    item = response.json()["item"]
    assert item["raw_text"] == raw
    assert item["item_class"] == "Staves"
    assert item["name"] == "Vorpal Ashen Staff of Siphoning"
    assert item["required_level"] == 44
    assert item["item_level"] == 66
    assert item["granted_skill"] == "Level 14 Firebolt"
    affixes = [modifier for modifier in item["modifiers"] if modifier["source"] == "explicit"]
    assert len(affixes) == 2
    assert affixes[0]["tier"] == 3
    assert affixes[0]["tags"] == ["Damage", "Elemental", "Lightning"]
    assert affixes[0]["values"] == [44]
    assert affixes[0]["roll_ranges"] == [[43, 48]]


@pytest.mark.anyio
async def test_real_single_line_input_is_preserved_and_warned(client: httpx.AsyncClient) -> None:
    raw = (ROOT / "docs/example-items.txt").read_text()
    response = await client.post("/api/items/parse", json={"raw_text": raw})
    assert response.status_code == 200
    body = response.json()
    assert body["item"]["raw_text"] == raw
    assert body["item"]["item_class"] is None
    assert body["item"]["rarity"] is None
    assert body["item"]["name"] is None
    assert body["item"]["modifiers"] == []
    assert body["item"]["unknown_lines"] == raw.splitlines()
    codes = {warning["code"] for warning in body["warnings"]}
    assert {"input_missing_line_breaks", "missing_item_identity", "no_modifiers_detected"} <= codes
    missing_breaks = next(
        warning for warning in body["warnings"] if warning["code"] == "input_missing_line_breaks"
    )
    assert missing_breaks["lines"] == []
    assert missing_breaks["raw_lines"] == []
    suggestion = body["line_break_suggestion"]
    assert suggestion is not None
    assert body["auto_format_status"] == "safe"
    repost = await client.post("/api/items/parse", json={"raw_text": suggestion["suggested_text"]})
    repost_codes = {warning["code"] for warning in repost.json()["warnings"]}
    assert "input_missing_line_breaks" not in repost_codes
    assert repost.json()["item"]["raw_text"] == suggestion["suggested_text"]
    assert repost.json()["auto_format_status"] == "unchanged"


@pytest.mark.anyio
async def test_collapsed_rare_is_always_ambiguous(client: httpx.AsyncClient) -> None:
    raw = "Item Class: Rings Rarity: Rare Doom Circle Ruby Ring -------- Item Level: 66"
    body = (await client.post("/api/items/parse", json={"raw_text": raw})).json()
    assert body["auto_format_status"] == "ambiguous"


@pytest.mark.anyio
async def test_blank_input_is_rejected_without_trimming_valid_input(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.post("/api/items/parse", json={"raw_text": ""})).status_code == 422
    assert (await client.post("/api/items/parse", json={"raw_text": "  \n "})).status_code == 422
    raw = "  Item Class: Rings\nRarity: Normal\nIron Ring  "
    response = await client.post("/api/items/parse", json={"raw_text": raw})
    assert response.json()["item"]["raw_text"] == raw


@pytest.mark.anyio
async def test_parse_service_and_endpoint_are_idempotent(client: httpx.AsyncClient) -> None:
    raw = (ROOT / "tests/fixtures/example_staff_multiline.txt").read_text()
    assert parse_with_warnings(raw) == parse_with_warnings(raw)
    first = (await client.post("/api/items/parse", json={"raw_text": raw})).json()
    second = (await client.post("/api/items/parse", json={"raw_text": raw})).json()
    assert first == second


@pytest.mark.anyio
async def test_malformed_input_returns_warnings_and_unknown_api_stays_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/items/parse", json={"raw_text": "mystery"})
    assert response.status_code == 200
    codes = {warning["code"] for warning in response.json()["warnings"]}
    assert "missing_item_identity" in codes
    assert (await client.get("/api/does-not-exist")).status_code == 404


@pytest.mark.anyio
async def test_unknown_warning_reports_original_line_numbers(client: httpx.AsyncClient) -> None:
    raw = "Item Class: Rings\nRarity: Rare\nDoom Circle\nRuby Ring\n--------\nMystery line"
    body = (await client.post("/api/items/parse", json={"raw_text": raw})).json()
    warning = next(
        warning for warning in body["warnings"] if warning["code"] == "unknown_lines_preserved"
    )
    assert warning["lines"] == [6]
    assert warning["raw_lines"] == ["Mystery line"]
