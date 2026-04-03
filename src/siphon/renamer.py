import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class RenameResult:
    original_title: str
    final_name: str        # filename stem, no extension
    tier: str              # "yt_metadata" | "title_separator" | "musicbrainz" | "yt_title_fallback"
    new_path: str          # absolute path to renamed file on disk

# ---------------------------------------------------------------------------
# MusicBrainz rate-limiting state
# ---------------------------------------------------------------------------

_mb_lock = threading.Lock()
_last_mb_request_time: float = 0.0

_MB_API_URL = "https://musicbrainz.org/ws/2/recording"
_MB_SCORE_MIN = 85
_MB_OVERLAP_MIN = 0.4

_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|]')

# Common YouTube title separators, in order of reliability.
# ⧸⧸ is yt-dlp's filename substitute for //; we check both.
_TITLE_SEPARATORS = [' ⧸⧸ ', ' // ', ' – ', ' — ', ' - ']


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rename_file(info_dict: dict, mb_user_agent: Optional[str] = None) -> Optional["RenameResult"]:
    """
    Rename the downloaded file to 'Artist - Track.ext'.

    Four-tier resolution chain:
      1.   YouTube metadata    — info_dict['artist'] + info_dict['track'] if both present.
      1.5  Title separator     — splits the YT title on // / – / — / - patterns.
      2.   MusicBrainz         — text search if mb_user_agent is configured.
      3.   YT title fallback   — sanitized info_dict['title'].

    Returns a RenameResult on success, or None if no filepath was found.
    Non-fatal: OS rename errors are logged and swallowed.
    """
    filepath = info_dict.get("filepath") or info_dict.get("filename")
    if not filepath:
        logger.warning("renamer: no filepath in info_dict, skipping rename")
        return None

    yt_title = (info_dict.get("title") or "").strip()

    # Tier 1: YouTube music catalog metadata
    artist = (info_dict.get("artist") or "").strip()
    track = (info_dict.get("track") or "").strip()
    if artist and track:
        artist = _resolve_primary_artist(artist, info_dict)
        final_name = f"{artist} - {track}"
        new_path = _do_rename(filepath, final_name)
        logger.debug("renamer: tier 1 resolved via YT metadata")
        return RenameResult(original_title=yt_title, final_name=final_name, tier="yt_metadata", new_path=new_path)

    # Tier 1.5: Title separator parsing
    artist_hint, track_hint = _parse_title_separator(yt_title)
    if artist_hint and track_hint:
        final_name = f"{sanitize(artist_hint)} - {sanitize(track_hint)}"
        new_path = _do_rename(filepath, final_name)
        logger.debug("renamer: tier 1.5 resolved via title separator")
        return RenameResult(original_title=yt_title, final_name=final_name, tier="title_separator", new_path=new_path)

    # Tier 2: MusicBrainz lookup
    if mb_user_agent:
        mb_result = _mb_search(yt_title, mb_user_agent)
        if mb_result:
            recordings = mb_result.get("recordings") or []
            if recordings and _mb_passes_threshold(recordings[0], yt_title):
                final_name = _mb_format_name(recordings[0])
                new_path = _do_rename(filepath, final_name)
                logger.debug("renamer: tier 2 resolved via MusicBrainz")
                return RenameResult(original_title=yt_title, final_name=final_name, tier="musicbrainz", new_path=new_path)
            else:
                logger.debug("renamer: tier 2 result below threshold, falling through")

    # Tier 3: YT title fallback
    final_name = sanitize(yt_title) if yt_title else "unknown"
    new_path = _do_rename(filepath, final_name)
    logger.debug("renamer: tier 3 fallback to YT title")
    return RenameResult(original_title=yt_title, final_name=final_name, tier="yt_title_fallback", new_path=new_path)


# ---------------------------------------------------------------------------
# File rename helper
# ---------------------------------------------------------------------------

def _do_rename(filepath: str, name: str) -> str:
    """Rename filepath to name, preserving extension. Logs and swallows OSError. Returns new path."""
    _, ext = os.path.splitext(filepath)
    dirpath = os.path.dirname(filepath)
    new_path = os.path.join(dirpath, f"{name}{ext}")
    if filepath == new_path:
        return new_path
    try:
        os.rename(filepath, new_path)
        logger.debug("renamer: '%s' → '%s'", os.path.basename(filepath), os.path.basename(new_path))
    except OSError as exc:
        logger.warning("renamer: failed to rename '%s': %s", filepath, exc)
        return filepath
    return new_path


def sanitize(name: str) -> str:
    """Strip filesystem-unsafe characters: / \\ : * ? \" < > |"""
    return _UNSAFE_CHARS.sub("", name).strip()


