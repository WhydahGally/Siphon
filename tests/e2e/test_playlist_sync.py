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

from tests.e2e.conftest import require_env, poll_items_stable, poll_job_terminal


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
    if r.status_code == 409:
        # Already registered by a preceding test — find and reuse it
        all_playlists = http.get(f"{base_url}/playlists").json()
        data = next((p for p in all_playlists if p["url"] == url), None)
        assert data is not None, "Playlist already registered but not found in GET /playlists"
    else:
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
def test_duplicate_url_rejected(http, base_url, playlist):
    """POST /playlists with an already-registered URL returns 409."""
    url = require_env("E2E_PLAYLIST_URL")
    r = http.post(
        f"{base_url}/playlists",
        json={"url": url, "format": "mp3", "auto_rename": False, "watched": False, "download": False},
    )
    assert r.status_code == 409, f"Expected 409 for duplicate URL, got {r.status_code}: {r.text}"


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
    # Trigger a second sync (items may or may not exist from prior tests)
    http.post(f"{base_url}/playlists/{playlist['id']}/sync")
    time.sleep(10)  # short wait — already-up-to-date syncs complete quickly

    items_after = http.get(f"{base_url}/playlists/{playlist['id']}/items").json()

    # No video_id should appear more than once
    video_ids = [item["video_id"] for item in items_after]
    duplicates = [vid for vid in set(video_ids) if video_ids.count(vid) > 1]
    assert not duplicates, f"Duplicate video_ids found after second sync: {duplicates}"


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


@pytest.mark.e2e
@pytest.mark.slow
def test_parallel_downloads_complete(http, base_url):
    """
    With max-concurrent-downloads set to a value > 1, a multi-item playlist
    downloads all items without corruption or state errors.
    """
    url = require_env("E2E_PLAYLIST_URL")

    # Save and set max-concurrent-downloads to 3
    original = http.get(f"{base_url}/settings/max-concurrent-downloads").json()["value"]
    http.put(f"{base_url}/settings/max-concurrent-downloads", json={"value": "3"})

    # Delete any existing registration so we get a fresh download
    all_playlists = http.get(f"{base_url}/playlists").json()
    existing = next((p for p in all_playlists if p["url"] == url), None)
    if existing:
        http.delete(f"{base_url}/playlists/{existing['id']}")

    try:
        r = http.post(
            f"{base_url}/jobs",
            json={"url": url, "format": "mp3", "auto_rename": False, "watched": False},
        )
        assert r.status_code == 202, f"POST /jobs failed: {r.text}"
        job_id = r.json()["job_id"]

        job = poll_job_terminal(http, base_url, job_id, timeout=300)
        done_items = [i for i in job["items"] if i["state"] == "done"]
        failed_items = [i for i in job["items"] if i["state"] == "failed"]

        assert len(done_items) >= 1, "No items completed with parallel downloads"
        assert len(failed_items) == 0, (
            f"Items failed under parallel downloads: {[(i['yt_title'], i.get('error')) for i in failed_items]}"
        )
    finally:
        http.put(f"{base_url}/settings/max-concurrent-downloads", json={"value": original})


@pytest.mark.e2e
def test_delete_playlist(http, base_url, playlist):
    """DELETE /playlists/{id} removes the playlist; GET returns 404 afterward.

    Runs last in this module — the playlist fixture teardown tolerates this.
    """
    playlist_id = playlist["id"]

    r = http.delete(f"{base_url}/playlists/{playlist_id}")
    assert r.status_code == 204, f"DELETE /playlists/{playlist_id} failed: {r.status_code}"

    r = http.get(f"{base_url}/playlists/{playlist_id}")
    assert r.status_code == 404, f"Expected 404 after delete, got {r.status_code}"
