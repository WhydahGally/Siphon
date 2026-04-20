"""Tests for siphon.models — DownloadJob, JobItem, Pydantic models."""
import time

import pytest

from siphon.models import DownloadJob, JobItem, PlaylistCreate, PlaylistPatch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_items(*states: str) -> list:
    return [
        JobItem(
            video_id=f"vid{i}",
            yt_title=f"Title {i}",
            url=f"https://youtu.be/vid{i}",
            state=state,
        )
        for i, state in enumerate(states)
    ]


def _make_job(*states: str, **kwargs) -> DownloadJob:
    items = _make_items(*states)
    return DownloadJob(
        job_id="job-1",
        playlist_id="pl-1",
        playlist_name="My Playlist",
        items=items,
        created_at=time.time(),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# DownloadJob.done_count / failed_count
# ---------------------------------------------------------------------------

def test_done_count():
    job = _make_job("done", "done", "pending")
    assert job.done_count == 2


def test_failed_count():
    job = _make_job("failed", "done", "failed")
    assert job.failed_count == 2


def test_total():
    job = _make_job("pending", "pending", "pending")
    assert job.total == 3


def test_original_total_set_on_init():
    job = _make_job("pending", "pending")
    assert job.original_total == 2


# ---------------------------------------------------------------------------
# DownloadJob.is_terminal()
# ---------------------------------------------------------------------------

def test_is_terminal_all_done():
    job = _make_job("done", "done")
    assert job.is_terminal() is True


def test_is_terminal_all_failed():
    job = _make_job("failed", "failed")
    assert job.is_terminal() is True


def test_is_terminal_mix_done_failed():
    job = _make_job("done", "failed")
    assert job.is_terminal() is True


def test_is_terminal_mix_done_cancelled():
    job = _make_job("done", "cancelled")
    assert job.is_terminal() is True


def test_not_terminal_when_pending():
    job = _make_job("done", "pending")
    assert job.is_terminal() is False


def test_not_terminal_when_downloading():
    job = _make_job("done", "downloading")
    assert job.is_terminal() is False


def test_not_terminal_empty_items():
    job = _make_job()
    # No items → is_terminal returns False (bool([]) is False)
    assert job.is_terminal() is False


# ---------------------------------------------------------------------------
# JobItem properties
# ---------------------------------------------------------------------------

def test_job_item_defaults():
    item = JobItem(video_id="v1", yt_title="Song", url="https://youtu.be/v1", state="pending")
    assert item.renamed_to is None
    assert item.error is None
    assert item.started_at is None
    assert item.finished_at is None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

def test_playlist_create_defaults():
    p = PlaylistCreate(url="https://youtube.com/playlist?list=PL123")
    assert p.format == "mp3"
    assert p.quality == "best"
    assert p.auto_rename is False
    assert p.watched is True
    assert p.download is False


def test_playlist_create_custom():
    p = PlaylistCreate(
        url="https://youtube.com/playlist?list=PL123",
        format="mp4",
        quality="1080",
        auto_rename=True,
    )
    assert p.format == "mp4"
    assert p.quality == "1080"
    assert p.auto_rename is True


def test_playlist_patch_all_none_by_default():
    p = PlaylistPatch()
    assert p.watched is None
    assert p.check_interval_secs is None
    assert p.auto_rename is None
