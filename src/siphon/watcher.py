"""
siphon.watcher — Playlist watcher, scheduler daemon, and CLI entry point.

Architecture:
    `siphon watch` starts a long-running FastAPI daemon on port 8000. All other
    subcommands are thin HTTP clients that talk to the daemon. The daemon owns
    the DB connection and the PlaylistScheduler.

    The daemon is a prerequisite for all subcommands other than `watch` itself.
    If the daemon is not running, commands exit with an error.

Global configuration (stored in the DB settings table):
    mb-user-agent              MusicBrainz User-Agent string — set once via
                               `siphon config mb-user-agent "App/1.0 (you@example.com)"`.
    max-concurrent-downloads   Number of simultaneous downloads (1–10, default 5).
    interval                   Default sync interval in seconds for all watched
                               playlists (default: 86400). Per-playlist overrides
                               take precedence.
    log-level                  Logging verbosity: DEBUG, INFO, WARNING, ERROR.

CLI usage:
    siphon watch
    siphon config <key> [<value>]
    siphon add <url> [--download] [--no-watch] [--interval <secs>]
               [--auto-rename] [--format mp3] [--output-dir ./downloads]
    siphon sync [<name>]
    siphon sync-failed [<name>]
    siphon list
    siphon delete <name>
    siphon config-playlist <name> [<key> [<value>]]
"""
import os
import sys
import argparse
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests as _requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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

def _parse_bool(value: str) -> bool:
    """Argparse type for accepting true/false/1/0 as a boolean."""
    if value.lower() in ("true", "1", "yes"):
        return True
    if value.lower() in ("false", "0", "no"):
        return False
    raise argparse.ArgumentTypeError(f"Expected true/false, got '{value}'.")


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
    body: dict = {
        "url": args.url,
        "format": args.format,
        "quality": args.quality,
        "output_dir": args.output_dir,
        "auto_rename": args.auto_rename,
        "watched": not args.no_watch,
        "download": args.download,
    }
    if args.interval is not None:
        if args.interval <= 0:
            logger.error("--interval must be a positive integer.")
            return 1
        body["check_interval_secs"] = args.interval

    try:
        resp = _requests.post(f"{_DAEMON_URL}/playlists", json=body, timeout=120)
    except _requests.exceptions.ConnectionError:
        print("siphon watch is not running. Start it with 'siphon watch'.", file=sys.stderr)
        return 1

    if resp.status_code == 409:
        logger.error("Playlist already registered. Use 'siphon sync' to fetch new items.")
        return 1
    if resp.status_code == 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        logger.error("%s", detail)
        return 1
    if not resp.ok:
        _daemon_handle_error(resp)
        return 1

    data = resp.json()
    name = data.get("name", "?")
    pid = data.get("id", "?")
    watch_status = "" if body["watched"] else "  (auto-sync disabled)"
    logger.info("Registered: %s  (ID: %s)%s", name, pid, watch_status)
    if args.download:
        logger.info("Download started in background.")
    return 0


# ===========================================================================
# PlaylistScheduler
# ===========================================================================

_DEFAULT_INTERVAL = 86400  # 24 hours


