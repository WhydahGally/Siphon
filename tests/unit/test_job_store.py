"""Tests for siphon.job_store.JobStore — sync operations only."""
import time

import pytest

from siphon.job_store import JobStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entries(*video_ids: str) -> list:
    return [
        {"id": vid, "url": f"https://youtu.be/{vid}", "title": f"Title {vid}"}
        for vid in video_ids
    ]


# ---------------------------------------------------------------------------
# create_job
# ---------------------------------------------------------------------------

class TestCreateJob:
    def test_returns_uuid_string(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        assert isinstance(job_id, str)
        assert len(job_id) == 36  # UUID4 format

    def test_job_is_retrievable(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1", "v2"))
        job = store.get_job(job_id)
        assert job is not None
        assert job.job_id == job_id
        assert len(job.items) == 2

    def test_items_start_pending(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        job = store.get_job(job_id)
        assert all(i.state == "pending" for i in job.items)

    def test_playlist_metadata(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"), auto_rename=True)
        job = store.get_job(job_id)
        assert job.playlist_id == "pl-1"
        assert job.playlist_name == "My Playlist"
        assert job.auto_rename is True

    def test_single_video_job_no_playlist_id(self):
        store = JobStore()
        job_id = store.create_job(None, None, _entries("v1"))
        job = store.get_job(job_id)
        assert job.playlist_id is None


# ---------------------------------------------------------------------------
# Duplicate active job guard
# ---------------------------------------------------------------------------

class TestDuplicateGuard:
    def test_second_create_raises_when_active(self):
        store = JobStore()
        store.create_job("pl-1", "My Playlist", _entries("v1"))
        with pytest.raises(ValueError, match="active_job_exists"):
            store.create_job("pl-1", "My Playlist", _entries("v2"))

    def test_second_create_succeeds_after_first_terminal(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        store.update_item_state(job_id, "v1", "done")
        # Now terminal — a new job should succeed
        job_id2 = store.create_job("pl-1", "My Playlist", _entries("v2"))
        assert job_id2 != job_id

    def test_single_video_jobs_not_guarded(self):
        store = JobStore()
        store.create_job(None, None, _entries("v1"))
        # No playlist_id → no guard
        store.create_job(None, None, _entries("v2"))


# ---------------------------------------------------------------------------
# update_item_state
# ---------------------------------------------------------------------------

class TestUpdateItemState:
    def test_state_transitions(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        store.update_item_state(job_id, "v1", "downloading")
        job = store.get_job(job_id)
        assert job.items[0].state == "downloading"

    def test_done_sets_finished_at(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        store.update_item_state(job_id, "v1", "done")
        job = store.get_job(job_id)
        assert job.items[0].finished_at is not None

    def test_renamed_to_stored(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        store.update_item_state(job_id, "v1", "done", renamed_to="Artist - Track")
        job = store.get_job(job_id)
        assert job.items[0].renamed_to == "Artist - Track"

    def test_error_stored(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        store.update_item_state(job_id, "v1", "failed", error="HTTP 403")
        job = store.get_job(job_id)
        assert job.items[0].error == "HTTP 403"

    def test_is_terminal_after_all_done(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1", "v2"))
        store.update_item_state(job_id, "v1", "done")
        store.update_item_state(job_id, "v2", "done")
        assert store.get_job(job_id).is_terminal()


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------

class TestEviction:
    def test_oldest_terminal_evicted_at_capacity(self):
        store = JobStore()
        first_id = None
        for i in range(store._MAX_JOBS):
            vid = f"v{i}"
            job_id = store.create_job(f"pl-{i}", f"Playlist {i}", _entries(vid))
            # Mark terminal immediately
            store.update_item_state(job_id, vid, "done")
            if i == 0:
                first_id = job_id
        # All MAX_JOBS slots are terminal. Creating one more should evict the oldest.
        new_id = store.create_job("pl-new", "New Playlist", _entries("vN"))
        assert store.get_job(first_id) is None
        assert store.get_job(new_id) is not None


# ---------------------------------------------------------------------------
# cancel_all_jobs
# ---------------------------------------------------------------------------

class TestCancelAllJobs:
    def test_pending_items_cancelled(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1", "v2"))
        cancelled = store.cancel_all_jobs()
        assert cancelled == 2
        job = store.get_job(job_id)
        assert all(i.state == "cancelled" for i in job.items)

    def test_single_video_jobs_not_cancelled(self):
        store = JobStore()
        store.create_job(None, None, _entries("v1"))
        cancelled = store.cancel_all_jobs()
        assert cancelled == 0

    def test_already_terminal_not_affected(self):
        store = JobStore()
        job_id = store.create_job("pl-1", "My Playlist", _entries("v1"))
        store.update_item_state(job_id, "v1", "done")
        cancelled = store.cancel_all_jobs()
        assert cancelled == 0
