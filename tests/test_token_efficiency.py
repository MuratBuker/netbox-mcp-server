"""Tests for token-saving response handling."""

from unittest.mock import patch

from netbox_mcp_server.server import (
    DEFAULT_CHANGELOG_FIELDS,
    compact,
    netbox_get_changelogs,
    netbox_get_objects,
    netbox_search_objects,
)

EMPTY_PAGE = {"count": 0, "next": None, "previous": None, "results": []}


def test_compact_drops_links_and_empty_values_recursively():
    """Links and empty values go; falsy-but-meaningful values stay."""
    obj = {
        "id": 1,
        "url": "https://nb/api/dcim/devices/1/",
        "display_url": "https://nb/dcim/devices/1/",
        "site": {"id": 2, "url": "https://nb/api/dcim/sites/2/", "name": "DC1"},
        "tenant": None,
        "comments": "",
        "tags": [],
        "custom_fields": {"owner": None},
        "position": 0,
        "is_primary": False,
    }

    assert compact(obj) == {
        "id": 1,
        "site": {"id": 2, "name": "DC1"},
        "position": 0,
        "is_primary": False,
    }


@patch("netbox_mcp_server.server.netbox")
def test_get_objects_keeps_page_envelope(mock_netbox):
    """Pagination keys survive even when empty; only objects are compacted."""
    mock_netbox.get.return_value = {
        **EMPTY_PAGE,
        "count": 1,
        "results": [{"id": 1, "url": "x", "tenant": None}],
    }

    result = netbox_get_objects("dcim.device", {})

    assert result == {"count": 1, "next": None, "previous": None, "results": [{"id": 1}]}


@patch("netbox_mcp_server.server.netbox")
def test_changelogs_default_to_limit_and_summary_fields(mock_netbox):
    """Default call is paginated and omits object snapshots."""
    mock_netbox.get.return_value = EMPTY_PAGE

    netbox_get_changelogs({"action": "update"})

    params = mock_netbox.get.call_args[1]["params"]
    assert params == {
        "action": "update",
        "limit": 5,
        "offset": 0,
        "fields": ",".join(DEFAULT_CHANGELOG_FIELDS),
    }


@patch("netbox_mcp_server.server.netbox")
def test_changelogs_empty_fields_returns_all_fields(mock_netbox):
    """fields=[] opts back into full entries including snapshots."""
    mock_netbox.get.return_value = EMPTY_PAGE

    netbox_get_changelogs({}, fields=[])

    assert "fields" not in mock_netbox.get.call_args[1]["params"]


@patch("netbox_mcp_server.server.netbox")
def test_search_without_fields_uses_brief(mock_netbox):
    """Search defaults to brief objects instead of full ones."""
    mock_netbox.get.return_value = EMPTY_PAGE

    netbox_search_objects("switch", object_types=["dcim.device"])

    params = mock_netbox.get.call_args[1]["params"]
    assert params["brief"] == "1"
    assert "fields" not in params