class PlaylistScheduler:
    """
    Manages one threading.Timer per watched playlist.

    Lifecycle: fire → sync → rearm (sequential; no concurrent syncs per playlist).
    Interval is re-read from the DB at each rearm, so config changes take effect
    on the next cycle without any restart.

    Thread-safety: all mutations to _timers and _active_threads are protected
    by _lock.
    """

    def __init__(self) -> None:
        self._timers: Dict[str, threading.Timer] = {}
        self._active_threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Arm timers for all currently watched playlists."""
        playlists = registry.get_watched_playlists()
        for row in playlists:
            self._arm(row["id"], self._resolve_interval(row))
        logger.info("PlaylistScheduler started — %d playlist(s) scheduled.", len(playlists))

    def stop(self) -> None:
        """Cancel all pending timers and wait for any in-progress syncs to complete."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            threads_to_join = list(self._active_threads.values())

        for t in threads_to_join:
            t.join()
        logger.info("PlaylistScheduler stopped.")

    def add_playlist(self, playlist_id: str) -> None:
        """Arm a new timer for a newly registered playlist (no-op if watched=0)."""
        row = registry.get_playlist_by_id(playlist_id)
        if row is None or not row["watched"]:
            return
        interval = self._resolve_interval(row)
        self._arm(playlist_id, interval)
        logger.info(
            "PlaylistScheduler: watching '%s' — next sync in %s.",
            row["name"], self._fmt_interval(interval),
        )

    def remove_playlist(self, playlist_id: str) -> None:
        """Cancel the timer for a playlist being deleted (no-op if not present)."""
        with self._lock:
            timer = self._timers.pop(playlist_id, None)
        if timer is not None:
            timer.cancel()
            logger.debug("PlaylistScheduler: cancelled timer for deleted playlist %s.", playlist_id)

    def reschedule_playlist(self, playlist_id: str) -> None:
        """
        Cancel existing timer and re-arm with the current DB interval.
        If watched=0, cancel only (no re-arm).
        """
        with self._lock:
            old = self._timers.pop(playlist_id, None)
        if old is not None:
            old.cancel()

        row = registry.get_playlist_by_id(playlist_id)
        if row is None or not row["watched"]:
            logger.debug("PlaylistScheduler: playlist %s is unwatched — timer cancelled.", playlist_id)
            return

        interval = self._resolve_interval(row)
        self._arm(playlist_id, interval)
        logger.info(
            "PlaylistScheduler: '%s' rescheduled — next sync in %s.",
            row["name"], self._fmt_interval(interval),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_interval(seconds: int) -> str:
        """Return a human-readable interval string (e.g. '24h', '90m', '45s')."""
        if seconds >= 3600:
            hours = seconds / 3600
            return f"{hours:.4g}h"
        if seconds >= 60:
            minutes = seconds / 60
            return f"{minutes:.4g}m"
        return f"{seconds}s"

    def _resolve_interval(self, row: Any) -> int:
        """Return the effective check interval for a playlist row."""
        if row["check_interval_secs"] is not None:
            return int(row["check_interval_secs"])
        global_val = registry.get_setting("check_interval")
        if global_val is not None:
            try:
                return int(global_val)
            except ValueError:
                pass
        return _DEFAULT_INTERVAL

    def _arm(self, playlist_id: str, interval: int) -> None:
        """Create and start a one-shot timer for playlist_id."""
        timer = threading.Timer(interval, self._fire, args=(playlist_id,))
        timer.daemon = True
        timer.start()
        with self._lock:
            self._timers[playlist_id] = timer

    def _fire(self, playlist_id: str) -> None:
        """Called when a playlist's timer fires. Runs sync then rearms."""
        row = registry.get_playlist_by_id(playlist_id)
        if row is None:
            logger.warning("PlaylistScheduler._fire: playlist %s not found in DB, skipping.", playlist_id)
            return

        # Track active thread so stop() can join it.
        current = threading.current_thread()
        with self._lock:
            self._active_threads[playlist_id] = current

        try:
            logger.info("PlaylistScheduler: firing sync for '%s'.", row["name"])
            _sync_parallel(
                playlist_id=playlist_id,
                playlist_name=row["name"],
                url=row["url"],
                fmt=row["format"],
                quality=row["quality"] or "best",
                output_dir=row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR),
                mb_user_agent=registry.get_setting("mb_user_agent"),
                max_workers=_get_max_workers(),
                auto_rename=bool(row["auto_rename"]),
            )
        except Exception as exc:
            logger.error("PlaylistScheduler: sync failed for '%s': %s", row["name"], exc)
        finally:
            with self._lock:
                self._active_threads.pop(playlist_id, None)

        self._rearm(playlist_id)

    def _rearm(self, playlist_id: str) -> None:
        """Re-read interval from DB and arm a new timer."""
        row = registry.get_playlist_by_id(playlist_id)
        if row is None or not row["watched"]:
            return
        interval = self._resolve_interval(row)
        self._arm(playlist_id, interval)
        logger.debug("PlaylistScheduler: rearmed '%s' — next sync in %ds.", row["name"], interval)


# ===========================================================================
# FastAPI daemon
# ===========================================================================

# Module-level scheduler instance — set by cmd_watch during daemon startup.
_scheduler: Optional[PlaylistScheduler] = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _scheduler
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)
    _scheduler = PlaylistScheduler()
    _scheduler.start()
    yield
    if _scheduler is not None:
        _scheduler.stop()


app = FastAPI(title="Siphon", lifespan=_lifespan)

_DAEMON_URL = "http://localhost:8000"


# ------------------------------------------------------------------
# Pydantic request/response models
# ------------------------------------------------------------------

