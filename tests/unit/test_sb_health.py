"""Unit tests for SponsorBlock health check."""
import urllib.error
from unittest.mock import patch, MagicMock

from siphon.downloader import check_sb_health


class TestCheckSbHealth:
    """Tests for check_sb_health()."""

    @patch("siphon.downloader.urllib.request.urlopen")
    def test_healthy_on_200(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        result = check_sb_health()
        assert result == {"status": "healthy"}

    @patch("siphon.downloader.urllib.request.urlopen")
    def test_unhealthy_on_timeout_after_retries(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("timed out")

        result = check_sb_health()
        assert result == {"status": "unhealthy", "reason": "timeout"}
        assert mock_urlopen.call_count == 3

    @patch("siphon.downloader.urllib.request.urlopen")
    def test_unhealthy_on_5xx(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=503, msg="Service Unavailable", hdrs={}, fp=None
        )

        result = check_sb_health()
        assert result == {"status": "unhealthy", "reason": "server_error"}
        # No retry on 5xx
        assert mock_urlopen.call_count == 1

    @patch("siphon.downloader.urllib.request.urlopen")
    def test_unhealthy_on_4xx(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=403, msg="Forbidden", hdrs={}, fp=None
        )

        result = check_sb_health()
        assert result == {"status": "unhealthy", "reason": "client_error"}
        # No retry on 4xx
        assert mock_urlopen.call_count == 1

    @patch("siphon.downloader.urllib.request.urlopen")
    def test_healthy_on_404(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url="", code=404, msg="Not Found", hdrs={}, fp=None
        )

        result = check_sb_health()
        assert result == {"status": "healthy"}
        assert mock_urlopen.call_count == 1

    @patch("siphon.downloader.urllib.request.urlopen")
    def test_retries_on_url_error_then_succeeds(self, mock_urlopen):
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)

        mock_urlopen.side_effect = [
            urllib.error.URLError("Connection refused"),
            resp,
        ]

        result = check_sb_health()
        assert result == {"status": "healthy"}
        assert mock_urlopen.call_count == 2
