"""Tests for siphon.progress.make_progress_event()."""
import pytest

from siphon.progress import make_progress_event


def test_status_passed_through():
    event = make_progress_event({"status": "finished", "filename": "a.mp3"})
    assert event["status"] == "finished"


def test_status_defaults_to_downloading():
    event = make_progress_event({"filename": "a.mp3"})
    assert event["status"] == "downloading"


def test_filename():
    event = make_progress_event({"filename": "/tmp/song.mp3"})
    assert event["filename"] == "/tmp/song.mp3"


def test_filename_missing_defaults_to_empty_string():
    event = make_progress_event({})
    assert event["filename"] == ""


def test_total_bytes_preferred_over_estimate():
    event = make_progress_event({
        "filename": "a.mp3",
        "total_bytes": 1000,
        "total_bytes_estimate": 999,
    })
    assert event["total_bytes"] == 1000


def test_total_bytes_falls_back_to_estimate_when_none():
    event = make_progress_event({
        "filename": "a.mp3",
        "total_bytes": None,
        "total_bytes_estimate": 500,
    })
    assert event["total_bytes"] == 500


def test_total_bytes_none_when_both_absent():
    event = make_progress_event({"filename": "a.mp3"})
    assert event["total_bytes"] is None


def test_downloaded_bytes():
    event = make_progress_event({"filename": "a.mp3", "downloaded_bytes": 256})
    assert event["downloaded_bytes"] == 256


def test_speed_and_eta():
    event = make_progress_event({"filename": "a.mp3", "speed": 1024.5, "eta": 30})
    assert event["speed"] == pytest.approx(1024.5)
    assert event["eta"] == 30


def test_optional_fields_none_when_absent():
    event = make_progress_event({"filename": "a.mp3"})
    assert event["downloaded_bytes"] is None
    assert event["speed"] is None
    assert event["eta"] is None
