"""
tests/e2e/test_musicbrainz.py — MusicBrainz integration: ID3 tag embedding.

Covers:
  - Downloaded known track has TXXX:original_title embedded in ID3 tags

The TXXX:original_title tag is embedded by embed_original_title() in renamer.py
for every renamed file regardless of tier. The test reads the tag with mutagen
directly from disk to confirm end-to-end embedding works.

Secrets required:
  - E2E_SINGLE_VIDEO_URL  (must be a well-known song reliably found in MusicBrainz)
  - E2E_MB_USER_AGENT
"""
import os

import pytest

from tests.e2e.conftest import require_env, poll_job_terminal, _DOWNLOADS_DIR

try:
    from mutagen.id3 import ID3, ID3NoHeaderError
    _MUTAGEN_AVAILABLE = True
except ImportError:
    _MUTAGEN_AVAILABLE = False


# ---------------------------------------------------------------------------
# Module-scoped fixture: download the known track (reuses result if already done).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def known_track_job(http, base_url):
    url = require_env("E2E_SINGLE_VIDEO_URL")
    mb_ua = require_env("E2E_MB_USER_AGENT")

    http.put(f"{base_url}/settings/mb-user-agent", json={"value": mb_ua})

    r = http.post(
        f"{base_url}/jobs",
        json={"url": url, "format": "mp3", "auto_rename": True, "watched": False},
    )
    if r.status_code == 422:
        pytest.skip("Known track already registered — cannot re-download for tag test")
    assert r.status_code == 202, f"POST /jobs failed: {r.text}"
    job_id = r.json()["job_id"]

    return poll_job_terminal(http, base_url, job_id, timeout=300)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_original_title_tag_embedded(known_track_job):
    """
    The downloaded file has a TXXX:original_title ID3 tag containing the
    original YouTube video title.
    """
    if not _MUTAGEN_AVAILABLE:
        pytest.skip("mutagen not installed")

    done_items = [i for i in known_track_job["items"] if i["state"] == "done"]
    assert done_items, "No items downloaded"

    item = done_items[0]
    stem = item.get("renamed_to") or item["yt_title"]
    original_title = item["yt_title"]

    # Find the file on disk
    audio_file = None
    for root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        for fname in files:
            if fname.endswith(".mp3") and stem[:15] in fname:
                audio_file = os.path.join(root, fname)
                break
        if audio_file:
            break

    assert audio_file, f"Could not find .mp3 file for stem '{stem[:15]}...' in {_DOWNLOADS_DIR}"

    try:
        tags = ID3(audio_file)
    except ID3NoHeaderError:
        pytest.fail(f"File has no ID3 header: {audio_file}")

    txxx_frames = tags.getall("TXXX:original_title")
    assert txxx_frames, f"No TXXX:original_title frame found in {audio_file}"
    embedded = txxx_frames[0].text[0]
    assert embedded, "TXXX:original_title frame is empty"
    assert embedded == original_title, (
        f"Embedded title '{embedded}' does not match original title '{original_title}'"
    )
