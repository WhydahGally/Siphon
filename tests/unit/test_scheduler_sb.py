"""Unit tests for scheduler SponsorBlock health gate."""
from unittest.mock import patch, MagicMock
import pytest

from siphon.scheduler import PlaylistScheduler


class TestSchedulerSbHealthGate:
    """Tests for sb-require-for-sync in scheduler _fire()."""

    @patch("siphon.scheduler.registry")
    def test_sync_proceeds_when_sb_healthy(self, mock_registry):
        mock_registry.get_playlist_by_id.return_value = {
            "id": "pl1", "name": "Test", "watched": 1,
            "check_interval_secs": 3600,
        }
        mock_registry.get_setting.return_value = "true"

        sync_fn = MagicMock()
        scheduler = PlaylistScheduler(sync_fn)

        with patch("siphon.downloader.check_sb_health", return_value={"status": "healthy"}):
            with patch.object(scheduler, "_rearm"):
                scheduler._fire("pl1")

        sync_fn.assert_called_once()

    @patch("siphon.scheduler.registry")
    def test_sync_skipped_when_sb_unhealthy(self, mock_registry):
        mock_registry.get_playlist_by_id.return_value = {
            "id": "pl1", "name": "Test", "watched": 1,
            "check_interval_secs": 3600,
        }
        mock_registry.get_setting.return_value = "true"

        sync_fn = MagicMock()
        scheduler = PlaylistScheduler(sync_fn)

        with patch("siphon.downloader.check_sb_health", return_value={"status": "unhealthy", "reason": "timeout"}):
            with patch.object(scheduler, "_rearm"):
                scheduler._fire("pl1")

        sync_fn.assert_not_called()
        mock_registry.append_playlist_warning.assert_called_once_with(
            "pl1", "sponsorblock", "Sync skipped: SponsorBlock unavailable"
        )

    @patch("siphon.scheduler.registry")
    def test_sync_proceeds_when_setting_off(self, mock_registry):
        mock_registry.get_playlist_by_id.return_value = {
            "id": "pl1", "name": "Test", "watched": 1,
            "check_interval_secs": 3600,
        }
        mock_registry.get_setting.return_value = "false"

        sync_fn = MagicMock()
        scheduler = PlaylistScheduler(sync_fn)

        with patch.object(scheduler, "_rearm"):
            scheduler._fire("pl1")

        sync_fn.assert_called_once()
