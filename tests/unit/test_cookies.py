"""Tests for browser cookie support.

Covers:
- _validate_netscape_cookies (pure helper)
- registry.get_cookie_file (resolution logic)
- registry.delete_cookie_file_safe (safety invariants)
- GET /settings/cookie-file
- POST /settings/cookie-file (upload, validation, size limit)
- DELETE /settings/cookie-file
- PUT /settings/cookies-enabled round-trip
- PATCH /playlists/:id cookies_enabled field
"""
import os

import pytest


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

_INVALID_COOKIE_CONTENT = "this is not a cookie file\n"


# ---------------------------------------------------------------------------
# _validate_netscape_cookies (pure helper)
# ---------------------------------------------------------------------------

class TestValidateNetscapeCookies:
    def _v(self, content: str) -> bool:
        from siphon.api import _validate_netscape_cookies
        return _validate_netscape_cookies(content)

    def test_valid_line_returns_true(self):
        assert self._v(_VALID_COOKIE_CONTENT) is True

    def test_comment_only_returns_false(self):
        assert self._v("# Netscape HTTP Cookie File\n# another comment\n") is False

    def test_empty_content_returns_false(self):
        assert self._v("") is False

    def test_wrong_field_count_returns_false(self):
        # Only 6 tab-separated fields — missing the 7th
        assert self._v(".example.com\tTRUE\t/\tFALSE\t0\tname\n") is False

    def test_invalid_boolean_field_returns_false(self):
        # Field 2 (index 1) is not TRUE/FALSE
        assert self._v(".example.com\tYES\t/\tFALSE\t0\tname\tval\n") is False

    def test_negative_expiry_returns_false(self):
        assert self._v(".example.com\tTRUE\t/\tFALSE\t-1\tname\tval\n") is False

    def test_non_integer_expiry_returns_false(self):
        assert self._v(".example.com\tTRUE\t/\tFALSE\tabc\tname\tval\n") is False

    def test_zero_expiry_is_valid(self):
        assert self._v(".example.com\tTRUE\t/\tFALSE\t0\tname\tval\n") is True

    def test_leading_blank_lines_ignored(self):
        assert self._v("\n\n" + _VALID_COOKIE_LINE + "\n") is True


# ---------------------------------------------------------------------------
# registry.get_cookie_file — resolution logic
# ---------------------------------------------------------------------------

class TestGetCookieFile:
    def test_returns_none_when_no_file(self, db):
        from siphon import registry
        assert registry.get_cookie_file() is None

    def test_returns_path_when_file_exists_and_global_enabled(self, db):
        from siphon import registry
        cookie_path = db / "cookies.txt"
        cookie_path.write_text(_VALID_COOKIE_CONTENT)
        registry.set_setting("cookies_enabled", "true")
        result = registry.get_cookie_file()
        assert result == str(cookie_path)

    def test_returns_none_when_global_disabled(self, db):
        from siphon import registry
        (db / "cookies.txt").write_text(_VALID_COOKIE_CONTENT)
        registry.set_setting("cookies_enabled", "false")
        assert registry.get_cookie_file() is None

    def test_per_playlist_force_disabled_overrides_global(self, db):
        from siphon import registry
        (db / "cookies.txt").write_text(_VALID_COOKIE_CONTENT)
        registry.set_setting("cookies_enabled", "true")
        registry.add_playlist("pl-1", "Test", "https://example.com", "mp3", "best", str(db))
        registry.set_playlist_cookies_enabled("pl-1", False)
        row = registry.get_playlist_by_id("pl-1")
        assert registry.get_cookie_file(row) is None

    def test_per_playlist_force_enabled_overrides_global_disabled(self, db):
        from siphon import registry
        cookie_path = db / "cookies.txt"
        cookie_path.write_text(_VALID_COOKIE_CONTENT)
        registry.set_setting("cookies_enabled", "false")
        registry.add_playlist("pl-1", "Test", "https://example.com", "mp3", "best", str(db))
        registry.set_playlist_cookies_enabled("pl-1", True)
        row = registry.get_playlist_by_id("pl-1")
        assert registry.get_cookie_file(row) == str(cookie_path)

    def test_per_playlist_null_falls_through_to_global(self, db):
        from siphon import registry
        (db / "cookies.txt").write_text(_VALID_COOKIE_CONTENT)
        registry.set_setting("cookies_enabled", "false")
        registry.add_playlist("pl-1", "Test", "https://example.com", "mp3", "best", str(db))
        registry.set_playlist_cookies_enabled("pl-1", None)
        row = registry.get_playlist_by_id("pl-1")
        assert registry.get_cookie_file(row) is None


# ---------------------------------------------------------------------------
# registry.delete_cookie_file_safe — safety invariants
# ---------------------------------------------------------------------------

class TestDeleteCookieFileSafe:
    def test_returns_false_when_file_absent(self, db):
        from siphon import registry
        assert registry.delete_cookie_file_safe(str(db)) is False

    def test_deletes_file_and_returns_true(self, db):
        from siphon import registry
        cookie_path = db / "cookies.txt"
        cookie_path.write_text(_VALID_COOKIE_CONTENT)
        result = registry.delete_cookie_file_safe(str(db))
        assert result is True
        assert not cookie_path.exists()

    def test_idempotent_second_call_returns_false(self, db):
        from siphon import registry
        (db / "cookies.txt").write_text(_VALID_COOKIE_CONTENT)
        registry.delete_cookie_file_safe(str(db))
        assert registry.delete_cookie_file_safe(str(db)) is False


