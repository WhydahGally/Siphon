"""Unit tests for warnings serialization and sb-require-for-sync setting."""
import json
import pytest
from unittest.mock import patch, MagicMock

from siphon import registry


class TestPlaylistWarnings:
    """Tests for playlist warnings column handling."""

    def test_append_playlist_warning(self, tmp_path):
        registry.init_db(str(tmp_path))
        # Create a playlist
        registry.add_playlist(
            playlist_id="pw1",
            name="Test Warnings",
            url="https://example.com/playlist",
            fmt="mp3",
            quality="best",
            output_dir=str(tmp_path),
        )
        # Append a warning
        registry.append_playlist_warning("pw1", "sponsorblock", "Test warning")

        row = registry.get_playlist_by_id("pw1")
        warnings = json.loads(row["warnings"])
        assert len(warnings) == 1
        assert warnings[0]["type"] == "sponsorblock"
        assert warnings[0]["message"] == "Test warning"
        assert "timestamp" in warnings[0]

    def test_aggregate_sb_warnings_clears_on_zero_failures(self, tmp_path):
        registry.init_db(str(tmp_path))
        registry.add_playlist(
            playlist_id="pw2",
            name="Test Agg",
            url="https://example.com/playlist",
            fmt="mp3",
            quality="best",
            output_dir=str(tmp_path),
        )
        # Add a pre-existing warning
        registry.append_playlist_warning("pw2", "sponsorblock", "Old warning")

        # Aggregate with no failed items
        registry.aggregate_sb_warnings("pw2")

        row = registry.get_playlist_by_id("pw2")
        # warnings should be NULL (no warnings left)
        assert row["warnings"] is None

    def test_sb_require_for_sync_setting(self, tmp_path):
        registry.init_db(str(tmp_path))
        # Default: not set
        assert registry.get_setting("sb_require_for_sync") is None

        # Set it
        registry.set_setting("sb_require_for_sync", "true")
        assert registry.get_setting("sb_require_for_sync") == "true"

        # Update it
        registry.set_setting("sb_require_for_sync", "false")
        assert registry.get_setting("sb_require_for_sync") == "false"
