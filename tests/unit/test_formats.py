"""Tests for siphon.formats."""
from unittest.mock import patch

import pytest

from siphon.formats import (
    DownloadOptions,
    VALID_RESOLUTIONS,
    VALID_VIDEO_FORMATS,
    VALID_AUDIO_FORMATS,
    build_video_format_selector,
    build_audio_postprocessors,
    build_options,
    check_ffmpeg,
)


# ---------------------------------------------------------------------------
# DownloadOptions — video mode
# ---------------------------------------------------------------------------

def test_video_defaults():
    opts = DownloadOptions(mode="video")
    assert opts.quality == "best"
    assert opts.video_format == "mp4"


def test_video_explicit_quality():
    opts = DownloadOptions(mode="video", quality="1080")
    assert opts.quality == "1080"


def test_video_invalid_quality():
    with pytest.raises(ValueError, match="Invalid quality"):
        DownloadOptions(mode="video", quality="999")


def test_video_invalid_format():
    with pytest.raises(ValueError, match="Invalid video format"):
        DownloadOptions(mode="video", video_format="avi")


def test_video_all_valid_resolutions():
    for q in VALID_RESOLUTIONS:
        opts = DownloadOptions(mode="video", quality=q)
        assert opts.quality == q


def test_video_all_valid_formats():
    for fmt in VALID_VIDEO_FORMATS:
        opts = DownloadOptions(mode="video", video_format=fmt)
        assert opts.video_format == fmt


# ---------------------------------------------------------------------------
# DownloadOptions — audio mode
# ---------------------------------------------------------------------------

def test_audio_mp3():
    opts = DownloadOptions(mode="audio", audio_format="mp3")
    assert opts.audio_format == "mp3"


def test_audio_opus():
    opts = DownloadOptions(mode="audio", audio_format="opus")
    assert opts.audio_format == "opus"


def test_audio_missing_format():
    with pytest.raises(ValueError, match="audio_format must be set"):
        DownloadOptions(mode="audio")


def test_audio_invalid_format():
    with pytest.raises(ValueError, match="Invalid audio format"):
        DownloadOptions(mode="audio", audio_format="flac")


# ---------------------------------------------------------------------------
# DownloadOptions — invalid mode
# ---------------------------------------------------------------------------

def test_invalid_mode():
    with pytest.raises(ValueError, match="Invalid mode"):
        DownloadOptions(mode="stream")


# ---------------------------------------------------------------------------
# build_video_format_selector
# ---------------------------------------------------------------------------

def test_format_selector_best():
    selector = build_video_format_selector("best")
    assert selector == "bestvideo+bestaudio/best"


def test_format_selector_height():
    selector = build_video_format_selector("1080")
    assert "1080" in selector
    assert selector.startswith("bestvideo[height<=1080]")


# ---------------------------------------------------------------------------
# build_audio_postprocessors
# ---------------------------------------------------------------------------

def test_audio_postprocessors_mp3():
    pps = build_audio_postprocessors("mp3")
    codecs = [p.get("preferredcodec") for p in pps]
    assert "mp3" in codecs


def test_audio_postprocessors_opus():
    pps = build_audio_postprocessors("opus")
    codecs = [p.get("preferredcodec") for p in pps]
    assert "opus" in codecs


def test_audio_postprocessors_invalid():
    with pytest.raises(ValueError):
        build_audio_postprocessors("flac")


# ---------------------------------------------------------------------------
# build_options
# ---------------------------------------------------------------------------

def test_build_options_mp3():
    opts = build_options("mp3")
    assert opts.mode == "audio"
    assert opts.audio_format == "mp3"


def test_build_options_mp4():
    opts = build_options("mp4", quality="1080")
    assert opts.mode == "video"
    assert opts.video_format == "mp4"
    assert opts.quality == "1080"


# ---------------------------------------------------------------------------
# check_ffmpeg
# ---------------------------------------------------------------------------

def test_check_ffmpeg_found():
    with patch("siphon.formats.shutil.which", return_value="/usr/bin/ffmpeg"):
        assert check_ffmpeg() is True


def test_check_ffmpeg_not_found():
    with patch("siphon.formats.shutil.which", return_value=None):
        assert check_ffmpeg() is False
