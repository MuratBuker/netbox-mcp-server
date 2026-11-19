"""Clients like Open WebUI send array/object tool arguments as JSON strings."""

import asyncio

import pytest
from fastmcp import Client

from netbox_mcp_server import server


class FakeNetBox:
    """Record the params of the last GET."""

    def __init__(self) -> None:
        self.params: dict = {}

    def get(self, endpoint: str, params: dict | None = None, fallback_endpoint=None) -> dict:
        self.params = params or {}
        return {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.parametrize(
    ("fields", "filters"),
    [
        ('["id", "name", "custom_fields"]', {"name": "miks"}),
        ("id, name, custom_fields", '{"name": "miks"}'),
        (["id", "name", "custom_fields"], {"name": "miks"}),
    ],
)
def test_get_objects_accepts_stringified_arguments(
    monkeypatch: pytest.MonkeyPatch, fields: object, filters: object
) -> None:
    fake = FakeNetBox()
    monkeypatch.setattr(server, "netbox", fake)

    async def call() -> None:
        async with Client(server.mcp) as client:
            await client.call_tool(
                "netbox_get_objects",
                {"object_type": "tenancy.tenant", "filters": filters, "fields": fields},
            )

    asyncio.run(call())
    assert fake.params["fields"] == "id,name,custom_fields"
    assert fake.params["name"] == "miks"


def test_tool_schema_still_advertises_arrays() -> None:
    async def schema() -> dict:
        async with Client(server.mcp) as client:
            tools = {t.name: t for t in await client.list_tools()}
            return tools["netbox_get_objects"].inputSchema["properties"]

    props = asyncio.run(schema())
    assert {"type": "array", "items": {"type": "string"}} in props["fields"]["anyOf"]
    assert props["filters"]["type"] == "object"
