"""Tests for siphon.downloader — filter_entries() with hand-crafted dicts."""
from unittest.mock import patch

import pytest

from siphon.downloader import filter_entries


def _entry(video_id: str, title: str = "Song") -> dict:
    return {"id": video_id, "url": f"https://youtu.be/{video_id}", "title": title}


# ---------------------------------------------------------------------------
# filter_entries
# ---------------------------------------------------------------------------

class TestFilterEntries:
    def test_new_entries_pass_through(self):
        entries = [_entry("v1"), _entry("v2")]
        with (
            patch("siphon.downloader.registry.get_downloaded_ids", return_value=set()),
            patch("siphon.downloader.registry.is_ignored", return_value=False),
            patch("siphon.downloader.registry.get_failed_attempt_count", return_value=0),
        ):
            result = filter_entries(entries, "pl-1")
        assert [e["id"] for e in result] == ["v1", "v2"]

    def test_already_downloaded_filtered_out(self):
        entries = [_entry("v1"), _entry("v2")]
        with (
            patch("siphon.downloader.registry.get_downloaded_ids", return_value={"v1"}),
            patch("siphon.downloader.registry.is_ignored", return_value=False),
            patch("siphon.downloader.registry.get_failed_attempt_count", return_value=0),
        ):
            result = filter_entries(entries, "pl-1")
        assert [e["id"] for e in result] == ["v2"]

    def test_all_already_downloaded_returns_empty(self):
        entries = [_entry("v1"), _entry("v2")]
        with (
            patch("siphon.downloader.registry.get_downloaded_ids", return_value={"v1", "v2"}),
            patch("siphon.downloader.registry.is_ignored", return_value=False),
            patch("siphon.downloader.registry.get_failed_attempt_count", return_value=0),
        ):
            result = filter_entries(entries, "pl-1")
        assert result == []

    def test_empty_entries_returns_empty(self):
        with (
            patch("siphon.downloader.registry.get_downloaded_ids", return_value=set()),
            patch("siphon.downloader.registry.is_ignored", return_value=False),
            patch("siphon.downloader.registry.get_failed_attempt_count", return_value=0),
        ):
            result = filter_entries([], "pl-1")
        assert result == []

    def test_ignored_items_filtered_out(self):
        entries = [_entry("v1"), _entry("v2")]
        with (
            patch("siphon.downloader.registry.get_downloaded_ids", return_value=set()),
            patch("siphon.downloader.registry.is_ignored", side_effect=lambda vid, pid: vid == "v1"),
            patch("siphon.downloader.registry.get_failed_attempt_count", return_value=0),
        ):
            result = filter_entries(entries, "pl-1")
        assert [e["id"] for e in result] == ["v2"]

    def test_items_with_3_or_more_failures_skipped(self):
        entries = [_entry("v1"), _entry("v2")]
        with (
            patch("siphon.downloader.registry.get_downloaded_ids", return_value=set()),
            patch("siphon.downloader.registry.is_ignored", return_value=False),
            patch("siphon.downloader.registry.get_failed_attempt_count",
                  side_effect=lambda vid, pid: 3 if vid == "v1" else 0),
        ):
            result = filter_entries(entries, "pl-1")
        assert [e["id"] for e in result] == ["v2"]

    def test_items_with_fewer_than_3_failures_included(self):
        entries = [_entry("v1")]
        with (
            patch("siphon.downloader.registry.get_downloaded_ids", return_value=set()),
            patch("siphon.downloader.registry.is_ignored", return_value=False),
            patch("siphon.downloader.registry.get_failed_attempt_count", return_value=2),
        ):
            result = filter_entries(entries, "pl-1")
        assert [e["id"] for e in result] == ["v1"]
