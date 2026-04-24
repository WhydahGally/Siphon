"""
tests/e2e/test_single_video.py — Single-video job: download, validation, ID3 tags, tiers.

Covers:
  - POST /jobs with a video URL creates a job and downloads the file
  - Downloaded file exists on disk and is a valid audio file (readable by mutagen)
  - TXXX:original_title ID3 tag is embedded in the downloaded file
  - Known track with MusicBrainz configured gets rename_tier=musicbrainz
  - POST /jobs/{id}/clear-done removes completed items from the job

Secrets required:
  - E2E_SINGLE_VIDEO_URL
  - E2E_MB_USER_AGENT  (optional — musicbrainz tier test skips without it)
"""
import os

import pytest
import mutagen

from tests.e2e.conftest import require_env, poll_job_terminal, _DOWNLOADS_DIR

try:
    from mutagen.id3 import ID3, ID3NoHeaderError
    _MUTAGEN_AVAILABLE = True
except ImportError:
    _MUTAGEN_AVAILABLE = False


# ---------------------------------------------------------------------------
# Module-scoped fixture: download a single video with auto_rename=True.
# Sets mb-user-agent when available so MusicBrainz lookup is exercised.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def single_video_job(http, base_url):
    url = require_env("E2E_SINGLE_VIDEO_URL")
    mb_ua = os.getenv("E2E_MB_USER_AGENT")

    if mb_ua:
        http.put(f"{base_url}/settings/mb-user-agent", json={"value": mb_ua})

    r = http.post(
        f"{base_url}/jobs",
        json={"url": url, "format": "mp3", "auto_rename": True, "watched": False},
    )
    assert r.status_code == 202, f"POST /jobs failed: {r.text}"
    job_id = r.json()["job_id"]

    return poll_job_terminal(http, base_url, job_id, timeout=300)


def _find_audio_file(stem: str) -> str | None:
    """Find an audio file on disk whose name starts with the given stem prefix."""
    for root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        for fname in files:
            if fname.startswith(stem[:20]) and fname.endswith((".mp3", ".opus", ".m4a", ".ogg")):
                return os.path.join(root, fname)
    return None


# ---------------------------------------------------------------------------
# Tests — non-destructive first, clear_done last
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_job_reaches_done(single_video_job):
    """At least one item in the job reaches the 'done' state."""
    done = [i for i in single_video_job["items"] if i["state"] == "done"]
    assert done, f"No items reached 'done'. States: {[i['state'] for i in single_video_job['items']]}"


@pytest.mark.e2e
@pytest.mark.slow
def test_file_exists_on_disk(single_video_job):
    """A downloaded audio file exists under the downloads directory."""
    done = [i for i in single_video_job["items"] if i["state"] == "done"]
    assert done, "No done items"
    stem = done[0].get("renamed_to") or done[0]["yt_title"]
    assert _find_audio_file(stem), (
        f"No audio file matching '{stem[:20]}...' in {_DOWNLOADS_DIR}"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_downloaded_file_is_valid_audio(single_video_job):
    """The downloaded file is openable by mutagen and has a positive duration."""
    done = [i for i in single_video_job["items"] if i["state"] == "done"]
    assert done, "No done items"
    stem = done[0].get("renamed_to") or done[0]["yt_title"]
    path = _find_audio_file(stem)
    assert path, f"Audio file not found for '{stem[:20]}...'"

    f = mutagen.File(path)
    assert f is not None, f"mutagen could not open {path}"
    assert f.info.length > 0, f"Audio duration is 0 for {path}"


@pytest.mark.e2e
@pytest.mark.slow
def test_original_title_tag_embedded(single_video_job):
    """The downloaded file has a TXXX:original_title ID3 tag with the original YouTube title."""
    if not _MUTAGEN_AVAILABLE:
        pytest.skip("mutagen not installed")

    done = [i for i in single_video_job["items"] if i["state"] == "done"]
    assert done, "No done items"

    item = done[0]
    stem = item.get("renamed_to") or item["yt_title"]
    path = _find_audio_file(stem)
    assert path, f"Audio file not found for '{stem[:20]}...'"

    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        pytest.fail(f"No ID3 header: {path}")

    txxx = tags.getall("TXXX:original_title")
    assert txxx, f"No TXXX:original_title in {path}"
    assert txxx[0].text[0] == item["yt_title"], (
        f"Embedded '{txxx[0].text[0]}' != original '{item['yt_title']}'"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_musicbrainz_tier(single_video_job):
    """Known track downloaded with mb-user-agent configured gets rename_tier=musicbrainz."""
    require_env("E2E_MB_USER_AGENT")

    done = [i for i in single_video_job["items"] if i["state"] == "done"]
    assert done, "No done items"

    tiers = [i.get("rename_tier") for i in done]
    assert "musicbrainz" in tiers, (
        f"Expected at least one item with rename_tier=musicbrainz. Got: {tiers}"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_clear_done_removes_completed_items(http, base_url, single_video_job):
    """POST /jobs/{id}/clear-done removes done items from the job.

    Runs last in this module — this is destructive to the shared fixture.
    """
    job_id = single_video_job["job_id"]
    done_before = [i for i in single_video_job["items"] if i["state"] == "done"]
    assert done_before, "No done items to clear"

    r = http.post(f"{base_url}/jobs/{job_id}/clear-done")
    assert r.status_code == 200, f"POST /jobs/{job_id}/clear-done failed: {r.text}"
    assert r.json()["cleared"] >= 1, "Expected at least 1 cleared item"

    jobs = http.get(f"{base_url}/jobs").json()
    job = next((j for j in jobs if j["job_id"] == job_id), None)
    if job:
        remaining_done = [i for i in job["items"] if i["state"] == "done"]
        assert len(remaining_done) == 0, f"Done items still present after clear: {remaining_done}"
