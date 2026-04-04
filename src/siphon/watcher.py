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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Optional, Tuple

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


def _download_worker(
    entry: dict,
    playlist_id: str,
    playlist_name: str,
    options: DownloadOptions,
    output_dir: str,
    mb_user_agent: Optional[str],
    auto_rename: bool = False,
) -> Tuple[Optional[ItemRecord], Optional[FailureRecord]]:
    """
    Worker function: download a single video entry.

    On success: writes item to DB, clears any prior failure record, logs result.
    On failure: writes failure to DB, logs error.

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

    start = time.monotonic()

    try:
        download(
            url=video_url,
            output_dir=item_output_dir,
            options=options,
            progress_callback=None,
            mb_user_agent=mb_user_agent,
            auto_rename=auto_rename,
            on_item_complete=on_item,
        )
    except Exception as exc:
        err = str(exc)
        registry.insert_failed(video_id, playlist_id, title, video_url, err)
        logger.warning("  \u2717 %s \u2014 %s", title, err)
        return None, FailureRecord(video_id=video_id, title=title, url=video_url, error_message=err)

    elapsed = time.monotonic() - start
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

    # Determine file size from disk.
    ext = f".{options.audio_format}" if options.mode == "audio" else f".{options.video_format}"
    candidate_path = os.path.join(item_output_dir, f"{filename}{ext}")
    size_str = _fmt_size(candidate_path) if os.path.isfile(candidate_path) else "?"

    logger.info("  \u2713 %s  [%s \u00b7 %ds]", filename, size_str, int(elapsed))
    if auto_rename and record.rename_tier is not None:
        logger.info('    Renamed: "%s" \u2192 "%s"  [%s]', record.yt_title, record.renamed_to, record.rename_tier)

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

    successes: List[ItemRecord] = []
    failures: List[FailureRecord] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, entry in enumerate(entries):
            fut = executor.submit(
                _download_worker,
                entry, playlist_id, playlist_name, options, output_dir,
                mb_user_agent, auto_rename,
            )
            futures[fut] = entry

        for fut in as_completed(futures):
            try:
                record, failure = fut.result()
            except Exception as exc:
                # Unexpected error not caught in _download_worker
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


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def cmd_add(args: argparse.Namespace) -> int:
    url = args.url
    if "list=" not in url and "/playlist" not in url:
        logger.error("Only playlist URLs are supported by 'siphon add'. A playlist URL must contain 'list=' (e.g. ?list=PLxxx).")
        return 1

    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    logger.info("Fetching playlist info from YouTube…")
    info = _fetch_playlist_info(url)
    playlist_id = info.get("id") or info.get("playlist_id")
    playlist_name = info.get("title") or info.get("playlist_title")

    if not playlist_id or not playlist_name:
        logger.error("Could not retrieve playlist ID or title from YouTube.")
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
        logger.error("Playlist already registered. Use 'siphon sync' to fetch new items.")
        return 1

    logger.info("Registered: %s  (ID: %s)", playlist_name, playlist_id)

    if args.download:
        logger.info("Syncing '%s'…", playlist_name)
        mb_user_agent = registry.get_setting("mb_user_agent")
        max_workers = _get_max_workers()
        _sync_parallel(
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


def _sync_parallel(
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

    logger.info("Enumerating '%s'…", playlist_name)
    entries = enumerate_entries(url)
    if not entries:
        logger.warning("No entries found for playlist '%s' (url=%s)", playlist_name, url)
        registry.update_last_synced(playlist_id)
        return

    to_download = _filter_entries(entries, playlist_id)
    if not to_download:
        registry.update_last_synced(playlist_id)
        total = registry.count_items(playlist_id)
        logger.info("'%s': Already up to date. (%d total)", playlist_name, total)
        return

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
    )

    registry.update_last_synced(playlist_id)
    total = registry.count_items(playlist_id)
    logger.info("'%s': %d new item(s) added. (%d total)", playlist_name, len(successes), total)

    if failures:
        logger.info("Failures (%d):", len(failures))
        for f in failures:
            logger.info("  \u2717 %s", f.title)
            logger.info("    %s", f.error_message)


def cmd_sync(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    playlists = registry.list_playlists()
    if not playlists:
        logger.info("No playlists registered. Use 'siphon add <url>' to add one.")
        return 0

    name_filter = getattr(args, "name", None)
    max_workers = _get_max_workers()

    if name_filter:
        row = registry.get_playlist_by_name(name_filter)
        if row is None:
            logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", name_filter)
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
        logger.info("Syncing '%s'…", pname)
        try:
            _sync_parallel(
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
        logger.info("No playlists registered.")
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
        logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", name)
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
            logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", name_filter)
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
        entries = [
            {"id": f["video_id"], "url": f["url"], "title": f["yt_title"]}
            for f in failures
        ]
        logger.info("Retrying %d failure(s) for '%s':", len(entries), pname)
        for idx, entry in enumerate(entries, 1):
            logger.info("  %d. %s", idx, entry["title"])
        options = _build_options(row["format"], row["quality"] or "best")
        output_dir = row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR)
        auto_rename = bool(row["auto_rename"])

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
        logger.info("'%s': %d recovered, %d still failing.", pname, len(successes), len(new_failures))
        if new_failures:
            for f in new_failures:
                logger.info("  \u2717 %s: %s", f.title, f.error_message)

    if name_filter and not any_failures:
        logger.info("No failures recorded for '%s'.", name_filter)
    elif not any_failures:
        logger.info("No failures recorded.")

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
        logger.error("Unknown config key '%s'. Known keys: %s", key_arg, known)
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
        logger.error(
            "Invalid log-level '%s'. Valid values: %s",
            args.value, ", ".join(sorted(_VALID_LOG_LEVELS)),
        )
        return 1
    if key_arg == "max-concurrent-downloads":
        try:
            int_val = int(args.value)
        except ValueError:
            logger.error("max-concurrent-downloads must be an integer, got '%s'.", args.value)
            return 1
        if not (1 <= int_val <= _MAX_WORKERS_CEILING):
            logger.error("max-concurrent-downloads must be between 1 and %d.", _MAX_WORKERS_CEILING)
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
