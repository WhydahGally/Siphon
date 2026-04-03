"""
siphon.watcher — Playlist watcher and CLI entry point.

This module is the main entry point for Siphon. It manages the playlist
registry, drives incremental sync via the parallel download engine, and
exposes the `siphon` CLI (add / sync / sync-failed / list / delete / config).

A future UI layer should import from this module to access the same
business logic (add_playlist, sync, list) without going through the CLI.

Global configuration (stored in the DB settings table):
    mb-user-agent              MusicBrainz User-Agent string — set once via
                               `siphon config mb-user-agent "App/1.0 (you@example.com)"`.
                               Used automatically by add and sync for rename lookups.
    max-concurrent-downloads   Number of simultaneous downloads (1–10, default 5).

CLI usage:
    siphon config <key> [<value>]
    siphon add <url> [--download] [--auto-rename] [--format mp3] [--output-dir ./downloads]
    siphon sync [<name>]
    siphon sync-failed [<name>]
    siphon list
    siphon delete <name>
"""
import os
import sys
import argparse
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from yt_dlp import YoutubeDL

from siphon import registry
from siphon.downloader import download, ItemRecord
from siphon.formats import DownloadOptions, VALID_AUDIO_FORMATS, VALID_VIDEO_FORMATS, VALID_RESOLUTIONS, check_ffmpeg
from siphon.renamer import sanitize as sanitize_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".data")
_DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
_ALL_FORMATS = sorted(VALID_AUDIO_FORMATS | VALID_VIDEO_FORMATS)
_DEFAULT_MAX_WORKERS = 5
_MAX_WORKERS_CEILING = 10


# ---------------------------------------------------------------------------
# FailureRecord
# ---------------------------------------------------------------------------

@dataclass
class FailureRecord:
    video_id: str
    title: str
    url: str
    error_message: str


# ---------------------------------------------------------------------------
# Parallel progress renderer
# ---------------------------------------------------------------------------

class ParallelProgressRenderer:
    """
    Fixed multi-slot progress display for concurrent downloads.

    Each worker owns one slot (by index). Workers post status dicts to
    their slot via post(). A background thread redraws the entire block
    (completed items + summary line + active slots) at ~10 Hz using ANSI
    cursor-up so lines update in place.

    Completed items accumulate at the top of the block and remain visible
    after stop() — only the empty slot lines are erased.
    """

    _REFRESH_HZ = 10

    def __init__(self, num_slots: int, playlist_name: str, total: int) -> None:
        self._num_slots = num_slots
        self._playlist_name = playlist_name
        self._total = total
        self._completed = 0
        self._slots: dict = {i: {} for i in range(num_slots)}
        self._completed_lines: List[str] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._prev_lines_drawn: int = 0
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def post(self, slot_index: int, status: dict) -> None:
        with self._lock:
            self._slots[slot_index] = status

    def item_done(self, slot_index: int, success: bool, label: str, error: str = "") -> None:
        with self._lock:
            self._completed += 1
            self._slots[slot_index] = {}
            if success:
                line = f"  \u2713 {label}"
            else:
                line = f"  \u2717 {label}" + (f" \u2014 {error}" if error else "")
            self._completed_lines.append(f"{line:<80}")

    def _render_loop(self) -> None:
        import time
        while not self._stop.is_set():
            self._draw()
            time.sleep(1.0 / self._REFRESH_HZ)
        self._draw()  # final draw

    def _draw(self) -> None:
        with self._lock:
            lines = []
            for cl in self._completed_lines:
                lines.append(cl)
            summary = f"  Syncing '{self._playlist_name}': {self._completed} / {self._total} downloaded"
            lines.append(f"{summary:<80}")
            for i in range(self._num_slots):
                st = self._slots.get(i, {})
                lines.append(self._format_slot(st))

            if self._prev_lines_drawn > 0:
                print(f"\033[{self._prev_lines_drawn}A", end="", flush=False)
            for line in lines:
                print(f"\r{line:<80}", flush=False)
            sys.stdout.flush()
            self._prev_lines_drawn = len(lines)

    @staticmethod
    def _fmt_bytes(n: Optional[int]) -> str:
        if n is None:
            return "?"
        if n < 1024:
            return f"{n} B"
        if n < 1024 ** 2:
            return f"{n / 1024:.1f} KB"
        if n < 1024 ** 3:
            return f"{n / 1024 ** 2:.1f} MB"
        return f"{n / 1024 ** 3:.2f} GB"

    def _format_slot(self, st: dict) -> str:
        if not st:
            return ""
        filename = os.path.basename(st.get("filename", ""))
        status = st.get("status", "")
        if status == "downloading":
            dl = st.get("downloaded_bytes")
            total = st.get("total_bytes")
            speed = st.get("speed")
            eta = st.get("eta")
            parts = [f"  \u2193 {filename}"]
            if total and dl is not None:
                pct = dl / total * 100
                parts.append(f"{pct:5.1f}%  {self._fmt_bytes(dl)} / {self._fmt_bytes(total)}")
            elif dl is not None:
                parts.append(self._fmt_bytes(dl))
            if speed:
                parts.append(f"{self._fmt_bytes(int(speed))}/s")
            if eta is not None:
                parts.append(f"ETA {eta}s")
            return ("  ".join(parts))[:80]
        return ""

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        # Erase just the N empty slot lines at the bottom of the block,
        # leaving completed items and the summary line intact.
        if self._prev_lines_drawn > 0 and self._num_slots > 0:
            print(f"\033[{self._num_slots}A\033[J", end="", flush=True)
        print(flush=True)


