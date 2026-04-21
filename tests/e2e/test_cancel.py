"""
tests/e2e/test_cancel.py — Job cancellation scenarios.

Covers:
  - Starting a multi-item download and cancelling via POST /jobs/cancel-all
    leaves at least one item in 'cancelled' state and no items remain 'pending'.

Strategy: set max-concurrent-downloads to 1 so only 1 item downloads at a time,
ensuring pending items exist when cancel-all is called. The setting is restored
after the test.

Secret required: E2E_PLAYLIST_URL  (needs ≥ 2 items for cancel to work)
"""
import time

import pytest

from tests.e2e.conftest import require_env, poll_job_terminal


@pytest.mark.e2e
@pytest.mark.slow
def test_cancel_leaves_cancelled_items(http, base_url):
    """
    Cancelling an in-progress multi-item job via POST /jobs/cancel-all
    transitions all pending items to 'cancelled'.
    """
    url = require_env("E2E_PLAYLIST_URL")

    # Set max concurrent downloads to 1 so pending items accumulate
    http.put(f"{base_url}/settings/max-concurrent-downloads", json={"value": "1"})

    try:
        r = http.post(
            f"{base_url}/jobs",
            json={"url": url, "format": "mp3", "auto_rename": False, "watched": False},
        )
        if r.status_code == 422:
            pytest.skip("Playlist already registered and up to date — cancel test requires pending items")
        assert r.status_code == 202, f"POST /jobs failed: {r.text}"
        job_id = r.json()["job_id"]

        # Wait until at least one item enters 'downloading' state
        deadline = time.time() + 60
        triggered = False
        while time.time() < deadline:
            jobs = {j["job_id"]: j for j in http.get(f"{base_url}/jobs").json()}
            if job_id in jobs:
                states = [i["state"] for i in jobs[job_id]["items"]]
                if "downloading" in states:
                    triggered = True
                    break
            time.sleep(1)

        if not triggered:
            pytest.skip("Download did not reach 'downloading' state within 60 s — skip cancel test")

        # Cancel all jobs
        cancel_r = http.post(f"{base_url}/jobs/cancel-all")
        assert cancel_r.status_code == 200, f"POST /jobs/cancel-all failed: {cancel_r.text}"

        # Wait for terminal state
        job = poll_job_terminal(http, base_url, job_id, timeout=120)

        # Assertions
        states = [i["state"] for i in job["items"]]
        assert "pending" not in states, f"Some items still pending after cancel: {states}"
        assert "cancelled" in states, f"No items were cancelled: {states}"

    finally:
        # Restore default max concurrent downloads
        http.put(f"{base_url}/settings/max-concurrent-downloads", json={"value": "5"})
