"""Tests for SponsorBlock resolution logic in registry.py and api.py."""
import json
from unittest.mock import patch

import pytest

from siphon import registry
from siphon.api import _resolve_sb_categories_for_create, _resolve_sb_categories_for_job
from siphon.models import JobCreate, PlaylistCreate


# ---------------------------------------------------------------------------
# registry.get_sponsorblock_categories
# ---------------------------------------------------------------------------

class TestGetSponsorblockCategories:
    def test_per_playlist_json_returned(self, db):
        cats = ["music_offtopic", "intro"]
        row = {"sponsorblock_categories": json.dumps(cats)}
        result = registry.get_sponsorblock_categories(row)
        assert result == cats

    def test_per_playlist_empty_string_returns_none(self, db):
        row = {"sponsorblock_categories": ""}
        assert registry.get_sponsorblock_categories(row) is None

    def test_per_playlist_null_falls_back_to_global(self, db):
        registry.set_setting("sponsorblock_enabled", "true")
        registry.set_setting("sponsorblock_categories", json.dumps(["outro"]))
        row = {"sponsorblock_categories": None}
        result = registry.get_sponsorblock_categories(row)
        assert result == ["outro"]

    def test_global_disabled_returns_none(self, db):
        registry.set_setting("sponsorblock_enabled", "false")
        row = {"sponsorblock_categories": None}
        assert registry.get_sponsorblock_categories(row) is None

    def test_no_global_setting_returns_default(self, db):
        row = {"sponsorblock_categories": None}
        result = registry.get_sponsorblock_categories(row)
        assert result == ["music_offtopic"]

    def test_none_row_returns_default(self, db):
        result = registry.get_sponsorblock_categories(None)
        assert result == ["music_offtopic"]

    def test_global_empty_array_returns_none(self, db):
        registry.set_setting("sponsorblock_enabled", "true")
        registry.set_setting("sponsorblock_categories", "[]")
        row = {"sponsorblock_categories": None}
        assert registry.get_sponsorblock_categories(row) is None

    def test_per_playlist_overrides_disabled_global(self, db):
        """Per-playlist JSON overrides a globally-disabled setting."""
        registry.set_setting("sponsorblock_enabled", "false")
        row = {"sponsorblock_categories": json.dumps(["sponsor"])}
        result = registry.get_sponsorblock_categories(row)
        assert result == ["sponsor"]


# ---------------------------------------------------------------------------
# api._resolve_sb_categories_for_create
# ---------------------------------------------------------------------------

class TestResolveSbCategoriesForCreate:
    def test_disabled_returns_empty_string(self):
        body = PlaylistCreate(
            url="https://www.youtube.com/playlist?list=PLxyz",
            sponsorblock_enabled=False,
        )
        assert _resolve_sb_categories_for_create(body) == ""

    def test_enabled_no_categories_returns_none(self):
        body = PlaylistCreate(
            url="https://www.youtube.com/playlist?list=PLxyz",
            sponsorblock_enabled=True,
            sponsorblock_categories=None,
        )
        assert _resolve_sb_categories_for_create(body) is None

    def test_enabled_with_categories_returns_json(self):
        cats = ["music_offtopic", "sponsor"]
        body = PlaylistCreate(
            url="https://www.youtube.com/playlist?list=PLxyz",
            sponsorblock_enabled=True,
            sponsorblock_categories=cats,
        )
        result = _resolve_sb_categories_for_create(body)
        assert json.loads(result) == cats


# ---------------------------------------------------------------------------
# api._resolve_sb_categories_for_job
# ---------------------------------------------------------------------------

class TestResolveSbCategoriesForJob:
    def _make_body(self, enabled=True, cats=None):
        return JobCreate(
            url="https://www.youtube.com/watch?v=abc123",
            sponsorblock_enabled=enabled,
            sponsorblock_categories=cats,
        )

    def test_disabled_returns_none(self, db):
        body = self._make_body(enabled=False)
        assert _resolve_sb_categories_for_job(body) is None

    def test_enabled_with_body_cats_returned(self, db):
        cats = ["intro", "outro"]
        body = self._make_body(enabled=True, cats=cats)
        assert _resolve_sb_categories_for_job(body) == cats

    def test_enabled_no_body_cats_falls_back_to_global(self, db):
        registry.set_setting("sponsorblock_categories", json.dumps(["sponsor"]))
        body = self._make_body(enabled=True, cats=None)
        assert _resolve_sb_categories_for_job(body) == ["sponsor"]

    def test_enabled_global_disabled_returns_none(self, db):
        registry.set_setting("sponsorblock_enabled", "false")
        body = self._make_body(enabled=True, cats=None)
        assert _resolve_sb_categories_for_job(body) is None

    def test_enabled_no_global_returns_default(self, db):
        body = self._make_body(enabled=True, cats=None)
        assert _resolve_sb_categories_for_job(body) == ["music_offtopic"]


# ---------------------------------------------------------------------------
# API route — SponsorBlock settings and playlist PATCH (via TestClient)
# ---------------------------------------------------------------------------

class TestSponsorblockApiRoutes:
    def test_settings_sb_enabled_round_trip(self, api_client):
        r = api_client.put("/settings/sb-enabled", json={"value": "false"})
        assert r.status_code == 200
        r = api_client.get("/settings/sb-enabled")
        assert r.status_code == 200
        assert r.json()["value"] == "false"

    def test_settings_sb_cats_round_trip(self, api_client):
        cats = json.dumps(["sponsor", "outro"])
        r = api_client.put("/settings/sb-cats", json={"value": cats})
        assert r.status_code == 200
        r = api_client.get("/settings/sb-cats")
        assert r.status_code == 200
        assert json.loads(r.json()["value"]) == ["sponsor", "outro"]

    def test_settings_sb_cats_invalid_category_rejected(self, api_client):
        r = api_client.put("/settings/sb-cats", json={"value": '["fake_category"]'})
        assert r.status_code == 400

    def test_settings_sb_enabled_invalid_value_rejected(self, api_client):
        r = api_client.put("/settings/sb-enabled", json={"value": "maybe"})
        assert r.status_code == 400

    def test_playlist_sponsorblock_patch(self, api_client):
        """PATCH /playlists/{id} can toggle sponsorblock_enabled."""
        fake_info = {"id": "PLxyz", "title": "My Playlist"}
        with (
            patch("siphon.api._fetch_playlist_info", return_value=fake_info),
            patch("siphon.api._normalise_url", side_effect=lambda u: u),
        ):
            r = api_client.post(
                "/playlists",
                json={
                    "url": "https://www.youtube.com/playlist?list=PLxyz",
                    "sponsorblock_enabled": False,
                    "download": False,
                },
            )
        assert r.status_code == 201
        pl_id = r.json()["id"]

        r = api_client.patch(f"/playlists/{pl_id}", json={"sponsorblock_enabled": True})
        assert r.status_code == 200

        r = api_client.get(f"/playlists/{pl_id}")
        assert r.status_code == 200
        assert r.json()["sponsorblock_enabled"] is True
