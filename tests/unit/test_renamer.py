"""Tests for siphon.renamer — pure functions and file I/O helpers."""
import os
from unittest.mock import patch, MagicMock

import pytest

from siphon import renamer
from siphon.renamer import (
    sanitize,
    safe_replace,
    strip_noise,
    extract_extension,
    resolve_file_path,
    embed_metadata,
    update_title_metadata,
    _VISUAL_EQUIVALENT_MAP,
)


# ---------------------------------------------------------------------------
# sanitize()
# ---------------------------------------------------------------------------

class TestSanitize:
    def test_removes_slash(self):
        assert "/" not in sanitize("AC/DC")

    def test_removes_all_unsafe_chars(self):
        result = sanitize('file/name\\:*?"<>|')
        for ch in '/\\:*?"<>|':
            assert ch not in result

    def test_strips_whitespace(self):
        assert sanitize("  hello  ") == "hello"

    def test_clean_title_unchanged(self):
        assert sanitize("Beach House - Space Song") == "Beach House - Space Song"

    def test_empty_string(self):
        assert sanitize("") == ""


# ---------------------------------------------------------------------------
# safe_replace()
# ---------------------------------------------------------------------------

class TestSafeReplace:
    def test_slash_replaced_with_visual_equivalent(self):
        result = safe_replace("AC/DC")
        assert "/" not in result
        assert _VISUAL_EQUIVALENT_MAP["/"] in result

    def test_all_unsafe_chars_replaced(self):
        unsafe = ''.join(_VISUAL_EQUIVALENT_MAP.keys())
        result = safe_replace(unsafe)
        for ch in _VISUAL_EQUIVALENT_MAP:
            assert ch not in result
        for replacement in _VISUAL_EQUIVALENT_MAP.values():
            assert replacement in result

    def test_clean_title_unchanged(self):
        assert safe_replace("Beach House - Space Song") == "Beach House - Space Song"


# ---------------------------------------------------------------------------
# strip_noise()
# ---------------------------------------------------------------------------

class TestStripNoise:
    def test_strips_official_music_video(self):
        assert "Official Music Video" not in strip_noise("Song (Official Music Video)")

    def test_strips_official_video_parens(self):
        result = strip_noise("Track (Official Video)")
        assert "(Official Video)" not in result

    def test_strips_official_audio_brackets(self):
        result = strip_noise("Track [Official Audio]")
        assert "[Official Audio]" not in result

    def test_strips_lyric_video(self):
        result = strip_noise("Song (Lyric Video)")
        assert "(Lyric Video)" not in result

    def test_strips_hd(self):
        result = strip_noise("Song [HD]")
        assert "[HD]" not in result

    def test_strips_4k(self):
        result = strip_noise("Song [4K]")
        assert "[4K]" not in result

    def test_strips_remastered(self):
        result = strip_noise("Song (2012 Remastered)")
        assert "Remastered" not in result

    def test_no_false_positive_on_clean_title(self):
        title = "Beach House - Space Song"
        assert strip_noise(title) == title

    def test_empty_patterns_disables_stripping(self):
        title = "Song (Official Video)"
        assert strip_noise(title, patterns=[]) == title

    def test_custom_pattern(self):
        result = strip_noise("Song (Demo)", patterns=[r"demo"])
        assert "(Demo)" not in result

    def test_iterative_stripping(self):
        result = strip_noise("Song (Official Video) (HD)")
        assert "(Official Video)" not in result
        assert "(HD)" not in result


# ---------------------------------------------------------------------------
# extract_extension()
# ---------------------------------------------------------------------------

class TestExtractExtension:
    def test_mp3(self):
        stem, ext = extract_extension("song.mp3")
        assert stem == "song"
        assert ext == ".mp3"

    def test_opus(self):
        stem, ext = extract_extension("song.opus")
        assert stem == "song"
        assert ext == ".opus"

    def test_mp4(self):
        stem, ext = extract_extension("video.mp4")
        assert stem == "video"
        assert ext == ".mp4"

    def test_unknown_extension_falls_back(self):
        stem, ext = extract_extension("file.wav")
        assert stem == "file"
        assert ext == ".wav"

    def test_stem_with_dots(self):
        stem, ext = extract_extension("artist - track.mp3")
        assert stem == "artist - track"
        assert ext == ".mp3"


