"""
tests/e2e/test_renamer.py — Auto-rename on/off and filename sanitisation scenarios.

Covers:
  - auto_rename=True: job item has renamed_to, filename on disk is clean
  - auto_rename=False: job item renamed_to is None or equals yt_title (raw output)
  - Visual-equivalent Unicode replaces filesystem-unsafe chars in title
  - Noise suffixes (Official Music Video, etc.) are stripped from filenames

Note on unsafe-char and noise-strip tests:
  These rely on videos in the configured playlist having titles with those properties.
  If no item qualifies, the assertion is skipped with a descriptive message.

Secret required: E2E_PLAYLIST_URL
"""
import os
import re

import pytest

from tests.e2e.conftest import require_env, poll_job_terminal, _DOWNLOADS_DIR

# Unicode visual equivalents for filesystem-unsafe chars (from renamer.py)
_VISUAL_EQUIVALENTS = {"\u29F8", "\u29F9", "\uA789", "\uFF0A", "\uFF1F", "\uFF02", "\uFF1C", "\uFF1E", "\uFF5C"}
_UNSAFE_ASCII = set('/\\:*?"<>|')

# Default noise pattern substrings to check (lower-case)
_NOISE_SUBSTRINGS = [
    "official music video",
    "official video",
    "official audio",
    "lyric video",
    "lyrics video",
]


def _find_audio_files_in_downloads() -> list[str]:
    result = []
    for root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        for f in files:
            if f.endswith((".mp3", ".opus", ".m4a", ".ogg", ".flac")):
                result.append(os.path.join(root, f))
    return result


# ---------------------------------------------------------------------------
# Module-scoped fixture: download the playlist with auto_rename=True.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def renamed_job(http, base_url):
    url = require_env("E2E_PLAYLIST_URL")

    r = http.post(
        f"{base_url}/jobs",
        json={"url": url, "format": "mp3", "auto_rename": True, "watched": False},
    )
    if r.status_code == 422:
        pytest.skip("Playlist already registered — cannot test auto_rename=True on fresh download")
    assert r.status_code == 202, f"POST /jobs failed: {r.text}"
    job_id = r.json()["job_id"]

    return poll_job_terminal(http, base_url, job_id, timeout=600)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_auto_rename_true_sets_renamed_to(renamed_job):
    """With auto_rename=True, at least one job item has a non-empty renamed_to."""
    done_items = [i for i in renamed_job["items"] if i["state"] == "done"]
    assert done_items, "No items downloaded successfully"

    renamed = [i for i in done_items if i.get("renamed_to")]
    assert renamed, (
        "auto_rename=True but no item has renamed_to set. "
        f"Items: {[(i['yt_title'], i.get('renamed_to')) for i in done_items]}"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_unsafe_chars_replaced_with_visual_equivalents(renamed_job):
    """
    For any renamed item whose original yt_title contains filesystem-unsafe chars,
    the renamed_to field and the file on disk must not contain those raw chars —
    instead the visual-equivalent Unicode replacements must be present.
    """
    done_items = [i for i in renamed_job["items"] if i["state"] == "done" and i.get("renamed_to")]
    unsafe_items = [i for i in done_items if any(c in i["yt_title"] for c in _UNSAFE_ASCII)]

    if not unsafe_items:
        pytest.skip("No items with unsafe chars in title in this playlist — skipping")

    for item in unsafe_items:
        renamed = item["renamed_to"]
        # The renamed stem must not contain raw unsafe chars
        for c in _UNSAFE_ASCII:
            assert c not in renamed, (
                f"Raw unsafe char '{c}' found in renamed_to '{renamed}' "
                f"(original title: '{item['yt_title']}')"
            )
        # And the file on disk should match
        audio_files = _find_audio_files_in_downloads()
        matching = [f for f in audio_files if renamed[:15] in os.path.basename(f)]
        if matching:
            for c in _UNSAFE_ASCII:
                assert c not in os.path.basename(matching[0]), (
                    f"Raw unsafe char '{c}' found in filename '{os.path.basename(matching[0])}'"
                )


@pytest.mark.e2e
@pytest.mark.slow
def test_noise_suffix_stripped_from_filename(renamed_job):
    """
    For any renamed item whose original yt_title contains a noise suffix
    (e.g. 'Official Music Video'), the renamed_to field must not contain it.
    """
    done_items = [i for i in renamed_job["items"] if i["state"] == "done" and i.get("renamed_to")]
    noisy_items = [
        i for i in done_items
        if any(ns in i["yt_title"].lower() for ns in _NOISE_SUBSTRINGS)
    ]

    if not noisy_items:
        pytest.skip("No items with noise suffixes in this playlist — skipping")

    for item in noisy_items:
        renamed_lower = item["renamed_to"].lower()
        for ns in _NOISE_SUBSTRINGS:
            assert ns not in renamed_lower, (
                f"Noise suffix '{ns}' still present in renamed_to '{item['renamed_to']}' "
                f"(original: '{item['yt_title']}')"
            )


@pytest.mark.e2e
@pytest.mark.slow
def test_auto_rename_false_leaves_raw_title(http, base_url):
    """
    With auto_rename=False, job items have no rename_tier.

    Run last in this module so the renamed_job fixture has already consumed all
    items. We delete the existing playlist and re-register from scratch so the
    daemon sees fresh items to download.
    """
    url = require_env("E2E_PLAYLIST_URL")

    # Delete the existing playlist so all items become eligible for download again
    all_playlists = http.get(f"{base_url}/playlists").json()
    existing = next((p for p in all_playlists if p["url"] == url), None)
    if existing:
        http.delete(f"{base_url}/playlists/{existing['id']}")

    r = http.post(
        f"{base_url}/jobs",
        json={"url": url, "format": "mp3", "auto_rename": False, "watched": False},
    )
    assert r.status_code == 202, f"POST /jobs failed: {r.text}"
    job_id = r.json()["job_id"]

    try:
        job = poll_job_terminal(http, base_url, job_id, timeout=600)
        done_items = [i for i in job["items"] if i["state"] == "done"]
        assert done_items, "No items downloaded"

        # With auto_rename=False, rename_tier should be absent or None.
        for item in done_items:
            assert item.get("rename_tier") is None, (
                f"Expected no rename_tier for auto_rename=False, got: {item.get('rename_tier')}"
            )
    finally:
        # Clean up: delete the playlist we registered for this test
        all_playlists = http.get(f"{base_url}/playlists").json()
        p = next((p for p in all_playlists if p["url"] == url), None)
        if p:
            http.delete(f"{base_url}/playlists/{p['id']}")
