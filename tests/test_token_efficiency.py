"""Tests for token-saving response handling."""

from unittest.mock import patch

import pytest

from netbox_mcp_server.server import (
    DEFAULT_CHANGELOG_FIELDS,
    compact,
    netbox_get_changelogs,
    netbox_get_objects,
    netbox_search_objects,
    select_fields,
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


def test_changelogs_reject_time_lookups_netbox_ignores():
    """time__gte is silently ignored by NetBox, returning all history; reject it."""
    with pytest.raises(ValueError, match="time_after"):
        netbox_get_changelogs({"time__gte": "2026-10-08T00:00:00Z"})


def test_dotted_fields_fetch_top_level_and_trim_nested_keys():
    """custom_fields.x asks NetBox for custom_fields, then keeps only x."""
    vm = {
        "id": 7,
        "name": "vm1",
        "platform": {"id": 3, "name": "Linux", "slug": "linux"},
        "custom_fields": {"vm_os_kernel": "5.14", "owner": "ops", "notes": "long text"},
    }
    page = {**EMPTY_PAGE, "count": 1, "results": [vm]}
    fields = ["id", "name", "platform.name", "custom_fields.vm_os_kernel", "missing.key"]
    with patch("netbox_mcp_server.server.netbox") as mock_netbox:
        mock_netbox.get.return_value = page
        result = netbox_get_objects("virtualization.virtualmachine", {}, fields=fields)

    params = mock_netbox.get.call_args.kwargs["params"]
    assert params["fields"] == "id,name,platform,custom_fields,missing"
    assert result["results"] == [
        {
            "id": 7,
            "name": "vm1",
            "platform": {"name": "Linux"},
            "custom_fields": {"vm_os_kernel": "5.14"},
        }
    ]
    assert result["count"] == 1


def test_select_fields_full_field_wins_over_dotted_path():
    obj = {"custom_fields": {"a": 1, "b": 2}}
    assert select_fields(obj, ["custom_fields.a", "custom_fields"]) == obj
    assert select_fields(obj, ["custom_fields", "custom_fields.a"]) == obj
    assert select_fields(obj, ["custom_fields.a", "custom_fields.b"]) == obj
