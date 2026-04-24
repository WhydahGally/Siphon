"""
tests/e2e/test_health.py — Daemon health, version, and settings endpoint checks.

These tests are fast (no download, no sync) and run on every e2e suite invocation.
"""
import pytest


@pytest.mark.e2e
def test_health(http, base_url):
    r = http.get(f"{base_url}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


@pytest.mark.e2e
def test_version(http, base_url):
    r = http.get(f"{base_url}/version")
    assert r.status_code == 200
    data = r.json()
    assert data.get("siphon") and len(data["siphon"]) > 0, "siphon version missing"
    assert data.get("yt_dlp") and len(data["yt_dlp"]) > 0, "yt_dlp version missing"


@pytest.mark.e2e
def test_settings_round_trip(http, base_url):
    """GET -> PUT -> GET round-trip for a known setting preserves the value."""
    key = "log-level"

    # Read original
    r = http.get(f"{base_url}/settings/{key}")
    assert r.status_code == 200
    original = r.json()["value"]

    # Set to a different value
    new_value = "DEBUG" if original != "DEBUG" else "WARNING"
    r = http.put(f"{base_url}/settings/{key}", json={"value": new_value})
    assert r.status_code == 200
    assert r.json()["value"] == new_value

    # Read back and verify
    r = http.get(f"{base_url}/settings/{key}")
    assert r.status_code == 200
    assert r.json()["value"] == new_value, (
        f"Setting not persisted: expected '{new_value}', got '{r.json()['value']}'"
    )

    # Restore original
    http.put(f"{base_url}/settings/{key}", json={"value": original})
