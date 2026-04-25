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
    final_name: str              # filename stem, no extension
    tier: Optional[str]          # "metadata" | "musicbrainz" | "title" | None (passthrough)
    new_path: str                # absolute path to renamed file on disk

# ---------------------------------------------------------------------------
# MusicBrainz rate-limiting state
# ---------------------------------------------------------------------------

_mb_lock = threading.Lock()
_last_mb_request_time: float = 0.0

_MB_API_URL = "https://musicbrainz.org/ws/2/recording"
_MB_SCORE_MIN = 85

_UNSAFE_CHARS = re.compile(r'[/\\:*?"<>|]')

# Visual-equivalent Unicode replacements for filesystem-unsafe ASCII characters.
# Each maps an unsafe char to a safe lookalike that preserves the title's appearance.
_VISUAL_EQUIVALENT_MAP: dict[str, str] = {
    "/":  "\u29F8",   # ⧸  BIG SOLIDUS
    "\\": "\u29F9",   # ⧹  BIG REVERSE SOLIDUS
    ":":  "\uA789",   # ꞉  MODIFIER LETTER COLON
    "*":  "\uFF0A",   # ＊ FULLWIDTH ASTERISK
    "?":  "\uFF1F",   # ？ FULLWIDTH QUESTION MARK
    '"':  "\uFF02",   # ＂ FULLWIDTH QUOTATION MARK
    "<":  "\uFF1C",   # ＜ FULLWIDTH LESS-THAN SIGN
    ">":  "\uFF1E",   # ＞ FULLWIDTH GREATER-THAN SIGN
    "|":  "\uFF5C",   # ｜ FULLWIDTH VERTICAL LINE
}

# Separators used only for the INFO-level diagnostic log.
_TITLE_SEPARATORS = [' ⧸⧸ ', ' // ', ' – ', ' — ', ' - ']