def _resolve_primary_artist(artist_field: str, info_dict: dict) -> str:
    """
    Given the raw artist field (may be comma-separated multi-artist string),
    return a single primary artist name.

    Strategy:
      - Single artist → return as-is.
      - Multiple artists → try to match one against channel/uploader name
        (the channel owner is reliably the primary artist on official channels).
        Falls back to the first entry if no match found.
    """
    artists = [a.strip() for a in artist_field.split(",") if a.strip()]
    if len(artists) <= 1:
        return artist_field.strip()

    uploader = (info_dict.get("uploader") or info_dict.get("channel") or "").strip().lower()
    if uploader:
        for candidate in artists:
            if candidate.lower() == uploader:
                return candidate

    return artists[0]


def _parse_title_separator(title: str) -> tuple:
    """
    Try to split a YouTube title into (artist, track) using common separators.
    Tries separators in order of reliability: // and ⧸⧸ first (YouTube channel
    convention), then en-dash, em-dash, then plain hyphen.
    Returns (artist, track) as strings, or (None, None) if no split found.
    """
    for sep in _TITLE_SEPARATORS:
        if sep in title:
            left, _, right = title.partition(sep)
            left, right = left.strip(), right.strip()
            if left and right:
                return left, right
    return None, None


# ---------------------------------------------------------------------------
# MusicBrainz helpers
# ---------------------------------------------------------------------------

def _mb_search(title: str, user_agent: str) -> Optional[dict]:
    """
    Search MusicBrainz recordings by title.

    Rate-limited to ≤ 1 req/sec via global lock.
    Returns parsed JSON dict or None on any failure.
    """
    global _last_mb_request_time

    with _mb_lock:
        elapsed = time.monotonic() - _last_mb_request_time
        wait = 1.0 - elapsed
        if wait > 0:
            time.sleep(wait)

        try:
            resp = requests.get(
                _MB_API_URL,
                params={"query": title, "limit": 5, "fmt": "json"},
                headers={"User-Agent": user_agent},
                timeout=10,
            )
        except requests.RequestException as exc:
            _last_mb_request_time = time.monotonic()
            logger.warning("renamer: MusicBrainz request failed: %s", exc)
            return None

        _last_mb_request_time = time.monotonic()

    if resp.status_code != 200:
        logger.warning("renamer: MusicBrainz returned HTTP %s", resp.status_code)
        return None

    return resp.json()


def _mb_passes_threshold(recording: dict, yt_title: str) -> bool:
    """
    Return True if:
    - recording score ≥ 85
    - MB primary artist tokens are sufficiently present in the YT title
    - MB track title tokens are sufficiently present in the YT title

    Checks artist and track independently against the YT title to prevent
    false positives from cover recordings whose titles contain the original
    artist's name (e.g. 'Space Song (Beach House)' by Miles McLaughlin).
    """
    score = int(recording.get("score", 0))
    if score < _MB_SCORE_MIN:
        return False

    mb_artist = _mb_primary_artist(recording)
    mb_track = recording.get("title", "")

    return (
        _tokens_in_text(mb_artist, yt_title)
        and _tokens_in_text(mb_track, yt_title)
    )


def _tokens_in_text(needle: str, haystack: str) -> bool:
    """
    Return True if at least _MB_OVERLAP_MIN fraction of needle's word tokens
    appear in haystack. Checks containment (needle ⊆ haystack), not symmetric
    Jaccard, so a short artist name like 'Drake' doesn't get diluted by a
    long title string.
    """
    def tokens(s: str) -> set:
        return set(re.sub(r"[^\w\s]", "", s.lower()).split())

    n_tokens = tokens(needle)
    h_tokens = tokens(haystack)
    if not n_tokens:
        return False
    return len(n_tokens & h_tokens) / len(n_tokens) >= _MB_OVERLAP_MIN


def _mb_primary_artist(recording: dict) -> str:
    """Return the primary artist name from an artist-credit list."""
    credits = recording.get("artist-credit") or []
    if not credits:
        return ""
    first = credits[0]
    if isinstance(first, dict):
        return (first.get("artist") or {}).get("name", "") or first.get("name", "")
    return ""


def _mb_format_name(recording: dict) -> str:
    """Build 'Artist - Track' or 'Artist - Track feat. Artist2, Artist3' from recording."""
    credits = recording.get("artist-credit") or []
    track = sanitize(recording.get("title", "unknown"))

    artist_names = [
        credit["artist"].get("name", "").strip()
        for credit in credits
        if isinstance(credit, dict) and "artist" in credit and credit["artist"].get("name", "").strip()
    ]

    if not artist_names:
        return f"unknown - {track}"

    primary = sanitize(artist_names[0])
    if len(artist_names) == 1:
        return f"{primary} - {track}"

    featured = ", ".join(sanitize(n) for n in artist_names[1:])
    return f"{primary} - {track} feat. {featured}"