# ---------------------------------------------------------------------------
# resolve_file_path()
# ---------------------------------------------------------------------------

class TestResolveFilePath:
    def test_finds_existing_mp3(self, tmp_path):
        mp3 = tmp_path / "artist - track.mp3"
        mp3.touch()
        result = resolve_file_path(str(tmp_path), "artist - track")
        assert result == str(mp3)

    def test_returns_none_when_missing(self, tmp_path):
        result = resolve_file_path(str(tmp_path), "nonexistent")
        assert result is None

    def test_finds_first_matching_extension(self, tmp_path):
        # mp3 takes priority over opus (both present)
        mp3 = tmp_path / "track.mp3"
        opus = tmp_path / "track.opus"
        mp3.touch()
        opus.touch()
        result = resolve_file_path(str(tmp_path), "track")
        assert result is not None
        assert os.path.exists(result)


# ---------------------------------------------------------------------------
# embed_metadata() — MP3 ID3 tags
# ---------------------------------------------------------------------------

class TestEmbedMetadata:
    def test_embed_original_title_and_final_name(self, tmp_path):
        from mutagen.id3 import ID3, TIT2
        mp3_path = tmp_path / "song.mp3"
        # Write minimal ID3 header so mutagen can work with it.
        tags = ID3()
        tags.add(TIT2(encoding=3, text=["placeholder"]))
        tags.save(str(mp3_path))

        embed_metadata(str(mp3_path), "Original YT Title", "Artist - Track")

        tags2 = ID3(str(mp3_path))
        txxx = tags2.getall("TXXX:original_title")
        assert txxx, "TXXX:original_title frame not written"
        assert txxx[0].text[0] == "Original YT Title"
        tit2 = tags2.getall("TIT2")
        assert tit2[0].text[0] == "Artist - Track"

    def test_noop_on_unknown_extension(self, tmp_path):
        wav_path = tmp_path / "song.wav"
        wav_path.touch()
        # Should not raise
        embed_metadata(str(wav_path), "Title", "Name")

    def test_noop_when_both_empty(self, tmp_path):
        mp3_path = tmp_path / "song.mp3"
        mp3_path.touch()
        # Should not raise
        embed_metadata(str(mp3_path), "", "")


# ---------------------------------------------------------------------------
# update_title_metadata()
# ---------------------------------------------------------------------------

class TestUpdateTitleMetadata:
    def test_updates_tit2(self, tmp_path):
        from mutagen.id3 import ID3, TIT2
        mp3_path = tmp_path / "song.mp3"
        tags = ID3()
        tags.add(TIT2(encoding=3, text=["old title"]))
        tags.save(str(mp3_path))

        update_title_metadata(str(mp3_path), "new title")

        tags2 = ID3(str(mp3_path))
        assert tags2["TIT2"].text[0] == "new title"

    def test_noop_on_empty_title(self, tmp_path):
        mp3_path = tmp_path / "song.mp3"
        mp3_path.touch()
        update_title_metadata(str(mp3_path), "")


# ---------------------------------------------------------------------------
# MusicBrainz tier — _mb_search with mocked HTTP
# ---------------------------------------------------------------------------

class TestMbSearch:
    def test_returns_parsed_json_on_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"recordings": []}

        with patch("siphon.renamer.requests.get", return_value=mock_response):
            result = renamer._mb_search("Beach House Space Song", "TestApp/1.0")

        assert result == {"recordings": []}

    def test_returns_none_on_non_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch("siphon.renamer.requests.get", return_value=mock_response):
            result = renamer._mb_search("Some Song", "TestApp/1.0")

        assert result is None

    def test_returns_none_on_request_exception(self):
        import requests as req
        with patch("siphon.renamer.requests.get", side_effect=req.RequestException("timeout")):
            result = renamer._mb_search("Some Song", "TestApp/1.0")

        assert result is None