# Default inner regex patterns for strip_noise().
# These match the content inside ( ) or [ ] at the end of a title.
_DEFAULT_NOISE_PATTERNS = [
    r'official\s*music\s*video',
    r'official\s*video',
    r'official\s*audio',
    r'official\s*lyric\s*video',
    r'lyric\s*video',
    r'lyrics?',
    r'audio(?:\s*only)?',
    r'visuali[sz]er',
    r'visual',
    r'hd',
    r'4k',
    r'1080p',
    r'official',
    r'\d{4}\s*remaster(?:ed)?',
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rename_file(
    info_dict: dict,
    mb_user_agent: Optional[str] = None,
    noise_patterns: Optional[list] = None,
) -> Optional["RenameResult"]:
    """
    Rename the downloaded file to 'Artist - Track.ext'.

    Three-tier resolution chain:
      1.  Embedded metadata    — info_dict['artist'] + info_dict['track'] if both present.
      2.  MusicBrainz         — free-text search if mb_user_agent is configured;
                                validated via phrase-match against title and uploader.
      3.  Title fallback       — noise-stripped, sanitized info_dict['title'].

    Noise stripping is applied before the MB query and to the final name at every tier.
    Returns a RenameResult on success, or None if no filepath was found.
    Non-fatal: OS rename errors are logged and swallowed.
    """
    filepath = info_dict.get("filepath") or info_dict.get("filename")
    if not filepath:
        logger.warning("renamer: no filepath in info_dict, skipping rename")
        return None

    yt_title = (info_dict.get("title") or "").strip()
    uploader = (info_dict.get("uploader") or info_dict.get("channel") or "").strip()

    # Tier 1: Embedded metadata (artist + track fields provided by the platform)
    artist = (info_dict.get("artist") or "").strip()
    track = (info_dict.get("track") or "").strip()
    if artist and track:
        artist = _resolve_primary_artist(artist, info_dict)
        final_name = strip_noise(f"{artist} - {track}", noise_patterns)
        new_path = _do_rename(filepath, final_name)
        logger.debug("renamer: tier 1 resolved via embedded metadata")
        return RenameResult(original_title=yt_title, final_name=final_name, tier="metadata", new_path=new_path)

    # Tier 2: MusicBrainz lookup
    cleaned_title = strip_noise(yt_title, noise_patterns)
    if mb_user_agent:
        if any(sep in cleaned_title for sep in _TITLE_SEPARATORS):
            logger.info("renamer: separator detected in title — using free-text MB query")
        mb_result = _mb_search(cleaned_title, mb_user_agent)
        if mb_result:
            recordings = mb_result.get("recordings") or []
            if recordings and _mb_passes_threshold(recordings[0], cleaned_title, uploader):
                final_name = strip_noise(_mb_format_name(recordings[0]), noise_patterns)
                new_path = _do_rename(filepath, final_name)
                logger.debug("renamer: tier 2 resolved via MusicBrainz")
                return RenameResult(original_title=yt_title, final_name=final_name, tier="musicbrainz", new_path=new_path)
            else:
                logger.debug("renamer: tier 2 result below threshold, falling through")
    else:
        logger.debug("renamer: mb_user_agent not configured, skipping tier 2")

    # Tier 3: Title fallback
    if cleaned_title:
        sep_result = _try_separator_split(cleaned_title)
        if sep_result:
            artist, track = sep_result
            final_name = strip_noise(f"{artist} - {track}", noise_patterns)
        else:
            final_name = strip_noise(safe_replace(cleaned_title), noise_patterns)
    else:
        final_name = "unknown"
    new_path = _do_rename(filepath, final_name)
    logger.debug("renamer: tier 3 fallback to title")
    return RenameResult(original_title=yt_title, final_name=final_name, tier="title", new_path=new_path)


def passthrough_rename(info_dict: dict) -> Optional["RenameResult"]:
    """Rename a downloaded file using the raw YT title with visual-equivalent safe chars.

    No noise stripping, no MusicBrainz, no metadata extraction.
    Used when auto-rename is OFF to ensure DB and disk filenames agree.
    """
    filepath = info_dict.get("filepath") or info_dict.get("filename")
    if not filepath:
        logger.warning("renamer: no filepath in info_dict, skipping passthrough rename")
        return None

    yt_title = (info_dict.get("title") or "").strip()
    final_name = safe_replace(yt_title) if yt_title else "unknown"
    new_path = _do_rename(filepath, final_name)
    logger.debug("renamer: passthrough rename applied")
    return RenameResult(original_title=yt_title, final_name=final_name, tier=None, new_path=new_path)


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


def safe_replace(name: str) -> str:
    """Replace filesystem-unsafe characters with visual-equivalent Unicode lookalikes."""
    for unsafe, safe in _VISUAL_EQUIVALENT_MAP.items():
        name = name.replace(unsafe, safe)
    return name.strip()


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


def strip_noise(title: str, patterns: Optional[list] = None) -> str:
    """
    Strip common YouTube title suffixes such as (Official Video), [Lyric Video], etc.

    Patterns are inner regex strings matched inside ( ) or [ ] at the end of the title.
    - patterns=None  → use built-in defaults (_DEFAULT_NOISE_PATTERNS)
    - patterns=[]    → no stripping (noise filtering disabled)
    Applied iteratively until no further matches are found.
    """
    active = _DEFAULT_NOISE_PATTERNS if patterns is None else patterns
    if not active:
        return title
    inner = "|".join(active)
    noise_re = re.compile(
        r"\s*[\(\[]\s*(?:" + inner + r")\s*[\)\]]\s*$",
        re.IGNORECASE,
    )
    original = title
    prev = None
    while prev != title:
        prev = title
        title = noise_re.sub("", title).strip()
    if title != original:
        logger.debug("Stripped noise: %r → %r", original, title)
    return title


def _try_separator_split(title: str) -> Optional[tuple]:
    """Try to split a title on a known separator into (artist, track).

    Returns (artist, track) if a separator is found, None otherwise.
    Both parts are sanitized to remove any remaining unsafe chars.
    """
    for sep in _TITLE_SEPARATORS:
        if sep in title:
            parts = title.split(sep, 1)
            artist = sanitize(parts[0].strip())
            track = sanitize(parts[1].strip())
            if artist and track:
                return artist, track
    return None


def _normalize(s: str) -> str:
    """Lowercase, replace non-alphanumeric characters with space, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w]", " ", s.lower())).strip()


def _mb_artist_in_title(mb_artist: str, title: str) -> bool:
    """Return True if the normalized MB artist is a contiguous substring of the normalized title."""
    if not mb_artist:
        return False
    return _normalize(mb_artist) in _normalize(title)


def _mb_track_in_title_excl_artist(mb_track: str, mb_artist: str, title: str) -> bool:
    """
    Return True if the normalized MB track is a contiguous substring of the normalized title
    after removing the first occurrence of the normalized artist from the normalized title.
    """
    if not mb_track:
        return False
    norm_title = _normalize(title)
    norm_artist = _normalize(mb_artist)
    if norm_artist:
        norm_title = norm_title.replace(norm_artist, "", 1)
    return _normalize(mb_track) in norm_title


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
            logger.debug("MB rate-limit: waiting %.0fms", wait * 1000)
            time.sleep(wait)

        req_start = time.monotonic()
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
        latency_ms = (_last_mb_request_time - req_start) * 1000

    logger.debug("MB lookup: %r → HTTP %s (%.0fms)", title, resp.status_code, latency_ms)
    if resp.status_code != 200:
        logger.warning("renamer: MusicBrainz returned HTTP %s", resp.status_code)
        return None

    return resp.json()


def _mb_passes_threshold(recording: dict, yt_title: str, uploader: str = "") -> bool:
    """
    Validate a MusicBrainz result against the YouTube title using phrase-match logic.

    Two acceptance paths (both require score ≥ 85):

    BOTH_IN_TITLE:
      normalized(mb_artist) is a contiguous substring of normalized(yt_title)
      AND normalized(mb_track) is a contiguous substring of normalized(yt_title)
          with the artist portion removed first.

    UPLOADER_MATCH:
      normalized(mb_track) is a contiguous substring of normalized(yt_title)
      AND normalized(uploader) == normalized(mb_artist) exactly.

    Returns True if either path passes, False otherwise.
    """
    score = int(recording.get("score", 0))
    if score < _MB_SCORE_MIN:
        return False

    mb_artist = _mb_primary_artist(recording)
    mb_track = recording.get("title", "")

    # BOTH_IN_TITLE path
    if _mb_artist_in_title(mb_artist, yt_title) and _mb_track_in_title_excl_artist(mb_track, mb_artist, yt_title):
        logger.debug("renamer: MB validator BOTH_IN_TITLE accepted")
        return True

    # UPLOADER_MATCH path
    if uploader and _normalize(uploader) == _normalize(mb_artist):
        if _mb_track_in_title_excl_artist(mb_track, mb_artist, yt_title):
            logger.debug("renamer: MB validator UPLOADER_MATCH accepted")
            return True

    return False


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


# ---------------------------------------------------------------------------
# Manual rename helpers
# ---------------------------------------------------------------------------

# All extensions Siphon can produce via yt-dlp postprocessors.
_KNOWN_EXTENSIONS = {"mp3", "opus", "mp4", "mkv", "webm"}


def extract_extension(filename: str) -> tuple:
    """Split a filename into (stem, '.ext').

    Checks against Siphon's known format extensions first, falls back to
    ``os.path.splitext`` for unrecognised extensions.
    """
    for ext in _KNOWN_EXTENSIONS:
        suffix = f".{ext}"
        if filename.endswith(suffix):
            return filename[: -len(suffix)], suffix
    return os.path.splitext(filename)


def resolve_file_path(directory: str, stem: str) -> Optional[str]:
    """Find a file in *directory* whose name starts with *stem* and has a known extension.

    Returns the absolute path if found, ``None`` otherwise.
    """
    for ext in _KNOWN_EXTENSIONS:
        candidate = os.path.join(directory, f"{stem}.{ext}")
        if os.path.isfile(candidate):
            return candidate
    # Fallback: try any file matching stem.* in case of an unexpected extension.
    for entry in os.scandir(directory):
        if entry.is_file():
            name_stem, _ = os.path.splitext(entry.name)
            if name_stem == stem:
                return entry.path
    return None


# ---------------------------------------------------------------------------
# Metadata embedding
# ---------------------------------------------------------------------------

def embed_metadata(filepath: str, original_title: str, final_name: str) -> None:
    """Write the original YT title and resolved name into the file's audio metadata.

    MP3:  ID3 ``TXXX:original_title`` for the raw YT title, ``TIT2`` for the resolved name.
    Opus: Vorbis ``ORIGINAL_TITLE`` for the raw YT title, ``TITLE`` for the resolved name.
    Other formats are silently skipped.
    """
    if not original_title and not final_name:
        return

    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".mp3":
            from mutagen.id3 import ID3, TIT2, TXXX, ID3NoHeaderError
            try:
                tags = ID3(filepath)
            except ID3NoHeaderError:
                tags = ID3()
            if original_title:
                tags.add(TXXX(encoding=3, desc="original_title", text=[original_title]))
            if final_name:
                tags.add(TIT2(encoding=3, text=[final_name]))
            tags.save(filepath)
        elif ext == ".opus":
            from mutagen.oggopus import OggOpus
            audio = OggOpus(filepath)
            if original_title:
                audio["ORIGINAL_TITLE"] = [original_title]
            if final_name:
                audio["TITLE"] = [final_name]
            audio.save()
        else:
            return
        logger.debug("Embedded metadata in %s", os.path.basename(filepath))
    except Exception as exc:
        logger.warning("Failed to embed metadata in %s: %s", filepath, exc)


def update_title_metadata(filepath: str, new_title: str) -> None:
    """Update only the TITLE metadata field in an audio file.

    Used after manual renames to keep metadata in sync with the filename.
    """
    if not new_title:
        return

    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".mp3":
            from mutagen.id3 import ID3, TIT2, ID3NoHeaderError
            try:
                tags = ID3(filepath)
            except ID3NoHeaderError:
                tags = ID3()
            tags.add(TIT2(encoding=3, text=[new_title]))
            tags.save(filepath)
        elif ext == ".opus":
            from mutagen.oggopus import OggOpus
            audio = OggOpus(filepath)
            audio["TITLE"] = [new_title]
            audio.save()
        else:
            return
        logger.debug("Updated TITLE metadata in %s", os.path.basename(filepath))
    except Exception as exc:
        logger.warning("Failed to update TITLE in %s: %s", filepath, exc)