def _make_slot_callback(slot_index: int, renderer: ParallelProgressRenderer) -> Callable:
    """Return a progress callback bound to a specific renderer slot."""
    def callback(event: dict) -> None:
        event["slot_index"] = slot_index
        renderer.post(slot_index, event)
    return callback


def _make_cli_progress_callback() -> Callable:
    """
    Single-slot progress callback for standalone download() use (e.g. __main__).
    Not used in the parallel sync path.
    """
    def _fmt_bytes(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        if n < 1024 ** 2:
            return f"{n / 1024:.1f} KB"
        if n < 1024 ** 3:
            return f"{n / 1024 ** 2:.1f} MB"
        return f"{n / 1024 ** 3:.2f} GB"

    def callback(event: dict) -> None:
        status = event.get("status", "")
        filename = os.path.basename(event.get("filename", ""))
        if status == "downloading":
            dl = event.get("downloaded_bytes") or 0
            total = event.get("total_bytes")
            speed = event.get("speed")
            eta = event.get("eta")
            parts = [f"  \u2193 {filename}"]
            if total:
                pct = dl / total * 100
                parts.append(f"{pct:5.1f}%  {_fmt_bytes(dl)} / {_fmt_bytes(total)}")
            else:
                parts.append(_fmt_bytes(dl))
            if speed:
                parts.append(f"{_fmt_bytes(int(speed))}/s")
            if eta is not None:
                parts.append(f"ETA {eta}s")
            line = "  ".join(parts)
            print(f"\r{line:<80}", end="", flush=True)
        elif status == "finished":
            print(f"\r  \u2713 {filename:<77}", flush=True)

    return callback


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_data_dir() -> str:
    return os.path.abspath(_DATA_DIR)


def _resolve_output_dir(output_dir: str) -> str:
    return os.path.abspath(output_dir)


def _build_options(fmt: str, quality: str = "best") -> DownloadOptions:
    if fmt in VALID_AUDIO_FORMATS:
        return DownloadOptions(mode="audio", audio_format=fmt)
    return DownloadOptions(mode="video", quality=quality, video_format=fmt)


def _fetch_playlist_info(url: str) -> dict:
    """Use yt-dlp to fetch playlist metadata without downloading."""
    ydl_opts = {
        "quiet": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return info or {}


def _print_table(rows: list, headers: list, col_widths: list) -> None:
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*[str(v) if v is not None else "never" for v in row]))


# ---------------------------------------------------------------------------
# Parallel download engine
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


