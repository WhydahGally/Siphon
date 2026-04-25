import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, List, Optional, Tuple

from yt_dlp import YoutubeDL
from yt_dlp.postprocessor import PostProcessor

from siphon.formats import (
    DownloadOptions,
    build_audio_postprocessors,
    build_options,
    build_video_format_selector,
    check_ffmpeg,
)
from siphon.models import FailureRecord, ItemRecord
from siphon.progress import make_progress_event
from siphon import registry
from siphon import renamer

logger = logging.getLogger(__name__)


def download(
    url: str,
    output_dir: str,
    options: DownloadOptions,
    progress_callback: Optional[Callable[[dict], None]] = None,
    mb_user_agent: Optional[str] = None,
    auto_rename: bool = False,
    on_item_complete: Optional[Callable[[ItemRecord], None]] = None,
    noise_patterns: Optional[list] = None,
) -> None:
    """Download a playlist or single video from any yt-dlp-supported platform.

    Args:
        url:               URL of a playlist or video (any yt-dlp-supported platform).
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
                           using the three-tier rename chain. If False, a passthrough
                           rename is applied to ensure DB and disk filenames agree.
        on_item_complete:  Optional callable invoked with an ItemRecord after each
                           item has been fully downloaded and renamed. Errors in the
                           callback are caught and logged — they will not abort the
                           download.
        noise_patterns:    Optional list of inner regex pattern strings passed to
                           strip_noise(). When None, the built-in defaults are used.

    Raises:
        RuntimeError: If mp3 transcoding or mp4/mkv remuxing is requested but ffmpeg
                      is not found on PATH.
        ValueError:   If options contain unsupported values (raised by DownloadOptions).

    Example::

        # Download a playlist as 1080p MP4 files
        download(
            url="https://www.example.com/playlist?list=PLAYLIST_ID",
            output_dir="./downloads",
            options=DownloadOptions(mode="video", quality="1080", video_format="mp4"),
        )

        # Download a playlist as MP3 audio
        download(
            url="https://www.example.com/playlist?list=PLAYLIST_ID",
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

    # Determine whether this is a playlist or a single video by asking yt-dlp.
    # We use extract_flat=True for a lightweight metadata-only pre-flight; no
    # format resolution or download is triggered. _type of "playlist" or "channel"
    # means grouped content; anything else (including absent _type) is single video.
    _preflight_opts = {"extract_flat": True, "quiet": True, "skip_download": True}
    with YoutubeDL(_preflight_opts) as _ydl:
        _info = _ydl.extract_info(url, download=False) or {}
    is_playlist = _info.get("_type") in ("playlist", "channel")

    if is_playlist:
        # Playlist: group files under a playlist-named subfolder.
        output_template = os.path.join(output_dir, "%(playlist_title)s", "%(title)s.%(ext)s")
        logger.debug("URL identified as playlist (_type=%s). Output template: %s", _info.get("_type"), output_template)
    else:
        # Single video: place directly in output_dir.
        output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
        logger.debug("URL identified as single video (_type=%s). Output template: %s", _info.get("_type"), output_template)

    # Build the yt-dlp options dict.
    ydl_opts = _build_ydl_opts(options, output_template, progress_callback, mb_user_agent)

    logger.info(
        "Starting download: %s (mode=%s)",
        url,
        options.mode,
    )

    with YoutubeDL(ydl_opts) as ydl:
        ydl.add_post_processor(
            _RenamePostProcessor(
                mb_user_agent,
                on_item_complete=on_item_complete,
                noise_patterns=noise_patterns,
                auto_rename=auto_rename,
            ),
            when="after_move",
        )
        ydl.download([url])

    logger.info("Download complete: %s", url)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_ydl_opts(
    options: DownloadOptions,
    output_template: str,
    progress_callback: Optional[Callable[[dict], None]],
    mb_user_agent: Optional[str] = None,
) -> dict:
    # Thread-safety note: this function and the YoutubeDL instance it feeds
    # are stateless with respect to module-level globals — each call creates
    # a fresh dict and a fresh YoutubeDL instance (in download()).
    # It is safe to call download() concurrently from multiple threads.
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
        ydl_opts["writethumbnail"] = True
        ydl_opts["postprocessors"] = build_audio_postprocessors(options.audio_format)
        logger.debug("Audio format: %s | postprocessors: %s", options.audio_format, ydl_opts["postprocessors"])

    logger.debug("Postprocessor chain: %s", ydl_opts.get('postprocessors', []))
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
        noise_patterns: Optional[list] = None,
        auto_rename: bool = False,
    ) -> None:
        super().__init__()
        self._mb_user_agent = mb_user_agent
        self._on_item_complete = on_item_complete
        self._noise_patterns = noise_patterns
        self._auto_rename = auto_rename
        if auto_rename and not mb_user_agent:
            logger.debug("renamer: MusicBrainz lookup skipped for this session: --mb-user-agent not configured")

    def run(self, info: dict) -> tuple:
        result: Optional[renamer.RenameResult] = None
        try:
            if self._auto_rename:
                result = renamer.rename_file(info, self._mb_user_agent, noise_patterns=self._noise_patterns)
            else:
                result = renamer.passthrough_rename(info)
        except Exception as exc:
            filepath = info.get("filepath") or info.get("filename", "")
            logger.warning("renamer: rename raised an error for %s: %s", filepath, exc)

        if result:
            renamer.embed_metadata(result.new_path, result.original_title, result.final_name)

        if self._on_item_complete is not None:
            try:
                record = ItemRecord(
                    video_id=info.get("id") or "",
                    playlist_id=info.get("playlist_id"),
                    title=info.get("title") or "",
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


# ---------------------------------------------------------------------------
# Playlist enumeration & filtering
# ---------------------------------------------------------------------------

def enumerate_entries(url: str) -> List[dict]:
    """
    Enumerate all entries in a playlist using extract_flat (no download).
    Returns a list of entry dicts, each with at least 'id', 'url', 'title'.
    """
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        logger.warning("enumerate_entries: no info returned for url=%s", url)
        return []

    entries = info.get("entries") or []
    result = []
    for e in entries:
        if not e:
            continue
        video_id = e.get("id")
        video_url = e.get("url") or e.get("webpage_url")
        if video_id and video_url:
            result.append({
                "id": video_id,
                "url": video_url,
                "title": e.get("title") or video_id,
            })
    logger.debug("enumerate_entries: found %d entries for url=%s", len(result), url)
    return result


def filter_entries(
    entries: List[dict],
    playlist_id: str,
) -> List[dict]:
    """
    Filter entries for dispatch:
    - Skip if already in items table
    - Skip if in ignored_items
    - Skip (with WARNING) if in failed_downloads with attempt_count >= 3
    Returns the list of entries to download.
    """
    downloaded = registry.get_downloaded_ids(playlist_id)
    to_dispatch = []
    for entry in entries:
        vid = entry["id"]
        if vid in downloaded:
            continue
        if registry.is_ignored(vid, playlist_id):
            continue
        attempt_count = registry.get_failed_attempt_count(vid, playlist_id)
        if attempt_count >= 3:
            logger.warning(
                "Skipping '%s' (id=%s): failed %d times — use 'siphon sync-failed' to retry manually.",
                entry["title"], vid, attempt_count,
            )
            continue
        to_dispatch.append(entry)
    return to_dispatch


def _fmt_size(path: str) -> str:
    """Return a human-readable file size string, or '?' if the file cannot be read."""
    try:
        n = os.path.getsize(path)
    except OSError:
        return "?"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.2f} GB"


# ---------------------------------------------------------------------------
# Single-item download worker
# ---------------------------------------------------------------------------

def download_worker(
    entry: dict,
    playlist_id: Optional[str],
    playlist_name: Optional[str],
    options: DownloadOptions,
    output_dir: str,
    mb_user_agent: Optional[str],
    auto_rename: bool = False,
    noise_patterns: Optional[list] = None,
    on_progress: Optional[Any] = None,
) -> Tuple[Optional[ItemRecord], Optional[FailureRecord]]:
    """
    Worker function: download a single video entry.

    On success: writes item to DB (if playlist_id set), clears any prior failure
    record, logs result.
    On failure: writes failure to DB (if playlist_id set), logs error.

    Returns (ItemRecord, None) on success or (None, FailureRecord) on failure.
    """
    video_id = entry["id"]
    title = entry["title"]
    video_url = entry["url"]
    logger.debug("Syncing item: %s (%s)", video_id, title)

    # Single-video jobs (playlist_id=None) go directly into output_dir.
    # Playlist items go into a per-playlist subfolder: <output_dir>/<playlist_name>/
    if playlist_id is None:
        item_output_dir = output_dir
    else:
        folder_key = playlist_name or playlist_id or video_id
        safe_folder = renamer.sanitize(folder_key) or video_id
        item_output_dir = os.path.join(output_dir, safe_folder)
    os.makedirs(item_output_dir, exist_ok=True)

    item_result: list = []  # mutable container for on_item_complete callback

    def on_item(record: ItemRecord) -> None:
        item_result.append(record)

    # Track whether yt-dlp actually finished downloading a file.
    # yt-dlp uses ignoreerrors=True, so unavailable/private/deleted videos are
    # silently skipped — no exception is raised, but no progress hook fires either.
    _file_downloaded: list = []

    def _track_progress(event: dict) -> None:
        if event.get("status") == "finished":
            _file_downloaded.append(True)
        elif event.get("status") == "downloading" and on_progress is not None:
            on_progress(event)

    start = time.monotonic()

    try:
        download(
            url=video_url,
            output_dir=item_output_dir,
            options=options,
            progress_callback=_track_progress,
            mb_user_agent=mb_user_agent,
            auto_rename=auto_rename,
            on_item_complete=on_item,
            noise_patterns=noise_patterns,
        )
    except Exception as exc:
        err = str(exc)
        if playlist_id is not None:
            registry.insert_failed(video_id, playlist_id, title, video_url, err)
        logger.warning("  \u2717 %s \u2014 %s", title, err)
        return None, FailureRecord(video_id=video_id, title=title, url=video_url, error_message=err)

    # If no file was downloaded, yt-dlp silently skipped this entry (unavailable,
    # private, deleted, or region-blocked).  Treat it as a failure so the UI
    # shows a red row and Retry button instead of a false green check mark.
    if not _file_downloaded:
        err = "Video unavailable, private, or deleted"
        if playlist_id is not None:
            registry.insert_failed(video_id, playlist_id, title, video_url, err)
        logger.warning("  \u2717 %s \u2014 %s", title, err)
        return None, FailureRecord(video_id=video_id, title=title, url=video_url, error_message=err)

    elapsed = time.monotonic() - start
    record = item_result[0] if item_result else ItemRecord(
        video_id=video_id,
        playlist_id=playlist_id,
        title=title,
        renamed_to=None,
        rename_tier=None,
        uploader=None,
        channel_url=None,
        duration_secs=None,
    )
    if playlist_id is not None:
        registry.insert_item(record, playlist_id)
        registry.clear_failed(video_id, playlist_id)  # no-op if no prior failure

    filename = record.renamed_to or title

    # Determine file size from disk.
    ext = f".{options.audio_format}" if options.mode == "audio" else f".{options.video_format}"
    candidate_path = os.path.join(item_output_dir, f"{filename}{ext}")
    size_str = _fmt_size(candidate_path) if os.path.isfile(candidate_path) else "?"

    logger.info("  \u2713 %s  [%s \u00b7 %ds]", filename, size_str, int(elapsed))
    if record.rename_tier is not None and record.rename_tier != "title":
        logger.info('    Renamed: "%s" \u2192 "%s"  [%s]', record.title, record.renamed_to, record.rename_tier)

    return record, None


# ---------------------------------------------------------------------------
# Parallel download orchestration
# ---------------------------------------------------------------------------

def download_parallel(
    entries: List[dict],
    playlist_id: str,
    playlist_name: str,
    options: DownloadOptions,
    output_dir: str,
    mb_user_agent: Optional[str],
    max_workers: int,
    auto_rename: bool = False,
    noise_patterns: Optional[list] = None,
) -> Tuple[List[ItemRecord], List[FailureRecord]]:
    """
    Download entries concurrently using a thread pool.

    Returns (successes, failures).
    """
    if not entries:
        return [], []

    # Guard ffmpeg before dispatching threads.
    ffmpeg_needed = (
        (options.mode == "audio" and options.audio_format == "mp3")
        or (options.mode == "video" and options.video_format in {"mp4", "mkv"})
    )
    if ffmpeg_needed and not check_ffmpeg():
        raise RuntimeError(
            "ffmpeg was not found on PATH. "
            "Install it with: brew install ffmpeg  (macOS) or  apt install ffmpeg  (Linux)."
        )

    successes: List[ItemRecord] = []
    failures: List[FailureRecord] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, entry in enumerate(entries):
            fut = executor.submit(
                download_worker,
                entry, playlist_id, playlist_name, options, output_dir,
                mb_user_agent, auto_rename, noise_patterns,
            )
            futures[fut] = entry

        for fut in as_completed(futures):
            try:
                record, failure = fut.result()
            except Exception as exc:
                # Unexpected error not caught in download_worker
                entry = futures[fut]
                failure = FailureRecord(
                    video_id=entry["id"],
                    title=entry["title"],
                    url=entry["url"],
                    error_message=str(exc),
                )
                registry.insert_failed(failure.video_id, playlist_id, failure.title, failure.url, failure.error_message)
                record = None

            if record is not None:
                successes.append(record)
            if failure is not None:
                failures.append(failure)

    return successes, failures


def run_download_job(
    job_id: str,
    entries: List[dict],
    playlist_id: Optional[str],
    playlist_name: Optional[str],
    options: DownloadOptions,
    output_dir: str,
    mb_user_agent: Optional[str],
    max_workers: int,
    job_store,
    auto_rename: bool = False,
    noise_patterns: Optional[list] = None,
) -> None:
    """
    Background thread: drives per-item state transitions and downloads.

    Wraps download_worker to update job state (pending→downloading→done/failed)
    in the JobStore, which fans out SSE events to browser subscribers.
    """
    if not entries:
        if job_store is not None:
            job_store.notify_terminal(job_id)
        return

    # Guard ffmpeg before dispatching threads.
    ffmpeg_needed = (
        (options.mode == "audio" and options.audio_format == "mp3")
        or (options.mode == "video" and options.video_format in {"mp4", "mkv"})
    )
    if ffmpeg_needed and not check_ffmpeg():
        for entry in entries:
            if job_store is not None:
                job_store.update_item_state(
                    job_id, entry["id"], "failed",
                    error="ffmpeg not found on PATH — install it to enable this format.",
                )
        if job_store is not None:
            job_store.notify_terminal(job_id)
        return

    def run_item(entry: dict) -> Tuple[Optional[ItemRecord], Optional[FailureRecord]]:
        # Check cancel flag before starting; skip without downloading if cancelled.
        if job_store is not None:
            job = job_store.get_job(job_id)
            if job is not None and job.cancelled:
                return None, None
            job_store.update_item_state(job_id, entry["id"], "downloading")
        def _on_progress(event: dict) -> None:
            if job_store is not None:
                job_store.publish_progress(job_id, {"speed": event.get("speed")})

        record, failure = download_worker(
            entry=entry,
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            options=options,
            output_dir=output_dir,
            mb_user_agent=mb_user_agent,
            auto_rename=auto_rename,
            noise_patterns=noise_patterns,
            on_progress=_on_progress,
        )
        if failure is not None:
            if job_store is not None:
                job_store.update_item_state(
                    job_id, entry["id"], "failed", error=failure.error_message,
                )
        else:
            renamed_to = record.renamed_to if record else None
            rename_tier = record.rename_tier if record else None
            if job_store is not None:
                job_store.update_item_state(
                    job_id, entry["id"], "done", renamed_to=renamed_to, rename_tier=rename_tier,
                )
        return record, failure

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_item, entry): entry for entry in entries}
        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as exc:
                entry = futures[fut]
                if job_store is not None:
                    job_store.update_item_state(job_id, entry["id"], "failed", error=str(exc))

    if playlist_id is not None:
        registry.update_last_synced(playlist_id)

    if job_store is not None:
        job_store.notify_terminal(job_id)


def sync_parallel(
    playlist_id: str,
    playlist_name: str,
    url: str,
    fmt: str,
    quality: str,
    output_dir: str,
    mb_user_agent: Optional[str],
    max_workers: int,
    auto_rename: bool = False,
    noise_patterns: Optional[list] = None,
    on_sync_info: Optional[Callable] = None,
    on_sync_done: Optional[Callable] = None,
) -> None:
    try:
        options = build_options(fmt, quality)

        logger.info("Enumerating '%s'…", playlist_name)
        entries = enumerate_entries(url)
        if not entries:
            logger.warning("No entries found for playlist '%s' (url=%s)", playlist_name, url)
            registry.update_last_synced(playlist_id)
            if on_sync_info:
                on_sync_info(playlist_id, 0)
            return

        to_download = filter_entries(entries, playlist_id)
        if not to_download:
            registry.update_last_synced(playlist_id)
            total = registry.count_items(playlist_id)
            logger.info("'%s': Already up to date. (%d total)", playlist_name, total)
            if on_sync_info:
                on_sync_info(playlist_id, 0)
            return

        if on_sync_info:
            on_sync_info(playlist_id, len(to_download))
        logger.info("%d new item(s) to download:", len(to_download))
        for idx, entry in enumerate(to_download, 1):
            logger.info("  %d. %s", idx, entry["title"])

        successes, failures = download_parallel(
            entries=to_download,
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            options=options,
            output_dir=output_dir,
            mb_user_agent=mb_user_agent,
            max_workers=max_workers,
            auto_rename=auto_rename,
            noise_patterns=noise_patterns,
        )

        registry.update_last_synced(playlist_id)
        total = registry.count_items(playlist_id)
        logger.info("'%s': %d new item(s) added. (%d total)", playlist_name, len(successes), total)

        if failures:
            logger.info("Failures (%d):", len(failures))
            for f in failures:
                logger.info("  \u2717 %s", f.title)
                logger.info("    %s", f.error_message)
    finally:
        if on_sync_done:
            on_sync_done(playlist_id)


def run_sync_failed_for_playlist(
    row,
    max_workers: int,
    default_output_dir: str,
) -> None:
    """Run sync-failed logic for a single playlist row (called in a thread)."""
    pid = row["id"]
    pname = row["name"]
    failures = registry.get_failed(pid)
    if not failures:
        logger.info("No failures recorded for '%s'.", pname)
        return
    entries = [{"id": f["video_id"], "url": f["url"], "title": f["title"]} for f in failures]
    options = build_options(row["format"], row["quality"] or "best")
    output_dir = row["output_dir"] or os.path.abspath(default_output_dir)
    successes, new_failures = download_parallel(
        entries=entries,
        playlist_id=pid,
        playlist_name=pname,
        options=options,
        output_dir=output_dir,
        mb_user_agent=registry.get_setting("mb_user_agent"),
        max_workers=max_workers,
        auto_rename=bool(row["auto_rename"]),
        noise_patterns=registry.get_noise_patterns(),
    )
    logger.info("'%s': %d recovered, %d still failing.", pname, len(successes), len(new_failures))



