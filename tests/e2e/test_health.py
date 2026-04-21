"""
tests/e2e/test_health.py — Daemon health and version endpoint checks.

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