def _filter_entries(
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


def _download_one(
    entry: dict,
    playlist_id: str,
    playlist_name: str,
    options: DownloadOptions,
    output_dir: str,
    mb_user_agent: Optional[str],
    slot_index: int,
    renderer: ParallelProgressRenderer,
    auto_rename: bool = False,
) -> Tuple[Optional[ItemRecord], Optional[FailureRecord]]:
    """
    Worker function: download a single video entry.

    On success: writes item to DB, clears any prior failure record, signals renderer.
    On failure: writes failure to DB, signals renderer.

    Returns (ItemRecord, None) on success or (None, FailureRecord) on failure.
    """
    video_id = entry["id"]
    title = entry["title"]
    video_url = entry["url"]

    # Items go into a per-playlist subfolder: <output_dir>/<playlist_name>/
    safe_folder = sanitize_name(playlist_name) or playlist_id
    item_output_dir = os.path.join(output_dir, safe_folder)
    os.makedirs(item_output_dir, exist_ok=True)

    item_result: list = []  # mutable container for on_item_complete callback

    def on_item(record: ItemRecord) -> None:
        item_result.append(record)

    progress_cb = _make_slot_callback(slot_index, renderer)

    try:
        download(
            url=video_url,
            output_dir=item_output_dir,
            options=options,
            progress_callback=progress_cb,
            mb_user_agent=mb_user_agent,
            auto_rename=auto_rename,
            on_item_complete=on_item,
        )
    except Exception as exc:
        err = str(exc)
        logger.warning("Download failed for '%s' (id=%s): %s", title, video_id, err)
        registry.insert_failed(video_id, playlist_id, title, video_url, err)
        renderer.item_done(slot_index, success=False, label=title, error=err)
        return None, FailureRecord(video_id=video_id, title=title, url=video_url, error_message=err)

    record = item_result[0] if item_result else ItemRecord(
        video_id=video_id,
        playlist_id=playlist_id,
        yt_title=title,
        renamed_to=None,
        rename_tier=None,
        uploader=None,
        channel_url=None,
        duration_secs=None,
    )
    registry.insert_item(record, playlist_id)
    registry.clear_failed(video_id, playlist_id)  # no-op if no prior failure
    filename = record.renamed_to or title
    renderer.item_done(slot_index, success=True, label=filename)
    return record, None


def download_parallel(
    entries: List[dict],
    playlist_id: str,
    playlist_name: str,
    options: DownloadOptions,
    output_dir: str,
    mb_user_agent: Optional[str],
    max_workers: int,
    auto_rename: bool = False,
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

    num_slots = min(max_workers, len(entries))
    renderer = ParallelProgressRenderer(num_slots, playlist_name, len(entries))

    successes: List[ItemRecord] = []
    failures: List[FailureRecord] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, entry in enumerate(entries):
            slot = i % num_slots
            fut = executor.submit(
                _download_one,
                entry, playlist_id, playlist_name, options, output_dir,
                mb_user_agent, slot, renderer, auto_rename,
            )
            futures[fut] = entry

        for fut in as_completed(futures):
            try:
                record, failure = fut.result()
            except Exception as exc:
                # Unexpected error not caught in _download_one
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

    renderer.stop()
    return successes, failures


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> int:
    url = args.url
    if "list=" not in url and "/playlist" not in url:
        print("Error: Only playlist URLs are supported by 'siphon add'.", file=sys.stderr)
        print("       A playlist URL must contain 'list=' (e.g. ?list=PLxxx).", file=sys.stderr)
        return 1

    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    print(f"Fetching playlist info from YouTube…")
    info = _fetch_playlist_info(url)
    playlist_id = info.get("id") or info.get("playlist_id")
    playlist_name = info.get("title") or info.get("playlist_title")

    if not playlist_id or not playlist_name:
        print("Error: Could not retrieve playlist ID or title from YouTube.", file=sys.stderr)
        return 1

    try:
        registry.add_playlist(
            playlist_id,
            playlist_name,
            url,
            fmt=args.format,
            quality=args.quality,
            output_dir=_resolve_output_dir(args.output_dir),
            auto_rename=args.rename,
        )
    except ValueError:
        print(
            f"Error: Playlist already registered. Use 'siphon sync' to fetch new items.",
            file=sys.stderr,
        )
        return 1

    print(f"Registered: {playlist_name}  (ID: {playlist_id})")

    if args.download:
        print(f"Syncing '{playlist_name}'…")
        mb_user_agent = registry.get_setting("mb_user_agent")
        max_workers = _get_max_workers()
        _sync_one(
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            url=url,
            fmt=args.format,
            quality=args.quality,
            output_dir=_resolve_output_dir(args.output_dir),
            mb_user_agent=mb_user_agent,
            max_workers=max_workers,
            auto_rename=args.rename,
        )

    return 0


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

def _get_max_workers() -> int:
    """Read max-concurrent-downloads from settings; default to _DEFAULT_MAX_WORKERS."""
    try:
        val = registry.get_setting("max_concurrent_downloads")
        if val is not None:
            return max(1, min(int(val), _MAX_WORKERS_CEILING))
    except Exception:
        pass
    return _DEFAULT_MAX_WORKERS


def _sync_one(
    playlist_id: str,
    playlist_name: str,
    url: str,
    fmt: str,
    quality: str,
    output_dir: str,
    mb_user_agent: Optional[str],
    max_workers: int,
    auto_rename: bool = False,
) -> None:
    options = _build_options(fmt, quality)

    print(f"  Enumerating '{playlist_name}'…")
    entries = enumerate_entries(url)
    if not entries:
        logger.warning("No entries found for playlist '%s' (url=%s)", playlist_name, url)
        registry.update_last_synced(playlist_id)
        print(f"  {playlist_name}: No entries found (playlist may be empty or unavailable).")
        return

    to_download = _filter_entries(entries, playlist_id)
    if not to_download:
        registry.update_last_synced(playlist_id)
        total = registry.count_items(playlist_id)
        print(f"  {playlist_name}: Already up to date. ({total} total)")
        return

    successes, failures = download_parallel(
        entries=to_download,
        playlist_id=playlist_id,
        playlist_name=playlist_name,
        options=options,
        output_dir=output_dir,
        mb_user_agent=mb_user_agent,
        max_workers=max_workers,
        auto_rename=auto_rename,
    )

    registry.update_last_synced(playlist_id)
    total = registry.count_items(playlist_id)
    print(f"  {playlist_name}: {len(successes)} new item(s) added. ({total} total)")

    if failures:
        print(f"\n  Failures ({len(failures)}):")
        for f in failures:
            print(f"    \u2717 {f.title}")
            print(f"      {f.error_message}")


def cmd_sync(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    playlists = registry.list_playlists()
    if not playlists:
        print("No playlists registered. Use 'siphon add <url>' to add one.")
        return 0

    name_filter = getattr(args, "name", None)
    max_workers = _get_max_workers()

    if name_filter:
        row = registry.get_playlist_by_name(name_filter)
        if row is None:
            print(
                f"Error: No playlist named '{name_filter}'. "
                "Run 'siphon list' to see registered playlists.",
                file=sys.stderr,
            )
            return 1
        targets = [row]
    else:
        targets = playlists

    mb_user_agent = registry.get_setting("mb_user_agent")

    for row in targets:
        pid = row["id"]
        pname = row["name"]
        url = row["url"]
        fmt = row["format"]
        quality = row["quality"] or "best"
        output_dir = row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR)
        auto_rename = bool(row["auto_rename"])
        print(f"Syncing '{pname}'\u2026")
        try:
            _sync_one(
                playlist_id=pid,
                playlist_name=pname,
                url=url,
                fmt=fmt,
                quality=quality,
                output_dir=output_dir,
                mb_user_agent=mb_user_agent,
                max_workers=max_workers,
                auto_rename=auto_rename,
            )
        except Exception as exc:
            logger.warning("Sync failed for '%s': %s", pname, exc)
            print(f"  Warning: sync failed for '{pname}': {exc}", file=sys.stderr)
            registry.update_last_synced(pid)

    return 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    playlists = registry.list_playlists()
    if not playlists:
        print("No playlists registered.")
        return 0

    rows = []
    for p in playlists:
        count = registry.count_items(p["id"])
        last_synced = p["last_synced_at"] or "never"
        # Trim ISO timestamp to readable form
        if last_synced != "never" and "T" in last_synced:
            last_synced = last_synced.replace("T", " ")[:19] + " UTC"
        rows.append((p["name"], p["url"], count, last_synced))

    name_w = max(len("NAME"), max(len(r[0]) for r in rows))
    url_w = max(len("URL"), max(len(r[1]) for r in rows))
    url_w = min(url_w, 60)  # cap URL column width
    items_w = max(len("ITEMS"), max(len(str(r[2])) for r in rows))
    sync_w = max(len("LAST SYNCED"), max(len(r[3]) for r in rows))

    _print_table(
        rows=[(r[0], r[1][:url_w], r[2], r[3]) for r in rows],
        headers=["NAME", "URL", "ITEMS", "LAST SYNCED"],
        col_widths=[name_w, url_w, items_w, sync_w],
    )
    return 0


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

def cmd_delete(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    name = args.name
    row = registry.get_playlist_by_name(name)
    if row is None:
        print(
            f"Error: No playlist named '{name}'. "
            "Run 'siphon list' to see registered playlists.",
            file=sys.stderr,
        )
        return 1

    pid = row["id"]
    count = registry.count_items(pid)
    print(f"Playlist:  {name}")
    print(f"Items:     {count}")
    print()
    print("This will remove the playlist and all its records from the registry.")
    print("Your downloaded music files will NOT be deleted.")
    print()
    answer = input("Confirm deletion? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. No changes made.")
        return 0

    registry.delete_playlist(pid)
    print(f"Deleted playlist '{name}' from registry.")
    return 0


# ---------------------------------------------------------------------------
# sync-failed
# ---------------------------------------------------------------------------

def cmd_sync_failed(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    name_filter = getattr(args, "name", None)
    max_workers = _get_max_workers()
    mb_user_agent = registry.get_setting("mb_user_agent")

    if name_filter:
        row = registry.get_playlist_by_name(name_filter)
        if row is None:
            print(
                f"Error: No playlist named '{name_filter}'. "
                "Run 'siphon list' to see registered playlists.",
                file=sys.stderr,
            )
            return 1
        targets = [row]
    else:
        targets = registry.list_playlists()

    any_failures = False
    for row in targets:
        pid = row["id"]
        pname = row["name"]
        failures = registry.get_failed(pid)
        if not failures:
            continue
        any_failures = True
        print(f"Retrying {len(failures)} failure(s) for '{pname}'…")
        options = _build_options(row["format"], row["quality"] or "best")
        output_dir = row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR)
        auto_rename = bool(row["auto_rename"])

        entries = [
            {"id": f["video_id"], "url": f["url"], "title": f["yt_title"]}
            for f in failures
        ]
        successes, new_failures = download_parallel(
            entries=entries,
            playlist_id=pid,
            playlist_name=pname,
            options=options,
            output_dir=output_dir,
            mb_user_agent=mb_user_agent,
            max_workers=max_workers,
            auto_rename=auto_rename,
        )
        print(f"  {pname}: {len(successes)} recovered, {len(new_failures)} still failing.")
        if new_failures:
            for f in new_failures:
                print(f"    \u2717 {f.title}: {f.error_message}")

    if name_filter and not any_failures:
        print(f"No failures recorded for '{name_filter}'.")
    elif not any_failures:
        print("No failures recorded.")

    return 0


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

_KNOWN_KEYS = {
    "mb-user-agent": (
        "mb_user_agent",
        "MusicBrainz User-Agent string (e.g. 'Siphon/1.0 (you@example.com)'). "
        "Required for MusicBrainz lookups in the rename chain.",
    ),
    "log-level": (
        "log_level",
        "Logging verbosity for the siphon logger. One of: DEBUG, INFO, WARNING, ERROR. "
        "Default: INFO.",
    ),
    "max-concurrent-downloads": (
        "max_concurrent_downloads",
        f"Maximum simultaneous downloads (1\u201310). Default: {_DEFAULT_MAX_WORKERS}.",
    ),
}

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}


def cmd_config(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    key_arg = args.key
    if key_arg not in _KNOWN_KEYS:
        known = ", ".join(_KNOWN_KEYS)
        print(f"Error: Unknown config key '{key_arg}'. Known keys: {known}", file=sys.stderr)
        return 1

    db_key, description = _KNOWN_KEYS[key_arg]

    if args.value is None:
        # Read mode
        val = registry.get_setting(db_key)
        if val is None:
            print(f"{key_arg}: (not set)")
        else:
            print(f"{key_arg}: {val}")
        return 0

    # Write mode — validate log-level and max-concurrent-downloads before persisting.
    if key_arg == "log-level" and args.value.upper() not in _VALID_LOG_LEVELS:
        print(
            f"Error: Invalid log-level '{args.value}'. "
            f"Valid values: {', '.join(sorted(_VALID_LOG_LEVELS))}",
            file=sys.stderr,
        )
        return 1
    if key_arg == "max-concurrent-downloads":
        try:
            int_val = int(args.value)
        except ValueError:
            print(
                f"Error: max-concurrent-downloads must be an integer, got '{args.value}'.",
                file=sys.stderr,
            )
            return 1
        if not (1 <= int_val <= _MAX_WORKERS_CEILING):
            print(
                f"Error: max-concurrent-downloads must be between 1 and {_MAX_WORKERS_CEILING}.",
                file=sys.stderr,
            )
            return 1
    value = args.value.upper() if key_arg == "log-level" else args.value
    registry.set_setting(db_key, value)
    print(f"Set {key_arg}.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # Apply log-level from DB if already set; fall back to INFO on a fresh install
    # or before the DB has been initialised by the actual command.
    try:
        stored_level = registry.get_setting("log_level") or "INFO"
    except RuntimeError:
        stored_level = "INFO"
    logging.getLogger("siphon").setLevel(getattr(logging, stored_level, logging.INFO))

    parser = argparse.ArgumentParser(
        prog="siphon",
        description="Siphon — manage and sync local copies of YouTube playlists.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # -- add --
    p_add = sub.add_parser("add", help="Register a YouTube playlist.")
    p_add.add_argument("url", help="YouTube playlist URL.")
    p_add.add_argument("--download", action="store_true", help="Download all items immediately after registering.")
    p_add.add_argument("--format", default="mp3", choices=_ALL_FORMATS, help="Output format (default: mp3).")
    p_add.add_argument("--quality", default="best", choices=sorted(VALID_RESOLUTIONS), help="Video quality: best, 2160, 1080, 720, 480, 360 (default: best). Only applies to video formats.")
    p_add.add_argument("--output-dir", default=_DEFAULT_OUTPUT_DIR, help="Root directory for downloads.")
    p_add.add_argument("--auto-rename", dest="rename", action="store_true", default=False, help="Enable auto-rename for this playlist: renames files to 'Artist - Track' using the rename chain (default: disabled).")

    # -- sync --
    p_sync = sub.add_parser("sync", help="Download new items for registered playlists.")
    p_sync.add_argument("name", nargs="?", default=None, help="Playlist name to sync (default: all).")

    # -- sync-failed --
    p_sf = sub.add_parser("sync-failed", help="Retry failed downloads for a playlist (or all).")
    p_sf.add_argument("name", nargs="?", default=None, help="Playlist name to retry (default: all).")

    # -- list --
    sub.add_parser("list", help="Show all registered playlists.")

    # -- delete --
    p_del = sub.add_parser("delete", help="Remove a playlist from the registry.")
    p_del.add_argument("name", help="Name of the playlist to delete.")

    # -- config --
    p_cfg = sub.add_parser("config", help="Get or set a global configuration value.")
    p_cfg.add_argument("key", choices=list(_KNOWN_KEYS), help="Config key to read or write.")
    p_cfg.add_argument("value", nargs="?", default=None, help="Value to set. Omit to read the current value.")

    args = parser.parse_args()

    dispatch = {
        "add": cmd_add,
        "sync": cmd_sync,
        "sync-failed": cmd_sync_failed,
        "list": cmd_list,
        "delete": cmd_delete,
        "config": cmd_config,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
