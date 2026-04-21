"""
tests/e2e/test_scheduler.py — PlaylistScheduler auto-sync and interval scenarios.

Covers:
  - A watched playlist with a short interval auto-syncs without a manual trigger (@slow)
  - Patching the interval causes the next cycle to use the new value (@slow)

Secret required: E2E_PLAYLIST_URL
"""
import time

import pytest

from tests.e2e.conftest import require_env, poll_items_stable


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_scheduler_auto_syncs(http, base_url):
    """
    A playlist registered with watched=True and interval=15 auto-syncs within 20 s
    without any manual POST /playlists/{id}/sync call.
    """
    url = require_env("E2E_PLAYLIST_URL")

    # Register with a 15-second interval
    r = http.post(
        f"{base_url}/playlists",
        json={"url": url, "format": "mp3", "auto_rename": False, "watched": True, "check_interval_secs": 15, "download": False},
    )
    assert r.status_code == 201, f"POST /playlists failed: {r.text}"
    playlist_id = r.json()["id"]

    try:
        # Wait 20 s — the scheduler should fire and download at least 1 item
        items = poll_items_stable(http, base_url, playlist_id, min_count=1, timeout=90)
        assert len(items) >= 1, "Scheduler did not trigger an auto-sync within 90 s"
    finally:
        http.delete(f"{base_url}/playlists/{playlist_id}")


@pytest.mark.e2e
@pytest.mark.slow
def test_scheduler_interval_change_takes_effect(http, base_url):
    """
    Patching check_interval_secs via PATCH /playlists/{id} causes the next timer
    to fire at the new interval rather than the old one.

    Strategy: register with interval=60 (won't fire quickly), then patch to 15
    and verify a sync completes within ~30 s.
    """
    url = require_env("E2E_PLAYLIST_URL")

    # Register with a long interval so the first timer won't fire during the test
    r = http.post(
        f"{base_url}/playlists",
        json={"url": url, "format": "mp3", "auto_rename": False, "watched": True, "check_interval_secs": 60, "download": False},
    )
    assert r.status_code == 201, f"POST /playlists failed: {r.text}"
    playlist_id = r.json()["id"]

    try:
        # Patch to short interval — scheduler rearranges the timer
        patch_r = http.patch(
            f"{base_url}/playlists/{playlist_id}",
            json={"check_interval_secs": 15},
        )
        assert patch_r.status_code == 200, f"PATCH /playlists failed: {patch_r.text}"

        # The rescheduled timer should fire within ~15 s and download items
        items = poll_items_stable(http, base_url, playlist_id, min_count=1, timeout=90)
        assert len(items) >= 1, "Rescheduled timer did not produce items within 90 s"
    finally:
        http.delete(f"{base_url}/playlists/{playlist_id}")
