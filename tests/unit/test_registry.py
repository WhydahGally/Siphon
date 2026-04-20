"""Tests for siphon.registry — CRUD operations via in-process SQLite."""
import pytest

from siphon import registry
from siphon.models import ItemRecord


# The `db` fixture from conftest.py initialises the registry against tmp_path
# and resets all state after each test.


# ---------------------------------------------------------------------------
# Playlist CRUD
# ---------------------------------------------------------------------------

def _add_pl(playlist_id="pl-1", name="My Playlist", url="https://youtube.com/playlist?list=PL1"):
    registry.add_playlist(
        playlist_id=playlist_id,
        name=name,
        url=url,
        fmt="mp3",
        quality="best",
        output_dir="/tmp/test",
    )


class TestPlaylistCRUD:
    def test_add_and_get(self, db):
        _add_pl()
        row = registry.get_playlist_by_id("pl-1")
        assert row is not None
        assert row["name"] == "My Playlist"

    def test_add_duplicate_raises(self, db):
        _add_pl()
        with pytest.raises(ValueError, match="already registered"):
            _add_pl()

    def test_list_playlists(self, db):
        _add_pl("pl-1", "First")
        _add_pl("pl-2", "Second")
        rows = registry.list_playlists()
        ids = [r["id"] for r in rows]
        assert "pl-1" in ids
        assert "pl-2" in ids

    def test_get_by_name(self, db):
        _add_pl()
        row = registry.get_playlist_by_name("My Playlist")
        assert row is not None
        assert row["id"] == "pl-1"

    def test_delete_playlist(self, db):
        _add_pl()
        registry.delete_playlist("pl-1")
        assert registry.get_playlist_by_id("pl-1") is None

    def test_set_watched(self, db):
        _add_pl()
        registry.set_playlist_watched("pl-1", False)
        row = registry.get_playlist_by_id("pl-1")
        assert row["watched"] == 0

    def test_get_watched_playlists(self, db):
        _add_pl("pl-1")
        _add_pl("pl-2", name="Other", url="https://youtube.com/playlist?list=PL2")
        registry.set_playlist_watched("pl-2", False)
        watched = [r["id"] for r in registry.get_watched_playlists()]
        assert "pl-1" in watched
        assert "pl-2" not in watched

    def test_set_interval(self, db):
        _add_pl()
        registry.set_playlist_interval("pl-1", 3600)
        row = registry.get_playlist_by_id("pl-1")
        assert row["check_interval_secs"] == 3600

    def test_set_auto_rename(self, db):
        _add_pl()
        registry.set_playlist_auto_rename("pl-1", True)
        row = registry.get_playlist_by_id("pl-1")
        assert row["auto_rename"] == 1


# ---------------------------------------------------------------------------
# Item persistence
# ---------------------------------------------------------------------------

def _make_record(video_id="vid-1", yt_title="Song"):
    return ItemRecord(
        video_id=video_id,
        playlist_id="pl-1",
        yt_title=yt_title,
        renamed_to=None,
        rename_tier=None,
        uploader=None,
        channel_url=None,
        duration_secs=None,
    )


class TestItemCRUD:
    def test_insert_and_get(self, db):
        _add_pl()
        record = _make_record()
        registry.insert_item(record, "pl-1")
        item = registry.get_item("vid-1", "pl-1")
        assert item is not None
        assert item["yt_title"] == "Song"

    def test_insert_idempotent(self, db):
        _add_pl()
        record = _make_record()
        registry.insert_item(record, "pl-1")
        registry.insert_item(record, "pl-1")  # second insert is silently ignored
        rows = registry.list_items_for_playlist("pl-1")
        assert len(rows) == 1

    def test_get_downloaded_ids(self, db):
        _add_pl()
        registry.insert_item(_make_record("vid-1"), "pl-1")
        registry.insert_item(_make_record("vid-2", "Song 2"), "pl-1")
        ids = registry.get_downloaded_ids("pl-1")
        assert ids == {"vid-1", "vid-2"}

    def test_count_items(self, db):
        _add_pl()
        registry.insert_item(_make_record("vid-1"), "pl-1")
        registry.insert_item(_make_record("vid-2", "Song 2"), "pl-1")
        assert registry.count_items("pl-1") == 2


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_set_and_get(self, db):
        registry.set_setting("mb_user_agent", "TestApp/1.0")
        assert registry.get_setting("mb_user_agent") == "TestApp/1.0"

    def test_get_missing_returns_none(self, db):
        assert registry.get_setting("nonexistent_key") is None

    def test_upsert_overwrites(self, db):
        registry.set_setting("key", "v1")
        registry.set_setting("key", "v2")
        assert registry.get_setting("key") == "v2"


# ---------------------------------------------------------------------------
# Failed downloads
# ---------------------------------------------------------------------------

class TestFailedDownloads:
    def test_insert_and_get(self, db):
        _add_pl()
        registry.insert_failed("vid-1", "pl-1", "Song", "https://youtu.be/vid-1", "HTTP 403")
        rows = registry.get_failed("pl-1")
        assert len(rows) == 1
        assert rows[0]["video_id"] == "vid-1"

    def test_attempt_count_increments(self, db):
        _add_pl()
        registry.insert_failed("vid-1", "pl-1", "Song", "https://youtu.be/vid-1", "err")
        registry.insert_failed("vid-1", "pl-1", "Song", "https://youtu.be/vid-1", "err")
        count = registry.get_failed_attempt_count("vid-1", "pl-1")
        assert count == 2

    def test_clear_failed(self, db):
        _add_pl()
        registry.insert_failed("vid-1", "pl-1", "Song", "https://youtu.be/vid-1", "err")
        registry.clear_failed("vid-1", "pl-1")
        assert registry.get_failed("pl-1") == []
