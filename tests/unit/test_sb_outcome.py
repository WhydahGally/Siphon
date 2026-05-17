"""Unit tests for SponsorBlock outcome tracking."""
from unittest.mock import patch, MagicMock
import pytest

from siphon.downloader import _YtdlpLogger


class TestYtdlpLoggerSbWarnings:
    """Tests for _YtdlpLogger SB warning buffering."""

    def test_captures_sponsorblock_warning(self):
        lg = _YtdlpLogger()
        lg.warning("Unable to communicate with SponsorBlock API")
        assert len(lg.sb_warnings) == 1
        assert "SponsorBlock" in lg.sb_warnings[0]

    def test_captures_sponsor_warning_with_error_detail(self):
        lg = _YtdlpLogger()
        lg.warning("Unable to communicate with SponsorBlock API: ConnectionError")
        assert len(lg.sb_warnings) == 1

    def test_ignores_unrelated_warning(self):
        lg = _YtdlpLogger()
        lg.warning("Some other warning about formats")
        assert len(lg.sb_warnings) == 0

    def test_captures_sb_error(self):
        lg = _YtdlpLogger()
        lg.error("Unable to communicate with SponsorBlock API: connection refused")
        assert len(lg.sb_warnings) == 1

    def test_ignores_benign_sb_warning(self):
        lg = _YtdlpLogger()
        lg.warning("Some SponsorBlock segments are from a video of different duration")
        assert len(lg.sb_warnings) == 0

    def test_multiple_warnings_accumulated(self):
        lg = _YtdlpLogger()
        lg.warning("Unable to communicate with SponsorBlock API: timeout")
        lg.warning("Unable to communicate with SponsorBlock API: refused")
        assert len(lg.sb_warnings) == 2


class TestSbOutcomeFromDownload:
    """Tests for sb_outcome determination in download()."""

    @patch("siphon.downloader.check_ffmpeg", return_value=True)
    @patch("siphon.downloader.YoutubeDL")
    def test_outcome_disabled_when_no_sb_categories(self, mock_ydl_cls, mock_ffmpeg):
        """When sponsorblock_categories is empty, outcome should be 'disabled'."""
        from siphon.downloader import download
        from siphon.formats import DownloadOptions
        import tempfile, os

        mock_ydl = MagicMock()
        mock_ydl.__enter__ = lambda s: s
        mock_ydl.__exit__ = MagicMock(return_value=False)
        mock_ydl.extract_info.return_value = {"_type": "video"}
        mock_ydl.download.return_value = None
        mock_ydl_cls.return_value = mock_ydl

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download(
                url="https://example.com/video",
                output_dir=tmpdir,
                options=DownloadOptions(mode="audio", audio_format="opus"),
            )

        assert result == "disabled"

    @patch("siphon.downloader.check_ffmpeg", return_value=True)
    @patch("siphon.downloader.YoutubeDL")
    def test_outcome_success_via_capture_pp(self, mock_ydl_cls, mock_ffmpeg):
        """When SBOutcomeCapture PP sees sponsorblock_chapters, outcome is 'success'."""
        from siphon.downloader import download
        from siphon.formats import DownloadOptions
        import tempfile

        class FakeYDL(MagicMock):
            def __init__(self, opts=None, **kw):
                super().__init__(**kw)
                self._pps = []
                self.params = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def extract_info(self, url, download=True):
                return {"_type": "video"}

            def add_post_processor(self, pp, when=None):
                self._pps.append((pp, when))

            def download(self, urls):
                info = {"sponsorblock_chapters": [{"start": 0, "end": 30}]}
                for pp, when in self._pps:
                    if when == "after_filter" and type(pp).__name__ == "_SBOutcomeCapture":
                        pp.run(info)

        mock_ydl_cls.side_effect = lambda opts: FakeYDL(opts)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download(
                url="https://example.com/video",
                output_dir=tmpdir,
                options=DownloadOptions(
                    mode="audio",
                    audio_format="opus",
                    sponsorblock_categories=["music_offtopic"],
                ),
            )

        assert result == "success"

    @patch("siphon.downloader.check_ffmpeg", return_value=True)
    @patch("siphon.downloader.YoutubeDL")
    def test_outcome_no_segments_when_empty_chapters_no_warnings(self, mock_ydl_cls, mock_ffmpeg):
        """When capture PP sees empty chapters and no warnings, outcome is 'no_segments'."""
        from siphon.downloader import download
        from siphon.formats import DownloadOptions
        import tempfile

        class FakeYDL(MagicMock):
            def __init__(self, opts=None, **kw):
                super().__init__(**kw)
                self._pps = []
                self.params = {}

            def __enter__(self):
                return self

            def __exit__(self, *a):
                pass

            def extract_info(self, url, download=True):
                return {"_type": "video"}

            def add_post_processor(self, pp, when=None):
                self._pps.append((pp, when))

            def download(self, urls):
                info = {"sponsorblock_chapters": []}
                for pp, when in self._pps:
                    if when == "after_filter" and type(pp).__name__ == "_SBOutcomeCapture":
                        pp.run(info)

        mock_ydl_cls.side_effect = lambda opts: FakeYDL(opts)

        with tempfile.TemporaryDirectory() as tmpdir:
            result = download(
                url="https://example.com/video",
                output_dir=tmpdir,
                options=DownloadOptions(
                    mode="audio",
                    audio_format="opus",
                    sponsorblock_categories=["music_offtopic"],
                ),
            )

        assert result == "no_segments"