class PlaylistCreate(BaseModel):
    url: str
    format: str = "mp3"
    quality: str = "best"
    output_dir: Optional[str] = None
    auto_rename: bool = False
    watched: bool = True
    check_interval_secs: Optional[int] = None
    download: bool = False


class PlaylistPatch(BaseModel):
    watched: Optional[bool] = None
    check_interval_secs: Optional[int] = None
    auto_rename: Optional[bool] = None


class SettingWrite(BaseModel):
    value: str


# ------------------------------------------------------------------
# /playlists endpoints
# ------------------------------------------------------------------

@app.post("/playlists", status_code=201)
def api_add_playlist(body: PlaylistCreate):
    url = body.url
    if "list=" not in url and "/playlist" not in url:
        raise HTTPException(status_code=400, detail="Only playlist URLs are supported. URL must contain 'list='.")

    output_dir = _resolve_output_dir(body.output_dir or _DEFAULT_OUTPUT_DIR)

    logger.info("Fetching playlist info from YouTube…")
    info = _fetch_playlist_info(url)
    playlist_id = info.get("id") or info.get("playlist_id")
    playlist_name = info.get("title") or info.get("playlist_title")

    if not playlist_id or not playlist_name:
        raise HTTPException(status_code=422, detail="Could not retrieve playlist ID or title from YouTube.")

    try:
        registry.add_playlist(
            playlist_id,
            playlist_name,
            url,
            fmt=body.format,
            quality=body.quality,
            output_dir=output_dir,
            auto_rename=body.auto_rename,
            watched=body.watched,
            check_interval_secs=body.check_interval_secs,
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Playlist already registered.")

    if _scheduler is not None:
        _scheduler.add_playlist(playlist_id)

    if body.download:
        mb_user_agent = registry.get_setting("mb_user_agent")
        t = threading.Thread(
            target=_sync_parallel,
            kwargs=dict(
                playlist_id=playlist_id,
                playlist_name=playlist_name,
                url=url,
                fmt=body.format,
                quality=body.quality,
                output_dir=output_dir,
                mb_user_agent=mb_user_agent,
                max_workers=_get_max_workers(),
                auto_rename=body.auto_rename,
            ),
            daemon=True,
        )
        t.start()

    row = registry.get_playlist_by_id(playlist_id)
    return _playlist_to_dict(row)


@app.get("/playlists")
def api_list_playlists():
    return [_playlist_to_dict(p) for p in registry.list_playlists()]


@app.get("/playlists/{playlist_id}")
def api_get_playlist(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    return _playlist_to_dict(row)


@app.delete("/playlists/{playlist_id}", status_code=204)
def api_delete_playlist(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    if _scheduler is not None:
        _scheduler.remove_playlist(playlist_id)
    registry.delete_playlist(playlist_id)


@app.patch("/playlists/{playlist_id}")
def api_patch_playlist(playlist_id: str, body: PlaylistPatch):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    if body.watched is not None:
        registry.set_playlist_watched(playlist_id, body.watched)
    if body.check_interval_secs is not None:
        registry.set_playlist_interval(playlist_id, body.check_interval_secs)
    if body.auto_rename is not None:
        registry.set_playlist_auto_rename(playlist_id, body.auto_rename)
    if _scheduler is not None:
        _scheduler.reschedule_playlist(playlist_id)
    return _playlist_to_dict(registry.get_playlist_by_id(playlist_id))


@app.post("/playlists/{playlist_id}/sync", status_code=202)
def api_sync_playlist(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    t = threading.Thread(
        target=_sync_parallel,
        kwargs=dict(
            playlist_id=playlist_id,
            playlist_name=row["name"],
            url=row["url"],
            fmt=row["format"],
            quality=row["quality"] or "best",
            output_dir=row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR),
            mb_user_agent=registry.get_setting("mb_user_agent"),
            max_workers=_get_max_workers(),
            auto_rename=bool(row["auto_rename"]),
        ),
        daemon=True,
    )
    t.start()
    return {"status": "sync started", "playlist_id": playlist_id}


@app.post("/playlists/{playlist_id}/sync-failed", status_code=202)
def api_sync_failed_playlist(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    t = threading.Thread(
        target=_run_sync_failed_for_playlist,
        args=(row,),
        daemon=True,
    )
    t.start()
    return {"status": "sync-failed started", "playlist_id": playlist_id}


# ------------------------------------------------------------------
# /settings endpoints
# ------------------------------------------------------------------

@app.get("/settings")
def api_get_settings():
    conn = registry._get_conn()
    rows = conn.execute("SELECT key, value FROM settings ORDER BY key ASC").fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.get("/settings/{key}")
def api_get_setting(key: str):
    value = registry.get_setting(key)
    return {"key": key, "value": value}


@app.put("/settings/{key}")
def api_put_setting(key: str, body: SettingWrite):
    # Normalise key (CLI uses hyphens, DB uses underscores for legacy keys)
    if key not in _KNOWN_KEYS and key.replace("-", "_") not in _KNOWN_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown key '{key}'. Known keys: {', '.join(_KNOWN_KEYS)}.")
    db_key = _KNOWN_KEYS.get(key, (key.replace("-", "_"), ""))[0]
    registry.set_setting(db_key, body.value)
    return {"key": key, "value": body.value}


# ------------------------------------------------------------------
# /health endpoint
# ------------------------------------------------------------------

@app.get("/health")
def api_health():
    watched = len(registry.get_watched_playlists())
    return {"status": "ok", "watched_playlists": watched}


# ------------------------------------------------------------------
# Internal helpers for API handlers
# ------------------------------------------------------------------

def _playlist_to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row)
    d["item_count"] = registry.count_items(row["id"])
    return d


def _run_sync_failed_for_playlist(row) -> None:
    """Run sync-failed logic for a single playlist row (called in a thread)."""
    pid = row["id"]
    pname = row["name"]
    failures = registry.get_failed(pid)
    if not failures:
        logger.info("No failures recorded for '%s'.", pname)
        return
    entries = [{"id": f["video_id"], "url": f["url"], "title": f["yt_title"]} for f in failures]
    options = _build_options(row["format"], row["quality"] or "best")
    output_dir = row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR)
    successes, new_failures = download_parallel(
        entries=entries,
        playlist_id=pid,
        playlist_name=pname,
        options=options,
        output_dir=output_dir,
        mb_user_agent=registry.get_setting("mb_user_agent"),
        max_workers=_get_max_workers(),
        auto_rename=bool(row["auto_rename"]),
    )
    logger.info("'%s': %d recovered, %d still failing.", pname, len(successes), len(new_failures))


# ===========================================================================
# siphon watch — daemon entry point
# ===========================================================================

def cmd_watch(_args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
    )
    return 0


# ===========================================================================
# CLI daemon client helper
# ===========================================================================

def _daemon_get(path: str) -> Any:
    """GET from the daemon. Exits with error if daemon is not reachable."""
    try:
        resp = _requests.get(f"{_DAEMON_URL}{path}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except _requests.exceptions.ConnectionError:
        print("siphon watch is not running. Start it with 'siphon watch'.", file=sys.stderr)
        sys.exit(1)


def _daemon_post(path: str, json: Optional[dict] = None, *, expect_status: int = 200) -> Any:
    """POST to the daemon. Returns parsed JSON or None for 204."""
    try:
        resp = _requests.post(f"{_DAEMON_URL}{path}", json=json or {}, timeout=60)
        if resp.status_code == expect_status:
            return resp.json() if resp.content else None
        _daemon_handle_error(resp)
        return None
    except _requests.exceptions.ConnectionError:
        print("siphon watch is not running. Start it with 'siphon watch'.", file=sys.stderr)
        sys.exit(1)


def _daemon_delete(path: str) -> None:
    """DELETE on the daemon."""
    try:
        resp = _requests.delete(f"{_DAEMON_URL}{path}", timeout=10)
        if resp.status_code not in (200, 204):
            _daemon_handle_error(resp)
    except _requests.exceptions.ConnectionError:
        print("siphon watch is not running. Start it with 'siphon watch'.", file=sys.stderr)
        sys.exit(1)


def _daemon_patch(path: str, json: dict) -> Any:
    """PATCH on the daemon."""
    try:
        resp = _requests.patch(f"{_DAEMON_URL}{path}", json=json, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except _requests.exceptions.ConnectionError:
        print("siphon watch is not running. Start it with 'siphon watch'.", file=sys.stderr)
        sys.exit(1)


def _daemon_put(path: str, json: dict) -> Any:
    """PUT on the daemon."""
    try:
        resp = _requests.put(f"{_DAEMON_URL}{path}", json=json, timeout=10)
        if resp.status_code == 400:
            data = resp.json()
            print(f"Error: {data.get('detail', resp.text)}", file=sys.stderr)
            sys.exit(1)
        resp.raise_for_status()
        return resp.json()
    except _requests.exceptions.ConnectionError:
        print("siphon watch is not running. Start it with 'siphon watch'.", file=sys.stderr)
        sys.exit(1)


def _daemon_handle_error(resp) -> None:
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    print(f"Error: {detail}", file=sys.stderr)
    sys.exit(1)


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
    name_filter = getattr(args, "name", None)
    if name_filter:
        playlists = _daemon_get("/playlists")
        match = next((p for p in playlists if p["name"] == name_filter), None)
        if match is None:
            logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", name_filter)
            return 1
        _daemon_post(f"/playlists/{match['id']}/sync", expect_status=202)
        logger.info("Sync started for '%s'.", name_filter)
    else:
        playlists = _daemon_get("/playlists")
        if not playlists:
            logger.info("No playlists registered. Use 'siphon add <url>' to add one.")
            return 0
        for p in playlists:
            _daemon_post(f"/playlists/{p['id']}/sync", expect_status=202)
            logger.info("Sync started for '%s'.", p["name"])
    return 0


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> int:
    playlists = _daemon_get("/playlists")
    if not playlists:
        logger.info("No playlists registered.")
        return 0

    rows = []
    for p in playlists:
        count = p.get("item_count", 0)
        last_synced = p.get("last_synced_at") or "never"
        if last_synced != "never" and "T" in last_synced:
            last_synced = last_synced.replace("T", " ")[:19] + " UTC"
        rows.append((p["name"], p["url"], count, last_synced))

    name_w = max(len("NAME"), max(len(r[0]) for r in rows))
    url_w = max(len("URL"), max(len(r[1]) for r in rows))
    url_w = min(url_w, 60)
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
    playlists = _daemon_get("/playlists")
    match = next((p for p in playlists if p["name"] == args.name), None)
    if match is None:
        logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", args.name)
        return 1

    count = match.get("item_count", 0)
    print(f"Playlist:  {args.name}")
    print(f"Items:     {count}")
    print()
    print("This will remove the playlist and all its records from the registry.")
    print("Your downloaded music files will NOT be deleted.")
    print()
    answer = input("Confirm deletion? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. No changes made.")
        return 0

    _daemon_delete(f"/playlists/{match['id']}")
    print(f"Deleted playlist '{args.name}' from registry.")
    return 0


# ---------------------------------------------------------------------------
# sync-failed
# ---------------------------------------------------------------------------

def cmd_sync_failed(args: argparse.Namespace) -> int:
    name_filter = getattr(args, "name", None)
    playlists = _daemon_get("/playlists")

    if name_filter:
        match = next((p for p in playlists if p["name"] == name_filter), None)
        if match is None:
            logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", name_filter)
            return 1
        _daemon_post(f"/playlists/{match['id']}/sync-failed", expect_status=202)
        logger.info("Sync-failed started for '%s'.", name_filter)
    else:
        if not playlists:
            logger.info("No failures recorded.")
            return 0
        for p in playlists:
            _daemon_post(f"/playlists/{p['id']}/sync-failed", expect_status=202)
        logger.info("Sync-failed started for all playlists.")
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
    "interval": (
        "check_interval",
        "Default sync interval in seconds for all watched playlists (e.g. 3600 = hourly, "
        "86400 = daily). Per-playlist overrides take precedence. Default: 86400.",
    ),
}

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}

_PLAYLIST_KNOWN_KEYS = {"interval", "auto-rename", "watched"}


def cmd_config(args: argparse.Namespace) -> int:
    key_arg = args.key
    if key_arg not in _KNOWN_KEYS:
        known = ", ".join(_KNOWN_KEYS)
        logger.error("Unknown config key '%s'. Known keys: %s", key_arg, known)
        return 1

    db_key, _description = _KNOWN_KEYS[key_arg]

    if args.value is None:
        # Read mode — query daemon
        data = _daemon_get(f"/settings/{db_key}")
        val = data.get("value")
        if val is None:
            print(f"{key_arg}: (not set)")
        else:
            print(f"{key_arg}: {val}")
        return 0

    # Write mode — validate before sending to daemon
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
    if key_arg == "interval":
        try:
            int_val = int(args.value)
        except ValueError:
            logger.error("interval must be a positive integer (seconds), got '%s'.", args.value)
            return 1
        if int_val <= 0:
            logger.error("interval must be a positive integer.")
            return 1

    value = args.value.upper() if key_arg == "log-level" else args.value
    _daemon_put(f"/settings/{db_key}", {"value": value})
    print(f"Set {key_arg}.")
    return 0


def cmd_config_playlist(args: argparse.Namespace) -> int:
    playlists = _daemon_get("/playlists")
    match = next((p for p in playlists if p["name"] == args.name), None)
    if match is None:
        logger.error("Playlist '%s' not found.", args.name)
        return 1

    pid = match["id"]

    if args.key is None:
        # Read-only: show all settings
        print(f"name:        {match['name']}")
        print(f"watched:     {bool(match.get('watched', True))}")
        interval = match.get("check_interval_secs")
        print(f"interval:    {interval if interval is not None else '(global default)'}")
        print(f"auto-rename: {bool(match.get('auto_rename', False))}")
        return 0

    if args.key not in _PLAYLIST_KNOWN_KEYS:
        logger.error("Unknown key '%s'. Known keys: %s", args.key, ", ".join(sorted(_PLAYLIST_KNOWN_KEYS)))
        return 1

    if args.value is None:
        # Read mode for a specific key
        if args.key == "interval":
            val = match.get("check_interval_secs")
            print(f"interval: {val if val is not None else '(global default)'}")
        elif args.key == "auto-rename":
            print(f"auto-rename: {bool(match.get('auto_rename', False))}")
        elif args.key == "watched":
            print(f"watched: {bool(match.get('watched', True))}")
        return 0

    # Write mode
    patch: dict = {}
    if args.key == "interval":
        try:
            val = int(args.value)
        except ValueError:
            logger.error("interval must be a positive integer (seconds), got '%s'.", args.value)
            return 1
        if val <= 0:
            logger.error("interval must be a positive integer.")
            return 1
        patch["check_interval_secs"] = val
    else:
        try:
            bool_val = _parse_bool(args.value)
        except argparse.ArgumentTypeError as exc:
            logger.error("%s", exc)
            return 1
        if args.key == "auto-rename":
            patch["auto_rename"] = bool_val
        else:
            patch["watched"] = bool_val

    _daemon_patch(f"/playlists/{pid}", patch)
    print(f"Set {args.key} for '{args.name}'.")
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

    # Apply log-level from DB if already set; fall back to INFO on a fresh install.
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

    # -- watch --
    sub.add_parser("watch", help="Start the Siphon daemon (required for all other commands).")

    # -- add --
    p_add = sub.add_parser("add", help="Register a YouTube playlist.")
    p_add.add_argument("url", help="YouTube playlist URL.")
    p_add.add_argument("--download", action="store_true", help="Download all items immediately after registering.")
    p_add.add_argument("--no-watch", dest="no_watch", action="store_true", default=False,
                       help="Register playlist without adding it to the automatic sync schedule.")
    p_add.add_argument("--interval", type=int, default=None, metavar="SECS",
                       help="Per-playlist sync interval in seconds (overrides global interval).")
    p_add.add_argument("--format", default="mp3", choices=_ALL_FORMATS, help="Output format (default: mp3).")
    p_add.add_argument("--quality", default="best", choices=sorted(VALID_RESOLUTIONS),
                       help="Video quality: best, 2160, 1080, 720, 480, 360 (default: best).")
    p_add.add_argument("--output-dir", default=_DEFAULT_OUTPUT_DIR, help="Root directory for downloads.")
    p_add.add_argument("--auto-rename", dest="auto_rename", action="store_true", default=False,
                       help="Enable auto-rename for this playlist.")

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

    # -- config-playlist --
    p_cfgp = sub.add_parser("config-playlist", help="Get or set a per-playlist configuration value.")
    p_cfgp.add_argument("name", help="Playlist name to configure.")
    p_cfgp.add_argument("key", nargs="?", default=None, metavar="key",
                        help="Setting to read or write: interval, auto-rename, watched. Omit to show all.")
    p_cfgp.add_argument("value", nargs="?", default=None, help="Value to set. Omit to read the current value.")

    args = parser.parse_args()

    dispatch = {
        "watch": cmd_watch,
        "add": cmd_add,
        "sync": cmd_sync,
        "sync-failed": cmd_sync_failed,
        "list": cmd_list,
        "delete": cmd_delete,
        "config": cmd_config,
        "config-playlist": cmd_config_playlist,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
