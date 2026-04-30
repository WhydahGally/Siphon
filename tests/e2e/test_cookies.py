"""
tests/e2e/test_cookies.py — Cookie file API integration tests.

Tests the full lifecycle against a running daemon:
  - GET /settings/cookie-file (no file present)
  - POST /settings/cookie-file (upload valid / invalid / oversized)
  - GET /settings/cookie-file (file present)
  - PUT /settings/cookies-enabled round-trip
  - Per-playlist cookies_enabled PATCH round-trip
  - DELETE /settings/cookie-file lifecycle

Secret required: none for cookie file tests.
Per-playlist test requires: E2E_PLAYLIST_URL
"""
import json

import pytest

from tests.e2e.conftest import require_env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_COOKIE_LINE = (
    ".example.com\tTRUE\t/\tFALSE\t1999999999\tmy_cookie\tmy_value"
)

_VALID_COOKIE_CONTENT = (
    "# Netscape HTTP Cookie File\n"
    + _VALID_COOKIE_LINE
    + "\n"
)

_INVALID_COOKIE_CONTENT = "this is not a valid cookie file\n"


def _cleanup_cookie(http, base_url):
    """Delete the cookie file if it exists — used in teardown."""
    r = http.get(f"{base_url}/settings/cookie-file")
    if r.status_code == 200 and r.json().get("set"):
        http.delete(f"{base_url}/settings/cookie-file")


# ---------------------------------------------------------------------------
# GET /settings/cookie-file — initial state
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_cookie_file_not_set_initially(http, base_url):
    """Cookie file should not exist after a factory reset."""
    _cleanup_cookie(http, base_url)
    r = http.get(f"{base_url}/settings/cookie-file")
    assert r.status_code == 200
    assert r.json() == {"set": False}


# ---------------------------------------------------------------------------
# POST /settings/cookie-file
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_upload_valid_cookie_file(http, base_url):
    """Uploading a valid Netscape cookie file returns 204."""
    r = http.post(
        f"{base_url}/settings/cookie-file",
        data=_VALID_COOKIE_CONTENT.encode(),
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    assert r.status_code == 204
    _cleanup_cookie(http, base_url)


@pytest.mark.e2e
def test_upload_invalid_cookie_file_returns_400(http, base_url):
    """Uploading non-Netscape content returns 400."""
    r = http.post(
        f"{base_url}/settings/cookie-file",
        data=_INVALID_COOKIE_CONTENT.encode(),
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    assert r.status_code == 400
    assert "Netscape" in r.json().get("detail", "")


@pytest.mark.e2e
def test_upload_oversized_file_returns_413(http, base_url):
    """A file larger than 1 MB returns 413."""
    oversized = (_VALID_COOKIE_LINE + "\n") * 150_000
    r = http.post(
        f"{base_url}/settings/cookie-file",
        data=oversized.encode(),
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# GET /settings/cookie-file — after upload
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_cookie_file_set_after_upload(http, base_url):
    """GET returns set=true after a successful upload."""
    http.post(
        f"{base_url}/settings/cookie-file",
        data=_VALID_COOKIE_CONTENT.encode(),
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    r = http.get(f"{base_url}/settings/cookie-file")
    assert r.status_code == 200
    assert r.json() == {"set": True}
    _cleanup_cookie(http, base_url)


# ---------------------------------------------------------------------------
# DELETE /settings/cookie-file
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_delete_cookie_file_lifecycle(http, base_url):
    """Upload → GET(set=true) → DELETE(204) → GET(set=false)."""
    http.post(
        f"{base_url}/settings/cookie-file",
        data=_VALID_COOKIE_CONTENT.encode(),
        headers={"Content-Type": "text/plain; charset=utf-8"},
    )
    assert http.get(f"{base_url}/settings/cookie-file").json() == {"set": True}

    r = http.delete(f"{base_url}/settings/cookie-file")
    assert r.status_code == 204

    assert http.get(f"{base_url}/settings/cookie-file").json() == {"set": False}


@pytest.mark.e2e
def test_delete_absent_cookie_file_returns_404(http, base_url):
    """DELETE with no file returns 404."""
    _cleanup_cookie(http, base_url)
    r = http.delete(f"{base_url}/settings/cookie-file")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# PUT /settings/cookies-enabled round-trip
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_cookies_enabled_round_trip(http, base_url):
    """PUT cookies-enabled true → GET → PUT false → GET → restore."""
    r = http.get(f"{base_url}/settings/cookies-enabled")
    assert r.status_code == 200
    original = r.json()["value"]

    http.put(f"{base_url}/settings/cookies-enabled", json={"value": "true"})
    assert http.get(f"{base_url}/settings/cookies-enabled").json()["value"] == "true"

    http.put(f"{base_url}/settings/cookies-enabled", json={"value": "false"})
    assert http.get(f"{base_url}/settings/cookies-enabled").json()["value"] == "false"

    # Restore
    http.put(f"{base_url}/settings/cookies-enabled", json={"value": original})


@pytest.mark.e2e
def test_cookies_enabled_invalid_value_returns_400(http, base_url):
    r = http.put(f"{base_url}/settings/cookies-enabled", json={"value": "yes"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Per-playlist cookies_enabled via PATCH /playlists/:id
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_per_playlist_cookies_enabled_patch(http, base_url):
    """PATCH cookies_enabled true/false/null persists and round-trips."""
    url = require_env("E2E_PLAYLIST_URL")

    r = http.post(
        f"{base_url}/playlists",
        json={"url": url, "format": "mp3", "auto_rename": False, "watched": False, "download": False},
    )
    if r.status_code == 409:
        all_playlists = http.get(f"{base_url}/playlists").json()
        data = next((p for p in all_playlists if p["url"] == url), None)
        assert data is not None
    else:
        assert r.status_code == 201, f"POST /playlists failed: {r.text}"
        data = r.json()

    playlist_id = data["id"]
    try:
        # Force-enable
        r = http.patch(f"{base_url}/playlists/{playlist_id}", json={"cookies_enabled": True})
        assert r.status_code == 200
        assert r.json()["cookies_enabled"] in (True, 1)

        # Force-disable
        r = http.patch(f"{base_url}/playlists/{playlist_id}", json={"cookies_enabled": False})
        assert r.status_code == 200
        assert r.json()["cookies_enabled"] in (False, 0)

        # Reset to global (null)
        r = http.patch(f"{base_url}/playlists/{playlist_id}", json={"cookies_enabled": None})
        assert r.status_code == 200
        assert r.json()["cookies_enabled"] is None
    finally:
        http.delete(f"{base_url}/playlists/{playlist_id}")