# ---------------------------------------------------------------------------
# GET /settings/cookie-file
# ---------------------------------------------------------------------------

class TestGetCookieFileEndpoint:
    def test_returns_set_false_when_no_file(self, api_client):
        resp = api_client.get("/settings/cookie-file")
        assert resp.status_code == 200
        assert resp.json() == {"set": False}

    def test_returns_set_true_after_upload(self, api_client):
        api_client.post(
            "/settings/cookie-file",
            content=_VALID_COOKIE_CONTENT.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        resp = api_client.get("/settings/cookie-file")
        assert resp.status_code == 200
        assert resp.json() == {"set": True}


# ---------------------------------------------------------------------------
# POST /settings/cookie-file
# ---------------------------------------------------------------------------

class TestUploadCookieFile:
    def test_valid_file_returns_204(self, api_client):
        resp = api_client.post(
            "/settings/cookie-file",
            content=_VALID_COOKIE_CONTENT.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        assert resp.status_code == 204

    def test_invalid_content_returns_400(self, api_client):
        resp = api_client.post(
            "/settings/cookie-file",
            content=_INVALID_COOKIE_CONTENT.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        assert resp.status_code == 400
        assert "Netscape" in resp.json()["detail"]

    def test_exceeds_size_limit_returns_413(self, api_client):
        oversized = (_VALID_COOKIE_LINE + "\n") * 150_000  # well over 1 MB
        resp = api_client.post(
            "/settings/cookie-file",
            content=oversized.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        assert resp.status_code == 413

    def test_upload_replaces_existing_file(self, api_client):
        first = _VALID_COOKIE_CONTENT
        second = ".other.com\tTRUE\t/\tTRUE\t0\tnew_cookie\tnew_val\n"
        api_client.post(
            "/settings/cookie-file",
            content=first.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        api_client.post(
            "/settings/cookie-file",
            content=second.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        # File should still be reported as set
        resp = api_client.get("/settings/cookie-file")
        assert resp.json() == {"set": True}


# ---------------------------------------------------------------------------
# DELETE /settings/cookie-file
# ---------------------------------------------------------------------------

class TestDeleteCookieFileEndpoint:
    def test_delete_after_upload_returns_204(self, api_client):
        api_client.post(
            "/settings/cookie-file",
            content=_VALID_COOKIE_CONTENT.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        resp = api_client.delete("/settings/cookie-file")
        assert resp.status_code == 204

    def test_delete_absent_file_returns_404(self, api_client):
        resp = api_client.delete("/settings/cookie-file")
        assert resp.status_code == 404

    def test_get_returns_set_false_after_delete(self, api_client):
        api_client.post(
            "/settings/cookie-file",
            content=_VALID_COOKIE_CONTENT.encode(),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )
        api_client.delete("/settings/cookie-file")
        resp = api_client.get("/settings/cookie-file")
        assert resp.json() == {"set": False}


# ---------------------------------------------------------------------------
# PUT /settings/cookies-enabled round-trip
# ---------------------------------------------------------------------------

class TestCookiesEnabledSetting:
    def test_set_true_and_read_back(self, api_client):
        api_client.put("/settings/cookies-enabled", json={"value": "true"})
        resp = api_client.get("/settings/cookies-enabled")
        assert resp.status_code == 200
        assert resp.json()["value"] == "true"

    def test_set_false_and_read_back(self, api_client):
        api_client.put("/settings/cookies-enabled", json={"value": "false"})
        resp = api_client.get("/settings/cookies-enabled")
        assert resp.json()["value"] == "false"

    def test_invalid_value_returns_400(self, api_client):
        resp = api_client.put("/settings/cookies-enabled", json={"value": "maybe"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# PATCH /playlists/:id — cookies_enabled field
# ---------------------------------------------------------------------------

class TestPlaylistCookiesEnabled:
    def _create_playlist(self, api_client):
        from unittest.mock import patch
        fake_info = {"id": "PLcookie", "title": "Cookie Test Playlist"}
        with (
            patch("siphon.api._fetch_playlist_info", return_value=fake_info),
            patch("siphon.api._normalise_url", side_effect=lambda u: u),
        ):
            api_client.post(
                "/playlists",
                json={"url": "https://www.youtube.com/playlist?list=PLcookie"},
            )

    def test_patch_cookies_enabled_true(self, api_client):
        self._create_playlist(api_client)
        resp = api_client.patch("/playlists/PLcookie", json={"cookies_enabled": True})
        assert resp.status_code == 200
        assert resp.json()["cookies_enabled"] in (True, 1)

    def test_patch_cookies_enabled_false(self, api_client):
        self._create_playlist(api_client)
        resp = api_client.patch("/playlists/PLcookie", json={"cookies_enabled": False})
        assert resp.status_code == 200
        assert resp.json()["cookies_enabled"] in (False, 0)

    def test_patch_cookies_enabled_null_resets_to_global(self, api_client):
        self._create_playlist(api_client)
        api_client.patch("/playlists/PLcookie", json={"cookies_enabled": True})
        resp = api_client.patch("/playlists/PLcookie", json={"cookies_enabled": None})
        assert resp.status_code == 200
        assert resp.json()["cookies_enabled"] is None
