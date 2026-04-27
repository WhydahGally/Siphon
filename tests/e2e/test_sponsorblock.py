"""
tests/e2e/test_sponsorblock.py — SponsorBlock settings integration.

These tests are fast (no download, no sync) and verify the SponsorBlock
configuration endpoints work end-to-end through the running daemon.

Secret required: none
"""
import json

import pytest


@pytest.mark.e2e
def test_sb_enabled_round_trip(http, base_url):
    """PUT/GET round-trip for sb-enabled preserves the value."""
    r = http.get(f"{base_url}/settings/sb-enabled")
    assert r.status_code == 200
    original = r.json()["value"]

    new_value = "false" if original != "false" else "true"
    r = http.put(f"{base_url}/settings/sb-enabled", json={"value": new_value})
    assert r.status_code == 200

    r = http.get(f"{base_url}/settings/sb-enabled")
    assert r.status_code == 200
    assert r.json()["value"] == new_value

    # Restore
    http.put(f"{base_url}/settings/sb-enabled", json={"value": original})


@pytest.mark.e2e
def test_sb_cats_round_trip(http, base_url):
    """PUT/GET round-trip for sb-cats preserves the JSON array."""
    r = http.get(f"{base_url}/settings/sb-cats")
    assert r.status_code == 200
    original = r.json()["value"]

    new_cats = json.dumps(["sponsor", "outro"])
    r = http.put(f"{base_url}/settings/sb-cats", json={"value": new_cats})
    assert r.status_code == 200

    r = http.get(f"{base_url}/settings/sb-cats")
    assert r.status_code == 200
    assert json.loads(r.json()["value"]) == ["sponsor", "outro"]

    # Restore
    if original:
        http.put(f"{base_url}/settings/sb-cats", json={"value": original})


@pytest.mark.e2e
def test_sb_cats_invalid_value_rejected(http, base_url):
    """PUT /settings/sb-cats with an unknown category returns 400."""
    r = http.put(f"{base_url}/settings/sb-cats", json={"value": '["not_a_real_category"]'})
    assert r.status_code == 400


@pytest.mark.e2e
def test_sb_enabled_invalid_value_rejected(http, base_url):
    """PUT /settings/sb-enabled with a non-boolean value returns 400."""
    r = http.put(f"{base_url}/settings/sb-enabled", json={"value": "maybe"})
    assert r.status_code == 400
