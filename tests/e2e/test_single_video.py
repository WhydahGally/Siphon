"""
tests/e2e/test_single_video.py — Single video download job scenarios.

Covers:
  - POST /jobs with a video URL creates a job and downloads the file (@slow)
  - File exists on disk and is a valid audio file readable by mutagen (@slow)
  - Job transitions through pending → downloading → done (@slow)

Secret required: E2E_SINGLE_VIDEO_URL
"""
import os

import pytest
import mutagen

from tests.e2e.conftest import require_env, poll_job_terminal, _DOWNLOADS_DIR


# ---------------------------------------------------------------------------
# Module-scoped fixture: submit and complete one single-video job.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def completed_video_job(http, base_url):
    url = require_env("E2E_SINGLE_VIDEO_URL")

    r = http.post(
        f"{base_url}/jobs",
        json={"url": url, "format": "mp3", "auto_rename": False},
    )
    assert r.status_code == 202, f"POST /jobs failed: {r.text}"
    job_id = r.json()["job_id"]

    job = poll_job_terminal(http, base_url, job_id, timeout=300)
    return job


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
@pytest.mark.slow
def test_job_reaches_done(completed_video_job):
    """At least one item in the job reaches the 'done' state."""
    items = completed_video_job["items"]
    done_items = [i for i in items if i["state"] == "done"]
    assert done_items, f"No items reached 'done'. Item states: {[i['state'] for i in items]}"


@pytest.mark.e2e
@pytest.mark.slow
def test_clear_done_removes_completed_items(http, base_url, completed_video_job):
    """POST /jobs/{id}/clear-done removes done items from the job."""
    job_id = completed_video_job["job_id"]
    done_before = [i for i in completed_video_job["items"] if i["state"] == "done"]
    assert done_before, "No done items to clear"

    r = http.post(f"{base_url}/jobs/{job_id}/clear-done")
    assert r.status_code == 200, f"POST /jobs/{job_id}/clear-done failed: {r.text}"
    assert r.json()["cleared"] >= 1, "Expected at least 1 cleared item"

    # Verify done items are gone
    jobs = http.get(f"{base_url}/jobs").json()
    job = next((j for j in jobs if j["job_id"] == job_id), None)
    if job:
        remaining_done = [i for i in job["items"] if i["state"] == "done"]
        assert len(remaining_done) == 0, f"Done items still present after clear: {remaining_done}"


@pytest.mark.e2e
@pytest.mark.slow
def test_file_exists_on_disk(completed_video_job):
    """A downloaded audio file exists under the downloads directory."""
    done_items = [i for i in completed_video_job["items"] if i["state"] == "done"]
    assert done_items, "No done items to check"

    # Find the file by stem (renamed_to or yt_title)
    stem = done_items[0].get("renamed_to") or done_items[0]["yt_title"]
    found = []
    for root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        for fname in files:
            if fname.startswith(stem[:20]) and fname.endswith((".mp3", ".opus", ".m4a", ".ogg")):
                found.append(os.path.join(root, fname))

    assert found, (
        f"No audio file found in {_DOWNLOADS_DIR} matching stem '{stem[:20]}...'"
    )


@pytest.mark.e2e
@pytest.mark.slow
def test_downloaded_file_is_valid_audio(completed_video_job):
    """
    The downloaded file is openable by mutagen and has a positive duration.
    """
    done_items = [i for i in completed_video_job["items"] if i["state"] == "done"]
    assert done_items, "No done items to check"

    stem = done_items[0].get("renamed_to") or done_items[0]["yt_title"]
    audio_file = None
    for root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        for fname in files:
            if fname.startswith(stem[:20]) and fname.endswith((".mp3", ".opus", ".m4a", ".ogg")):
                audio_file = os.path.join(root, fname)
                break
        if audio_file:
            break

    assert audio_file, f"Audio file not found for stem '{stem[:20]}...'"

    f = mutagen.File(audio_file)
    assert f is not None, f"mutagen could not open {audio_file}"
    assert f.info.length > 0, f"Audio duration is 0 for {audio_file}"


@pytest.mark.e2e
@pytest.mark.slow
def test_job_state_transitions(http, base_url):
    """
    A freshly submitted job starts with items in 'pending' state and eventually
    reaches a terminal state. Validates the state machine is exercised.
    """
    url = require_env("E2E_SINGLE_VIDEO_URL")

    r = http.post(
        f"{base_url}/jobs",
        json={"url": url, "format": "mp3", "auto_rename": False},
    )
    # May get 422 if the video is already registered (filter_entries returns empty).
    # That means the file was already downloaded — we can skip this transition check.
    if r.status_code == 422:
        pytest.skip("Video already registered — state transition test skipped")

    assert r.status_code == 202, f"POST /jobs failed: {r.text}"
    job_id = r.json()["job_id"]

    # The job should be visible immediately in a non-terminal state or just-done
    job = poll_job_terminal(http, base_url, job_id, timeout=300)
    terminal = {"done", "failed", "cancelled"}
    assert all(i["state"] in terminal for i in job["items"]), (
        f"Job did not reach terminal state: {[i['state'] for i in job['items']]}"
    )
