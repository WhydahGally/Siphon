"""
tests/e2e/test_playlist_sync.py — Playlist registration and sync scenarios.

Covers:
  - POST /playlists registers and returns playlist id + name  (fast, no download)
  - POST /playlists/{id}/sync populates items                 (@slow — downloads)
  - Syncing twice produces no duplicate items                 (@slow — downloads)
  - Each item has non-empty video_id and yt_title             (@slow — downloads)

Secret required: E2E_PLAYLIST_URL
"""
import time

import pytest

from tests.e2e.conftest import require_env, poll_items_stable


# ---------------------------------------------------------------------------
# Module-scoped fixture: one playlist shared across all tests in this module.
# Deleted on teardown.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def playlist(http, base_url):
    url = require_env("E2E_PLAYLIST_URL")
    r = http.post(
        f"{base_url}/playlists",
        json={"url": url, "format": "mp3", "auto_rename": False, "watched": False, "download": False},
    )
    assert r.status_code == 201, f"POST /playlists failed: {r.text}"
    data = r.json()
    playlist_id = data["id"]
    yield data
    http.delete(f"{base_url}/playlists/{playlist_id}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_playlist_registered(playlist):
    """POST /playlists returns a valid playlist with id and name."""
    assert playlist["id"], "playlist id is empty"
    assert playlist["name"], "playlist name is empty"


@pytest.mark.e2e
@pytest.mark.slow
def test_sync_populates_items(http, base_url, playlist):
    """POST /playlists/{id}/sync downloads items and populates the item list."""
    r = http.post(f"{base_url}/playlists/{playlist['id']}/sync")
    assert r.status_code == 202, f"POST /sync failed: {r.text}"

    items = poll_items_stable(http, base_url, playlist["id"], min_count=1, timeout=300)
    assert len(items) >= 1, "Sync did not produce any items"


@pytest.mark.e2e
@pytest.mark.slow
def test_sync_no_duplicates(http, base_url, playlist):
    """A second sync on an up-to-date playlist does not create duplicate items."""
    # Ensure items exist from a previous sync (or trigger one now)
    items_before = http.get(f"{base_url}/playlists/{playlist['id']}/items").json()
    if not items_before:
        http.post(f"{base_url}/playlists/{playlist['id']}/sync")
        items_before = poll_items_stable(http, base_url, playlist["id"], min_count=1, timeout=300)

    count_before = len(items_before)

    # Second sync
    http.post(f"{base_url}/playlists/{playlist['id']}/sync")
    time.sleep(10)  # short wait — already-up-to-date syncs complete quickly

    items_after = http.get(f"{base_url}/playlists/{playlist['id']}/items").json()
    assert len(items_after) == count_before, (
        f"Item count changed after second sync: {count_before} → {len(items_after)}"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_items_have_required_fields(http, base_url, playlist):
    """Every synced item has a non-empty video_id and yt_title."""
    items = http.get(f"{base_url}/playlists/{playlist['id']}/items").json()
    if not items:
        pytest.skip("No items yet — run sync first")

    for item in items:
        assert item.get("video_id"), f"Item missing video_id: {item}"
        assert item.get("yt_title"), f"Item missing yt_title: {item}"
