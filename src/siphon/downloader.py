import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor import PostProcessor

from siphon.formats import (
    DownloadOptions,
    build_audio_postprocessors,
    build_video_format_selector,
    check_ffmpeg,
)
from siphon.progress import make_progress_event
from siphon import renamer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class ItemRecord:
    video_id: str
    playlist_id: Optional[str]
    yt_title: str
    renamed_to: Optional[str]       # final filename stem, no extension
    rename_tier: Optional[str]      # tier from RenameResult
    uploader: Optional[str]
    channel_url: Optional[str]
    duration_secs: Optional[int]


def download(
    url: str,
    output_dir: str,
    options: DownloadOptions,
    progress_callback: Optional[Callable[[dict], None]] = None,
    mb_user_agent: Optional[str] = None,
    auto_rename: bool = False,
    on_item_complete: Optional[Callable[[ItemRecord], None]] = None,
) -> None:
    """
    Download a YouTube playlist or single video.

    Args:
        url:               YouTube playlist or video URL.
        output_dir:        Root directory for downloaded files.
        options:           Format and quality options (DownloadOptions).
                           For video mode, set `quality` (best/2160/1080/720/480/360)
                           and `video_format` (mp4/mkv/webm, default mp4).
                           For audio mode, set `audio_format` (mp3/opus).
        progress_callback: Optional callable invoked with a ProgressEvent dict
                           on each yt-dlp progress tick. Errors in the callback
                           are caught and logged — they will not abort the download.
        mb_user_agent:     Optional User-Agent string for MusicBrainz API lookups
                           (e.g. 'Siphon/1.0 (you@example.com)'). When omitted,
                           the MusicBrainz tier of the rename chain is skipped.
        auto_rename:       If True, rename each downloaded file to 'Artist - Track'
                           using the four-tier rename chain. Defaults to False.
        on_item_complete:  Optional callable invoked with an ItemRecord after each
                           item has been fully downloaded and renamed. Errors in the
                           callback are caught and logged — they will not abort the
                           download. Requires auto_rename=True to be effective.

    Raises:
        RuntimeError: If mp3 transcoding or mp4/mkv remuxing is requested but ffmpeg
                      is not found on PATH.
        ValueError:   If options contain unsupported values (raised by DownloadOptions).

    Example::

        # Download a playlist as 1080p MP4 files
        download(
            url="https://www.youtube.com/playlist?list=PLAYLIST_ID",
            output_dir="./downloads",
            options=DownloadOptions(mode="video", quality="1080", video_format="mp4"),
        )

        # Download a playlist as MP3 audio
        download(
            url="https://www.youtube.com/playlist?list=PLAYLIST_ID",
            output_dir="./downloads",
            options=DownloadOptions(mode="audio", audio_format="mp3"),
        )
    """
    # Guard: ffmpeg required for mp3 transcoding or mp4/mkv remuxing.
    ffmpeg_needed = (
        (options.mode == "audio" and options.audio_format == "mp3")
        or (options.mode == "video" and options.video_format in {"mp4", "mkv"})
    )
    if ffmpeg_needed and not check_ffmpeg():
        raise RuntimeError(
            "ffmpeg was not found on the system PATH. "
            "ffmpeg is required for transcoding/remuxing. "
            "Install it with: brew install ffmpeg  (macOS) or  apt install ffmpeg  (Linux)."
        )

    # Determine whether this is a playlist or a single video.
    # yt-dlp handles both with the same API; the output template differs.
    is_playlist = "list=" in url or "/playlist" in url

    if is_playlist:
        # Playlist: group files under a playlist-named subfolder.
        output_template = os.path.join(output_dir, "%(playlist_title)s", "%(title)s.%(ext)s")
        logger.debug("URL identified as playlist. Output template: %s", output_template)
    else:
        # Single video: place directly in output_dir.
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        logger.debug("URL identified as single video. Output template: %s", output_template)

    # Build the yt-dlp options dict.
    ydl_opts = _build_ydl_opts(options, output_template, progress_callback, mb_user_agent)

    logger.debug(
        "Starting download | url=%s | mode=%s | output_dir=%s",
        url,
        options.mode,
        output_dir,
    )

    with YoutubeDL(ydl_opts) as ydl:
        if auto_rename:
            ydl.add_post_processor(
                _RenamePostProcessor(mb_user_agent, on_item_complete=on_item_complete),
                when="after_move",
            )
        ydl.download([url])

    logger.debug("Download session complete for url=%s", url)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_ydl_opts(
    options: DownloadOptions,
    output_template: str,
    progress_callback: Optional[Callable[[dict], None]],
    mb_user_agent: Optional[str] = None,
) -> dict:
    """Assemble the yt-dlp options dict from DownloadOptions."""

    ydl_opts: dict = {
        "outtmpl": output_template,
        # Skip unavailable videos (private, deleted, region-blocked) instead of aborting.
        "ignoreerrors": True,
        # Suppress yt-dlp's own console output — we handle logging ourselves.
        "quiet": True,
        "no_warnings": False,  # Allow yt-dlp warnings to surface through its logger.
        "logger": _YtdlpLogger(),
        "progress_hooks": [_make_hook(options, progress_callback)],
        # YouTube JS challenge solving (signature decryption + n-param throttling).
        # yt-dlp needs two things:
        #   1. A JS runtime to execute the solver — node is standard in all Linux
        #      distros (single apt-get), ideal for containers; deno as local fallback.
        #   2. The challenge solver script itself (EJS) — fetched once from GitHub
        #      and cached by yt-dlp. Without it, the runtime alone cannot solve
        #      the challenges and formats/speed will be degraded.
        "js_runtimes": {"node": {}, "deno": {}},
        "remote_components": ["ejs:github"],
    }

    if options.mode == "video" and options.quality != "best":
        ydl_opts["match_filter"] = _make_quality_check_filter(options)

    if options.mode == "video":
        ydl_opts["format"] = build_video_format_selector(options.quality)
        ydl_opts["merge_output_format"] = options.video_format
        logger.debug("Video format selector: %s | container: %s", ydl_opts["format"], options.video_format)

    elif options.mode == "audio":
        # For audio we always want the best audio-only stream as the source.
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = build_audio_postprocessors(options.audio_format)
        logger.debug("Audio format: %s | postprocessors: %s", options.audio_format, ydl_opts["postprocessors"])

    return ydl_opts


