"""
tests/e2e/test_playlist_sync.py — Playlist registration, sync, download, and deletion.

Covers:
  - POST /playlists registers and returns playlist id + name  (fast, no download)
  - POST /playlists with duplicate URL returns 409             (fast)
  - POST /playlists/{id}/sync populates items                 (@slow — metadata)
  - Syncing twice produces no duplicate items                 (@slow — metadata)
  - Each item has non-empty video_id and yt_title             (@slow — metadata)
  - Parallel downloads (concurrency > 1) complete with no failures (@slow)
  - auto_rename=False leaves rename_tier unset                (@slow)
  - DELETE /playlists/{id} returns 204 and GET returns 404    (fast)

Secret required: E2E_PLAYLIST_URL
"""
import time

import pytest

from tests.e2e.conftest import require_env, poll_items_stable, poll_job_terminal


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def playlist(http, base_url):
    """Register playlist without downloading — for sync tests."""
    url = require_env("E2E_PLAYLIST_URL")
    r = http.post(
        f"{base_url}/playlists",
        json={"url": url, "format": "mp3", "auto_rename": False, "watched": False, "download": False},
    )
    if r.status_code == 409:
        all_playlists = http.get(f"{base_url}/playlists").json()
        data = next((p for p in all_playlists if p["url"] == url), None)
        assert data is not None, "Playlist registered but not found in GET /playlists"
    else:
        assert r.status_code == 201, f"POST /playlists failed: {r.text}"
        data = r.json()
    yield data
    # Best-effort cleanup — may already be deleted by raw_job or test_delete
    http.delete(f"{base_url}/playlists/{data['id']}")


@pytest.fixture(scope="module")
def raw_job(http, base_url):
    """Download the playlist with auto_rename=False and concurrency=3.

    Deletes any existing registration first so filter_entries sees all items.
    Shared by parallel-download and auto-rename-off assertions.
    """
    url = require_env("E2E_PLAYLIST_URL")

    # Save and bump concurrency
    original_conc = http.get(f"{base_url}/settings/max-concurrent-downloads").json()["value"]
    http.put(f"{base_url}/settings/max-concurrent-downloads", json={"value": "3"})

    # Remove existing registration so POST /jobs doesn't 422
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
    finally:
        http.put(f"{base_url}/settings/max-concurrent-downloads", json={"value": original_conc})

    return job


# ---------------------------------------------------------------------------
# Sync tests (use `playlist` fixture — no audio download)
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
    http.post(f"{base_url}/playlists/{playlist['id']}/sync")
    time.sleep(10)

    items_after = http.get(f"{base_url}/playlists/{playlist['id']}/items").json()
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


# ---------------------------------------------------------------------------
# Download tests (use `raw_job` fixture — one shared playlist download)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_parallel_downloads_complete(raw_job):
    """All items complete with no failures under concurrency=3."""
    done = [i for i in raw_job["items"] if i["state"] == "done"]
    failed = [i for i in raw_job["items"] if i["state"] == "failed"]

    assert len(done) >= 1, "No items completed with parallel downloads"
    assert len(failed) == 0, (
        f"Items failed under parallel downloads: {[(i['yt_title'], i.get('error')) for i in failed]}"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_auto_rename_false_leaves_raw_title(raw_job):
    """With auto_rename=False, no item has a rename_tier set."""
    done = [i for i in raw_job["items"] if i["state"] == "done"]
    assert done, "No items downloaded"

    for item in done:
        assert item.get("rename_tier") is None, (
            f"Expected no rename_tier for auto_rename=False, got: {item.get('rename_tier')}"
        )


# ---------------------------------------------------------------------------
# Cleanup test (last — uses raw_job's playlist)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_delete_playlist(http, base_url, raw_job):
    """DELETE /playlists/{id} removes the playlist; GET returns 404 afterward."""
    playlist_id = raw_job.get("playlist_id")
    if not playlist_id:
        pytest.skip("raw_job has no playlist_id")

    r = http.delete(f"{base_url}/playlists/{playlist_id}")
    assert r.status_code == 204, f"DELETE /playlists/{playlist_id} failed: {r.status_code}"

    r = http.get(f"{base_url}/playlists/{playlist_id}")
    assert r.status_code == 404, f"Expected 404 after delete, got {r.status_code}"