class _RenamePostProcessor(PostProcessor):
    """
    yt-dlp PostProcessor that invokes the renamer after all postprocessors
    (including ffmpeg) have completed and the file has been moved to its final path.
    Registered with when='after_move' so info_dict['filepath'] is the final file.
    """

    def __init__(
        self,
        mb_user_agent: Optional[str],
        on_item_complete: Optional[Callable[[ItemRecord], None]] = None,
    ) -> None:
        super().__init__()
        self._mb_user_agent = mb_user_agent
        self._on_item_complete = on_item_complete
        if not mb_user_agent:
            logger.debug("renamer: MusicBrainz lookup skipped for this session: --mb-user-agent not configured")

    def run(self, info: dict) -> tuple:
        result: Optional[renamer.RenameResult] = None
        try:
            result = renamer.rename_file(info, self._mb_user_agent)
        except Exception as exc:
            filepath = info.get("filepath") or info.get("filename", "")
            logger.warning("renamer.rename_file raised an error for %s: %s", filepath, exc)

        if self._on_item_complete is not None:
            try:
                record = ItemRecord(
                    video_id=info.get("id") or "",
                    playlist_id=info.get("playlist_id"),
                    yt_title=info.get("title") or "",
                    renamed_to=result.final_name if result else None,
                    rename_tier=result.tier if result else None,
                    uploader=info.get("uploader") or info.get("channel"),
                    channel_url=info.get("channel_url") or info.get("uploader_url"),
                    duration_secs=info.get("duration"),
                )
                self._on_item_complete(record)
            except Exception as exc:
                logger.warning("on_item_complete callback raised an error: %s", exc)

        return [], info


def _make_quality_check_filter(options: DownloadOptions) -> Callable[[dict], Optional[str]]:
    """
    Return a yt-dlp match_filter that warns before a download starts if the best
    available video height is lower than the requested quality.
    Always returns None so the download is never blocked.
    """
    requested_height = int(options.quality)

    def match_filter(info_dict: dict, *, incomplete: bool) -> Optional[str]:
        formats = info_dict.get("formats") or []
        available_heights = [
            f.get("height") for f in formats
            if f.get("height") is not None and f.get("vcodec") not in (None, "none")
        ]
        if available_heights:
            best_available = max(available_heights)
            if best_available < requested_height:
                title = info_dict.get("title") or info_dict.get("id", "unknown")
                logger.warning(
                    "Quality fallback for '%s': requested %sp but best available is %sp. "
                    "Downloading at %sp.",
                    title, requested_height, best_available, best_available,
                )
        return None  # always allow the download to proceed

    return match_filter


def _make_hook(options: DownloadOptions, progress_callback: Optional[Callable[[dict], None]]) -> Callable[[dict], None]:
    """
    Return a yt-dlp progress hook that:
    - Maps the raw yt-dlp dict to a normalised ProgressEvent.
    - Warns when the actual downloaded quality differs from the requested quality.
    - Forwards the event to the caller's progress_callback (if provided).
    - Catches and logs any exception raised by the callback.
    """

    def hook(d: dict) -> None:
        event = make_progress_event(d)

        # Forward progress to the caller.
        if progress_callback is not None:
            try:
                progress_callback(event)
            except Exception as exc:
                logger.warning("Progress callback raised an error: %s", exc)

    return hook


class _YtdlpLogger:
    """Routes yt-dlp internal messages to Python's logging module."""

    def debug(self, msg: str) -> None:
        # yt-dlp prefixes info-level messages with "[debug]" in debug mode.
        logger.debug("[yt-dlp] %s", msg)

    def info(self, msg: str) -> None:
        logger.info("[yt-dlp] %s", msg)

    def warning(self, msg: str) -> None:
        logger.warning("[yt-dlp] %s", msg)

    def error(self, msg: str) -> None:
        logger.error("[yt-dlp] %s", msg)



