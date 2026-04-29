"""
siphon.api — FastAPI daemon: routes, SSE streams, and background sync.

Started by ``siphon start`` (see :mod:`siphon.app`). All state lives in
module-level globals initialised in the lifespan handler.
"""
import asyncio
import json
import os
import logging
import re
import threading
import time
from contextlib import asynccontextmanager
from typing import List, Optional

import importlib.metadata

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from yt_dlp import YoutubeDL

from siphon import registry
from siphon.downloader import (
    enumerate_entries,
    filter_entries,
    run_download_job,
    sync_parallel,
    run_sync_failed_for_playlist,
)
from siphon.formats import VALID_AUDIO_FORMATS, VALID_VIDEO_FORMATS, build_options
from siphon.models import (
    DownloadJob,
    PlaylistCreate, PlaylistPatch, SettingWrite, JobCreate, RenameRequest,
)
from siphon.job_store import JobStore
from siphon.renamer import sanitize as sanitize_name, _DEFAULT_NOISE_PATTERNS, resolve_file_path, extract_extension, update_title_metadata
from siphon.cli import _KNOWN_KEYS, _ALLOWED_VALUES
from siphon.scheduler import PlaylistScheduler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".data")
_DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
_ALL_FORMATS = sorted(VALID_AUDIO_FORMATS | VALID_VIDEO_FORMATS)
_DEFAULT_MAX_WORKERS = 5
_MAX_WORKERS_CEILING = 10

_VALID_SB_CATEGORIES = frozenset({
    "sponsor", "interaction", "selfpromo", "intro", "outro",
    "preview", "hook", "filler", "music_offtopic",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_data_dir() -> str:
    return os.path.abspath(_DATA_DIR)


def _resolve_output_dir(output_dir: str) -> str:
    return os.path.abspath(output_dir)


def _normalise_url(url: str) -> str:
    """
    If the URL contains a YouTube list= param, return a clean playlist URL
    (https://www.youtube.com/playlist?list=LIST_ID), discarding any v= param.
    This avoids yt-dlp treating the URL as a single-video context and only
    returning one entry instead of the full playlist.
    For non-YouTube URLs, the URL is returned unchanged.

    Special auto-generated list types (Mix, Watch Later, etc.) are stripped
    entirely from the URL so yt-dlp treats it as a plain single-video URL.
    """
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parsed = urlparse(url)
    if parsed.netloc not in ("www.youtube.com", "youtube.com", "youtu.be"):
        return url
    qs = parse_qs(parsed.query, keep_blank_values=True)
    list_id = qs.get("list", [None])[0]
    if not list_id:
        return url
    # RD = Mix/Radio, WL = Watch Later, LL = Liked Videos, FL = Favourites —
    # these are private/auto-generated and cannot be fetched as playlist URLs.
    _UNVIEWABLE_PREFIXES = ("RD", "WL", "LL", "FL")
    if list_id.startswith(_UNVIEWABLE_PREFIXES):
        # Strip the list= param so yt-dlp only sees the v= and downloads one video.
        clean_qs = {k: v for k, v in qs.items() if k != "list"}
        return urlunparse(parsed._replace(query=urlencode(clean_qs, doseq=True)))
    if "v" in qs:
        # Has both v= and list= with a real playlist — normalise to clean playlist URL
        return f"https://www.youtube.com/playlist?list={list_id}"
    return url


_EXTRACTOR_SUFFIXES = re.compile(
    r'(?:Tab|Playlist|Channel|Album|User|Search|Feed|Tag|Set|IE)$'
)


def sanitize_platform(extractor_key: str) -> str:
    """Strip yt-dlp internal suffixes from extractor_key for human-readable display.

    Examples: 'YoutubeTab' → 'Youtube', 'BandcampAlbum' → 'Bandcamp'.
    """
    return _EXTRACTOR_SUFFIXES.sub('', extractor_key).strip() or extractor_key


# Cached playlist URL patterns derived from yt-dlp extractor _VALID_URL regexes.
# Computed once at first request so startup time is unaffected.
_PLAYLIST_PATTERNS: dict | None = None
_PLAYLIST_PATH_KW = frozenset(['list', 'playlist', 'album', 'set', 'channel', 'collection', 'series', 'feed', 'user', 'favlist', 'mylist'])
_PLAYLIST_PARAM_KW = frozenset(['list', 'playlist', 'playlistid', 'album', 'channel', 'series', 'user'])
_SKIP_SEGMENTS = frozenset(['www', 'com', 'net', 'org', 'tv', 'io', 'watch', 'video', 'videos'])


def _compute_playlist_patterns() -> dict:
    global _PLAYLIST_PATTERNS
    if _PLAYLIST_PATTERNS is not None:
        return _PLAYLIST_PATTERNS
    from yt_dlp import extractor as yt_extractor
    path_segments: set[str] = set()
    query_params: set[str] = set()
    for ie in yt_extractor.gen_extractors():
        valid_url = getattr(ie, '_VALID_URL', None)
        if not valid_url:
            continue
        if not isinstance(valid_url, str):
            valid_url = str(valid_url)
        for seg in re.findall(r'/([a-z_-]{3,20})/', valid_url):
            if seg not in _SKIP_SEGMENTS:
                path_segments.add(seg)
        for param in re.findall(r'[?&]([a-z_]{2,15})=', valid_url):
            query_params.add(param)
    _PLAYLIST_PATTERNS = {
        "path_segments": sorted(s for s in path_segments if any(k in s for k in _PLAYLIST_PATH_KW)),
        "query_params": sorted(q for q in query_params if any(k in q for k in _PLAYLIST_PARAM_KW)),
    }
    return _PLAYLIST_PATTERNS


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


# ===========================================================================
# FastAPI daemon
# ===========================================================================

# Module-level singleton instances — set during daemon startup.
_scheduler: Optional[PlaylistScheduler] = None
_job_store: Optional[JobStore] = None

# ---------------------------------------------------------------------------
# Sync-events state (daemon-memory only, resets on restart)
# ---------------------------------------------------------------------------

_syncing_playlists: set = set()           # playlist_ids currently syncing
_sync_info: dict = {}                     # playlist_id -> new_items count while syncing
_sync_event_queues: List[asyncio.Queue] = []  # one per SSE subscriber
_sync_loop: Optional[asyncio.AbstractEventLoop] = None

# ---------------------------------------------------------------------------
# Log-stream state (browser console SSE)
# ---------------------------------------------------------------------------

_log_queues: List[asyncio.Queue] = []     # one per /logs/stream SSE subscriber
_log_loop: Optional[asyncio.AbstractEventLoop] = None
_browser_logs_enabled: bool = False       # cached from DB setting


class _SSELogHandler(logging.Handler):
    """Push log records to SSE subscriber queues for browser console streaming."""

    def emit(self, record: logging.LogRecord) -> None:
        if not _browser_logs_enabled or not _log_queues:
            return
        loop = _log_loop
        if loop is None:
            return
        try:
            payload = json.dumps({
                "level": record.levelname,
                "name": record.name,
                "msg": self.format(record),
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(record.created)),
            })
        except Exception:
            return
        for q in list(_log_queues):
            try:
                loop.call_soon_threadsafe(q.put_nowait, payload)
            except Exception:
                pass


def _broadcast_sync_event(event: str, playlist_id: str, **extra) -> None:
    """
    Broadcast a sync lifecycle event to all sync-events SSE subscribers.
    Safe to call from background threads: bridges via asyncio.call_soon_threadsafe.
    """
    payload = json.dumps({"event": event, "playlist_id": playlist_id, **extra})
    loop = _sync_loop
    if loop is None:
        return
    for q in list(_sync_event_queues):
        try:
            loop.call_soon_threadsafe(q.put_nowait, payload)
        except Exception:
            pass


def _on_sync_info(playlist_id: str, new_items: int) -> None:
    """Callback for sync_parallel: update sync info and broadcast."""
    _sync_info[playlist_id] = new_items
    _broadcast_sync_event("sync_info", playlist_id, new_items=new_items)


def _on_sync_done(playlist_id: str) -> None:
    """Callback for sync_parallel: cleanup sync state and broadcast."""
    _sync_info.pop(playlist_id, None)
    _syncing_playlists.discard(playlist_id)
    _broadcast_sync_event("sync_done", playlist_id)


def _scheduler_sync_fn(row) -> None:
    """Callback wired into PlaylistScheduler._fire — runs sync_parallel with daemon globals."""
    playlist_id = row["id"]
    _syncing_playlists.add(playlist_id)
    _broadcast_sync_event("sync_started", playlist_id)
    sync_parallel(
        playlist_id=playlist_id,
        playlist_name=row["name"],
        url=row["url"],
        fmt=row["format"],
        quality=row["quality"] or "best",
        output_dir=row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR),
        mb_user_agent=registry.get_setting("mb_user_agent"),
        max_workers=_get_max_workers(),
        auto_rename=bool(row["auto_rename"]),
        noise_patterns=registry.get_noise_patterns(),
        on_sync_info=_on_sync_info,
        on_sync_done=_on_sync_done,
        sponsorblock_categories=registry.get_sponsorblock_categories(row),
        cookie_file=_get_cookie_file_path(row),
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    global _scheduler, _job_store, _sync_loop, _log_loop, _browser_logs_enabled
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)
    if not registry.get_setting("title_noise_patterns"):
        registry.set_setting("title_noise_patterns", json.dumps(_DEFAULT_NOISE_PATTERNS))
    _browser_logs_enabled = registry.get_setting("browser_logs") == "on"
    stored_log_level = registry.get_setting("log_level")
    if stored_log_level:
        logging.getLogger("siphon").setLevel(getattr(logging, stored_log_level, logging.INFO))
    _scheduler = PlaylistScheduler(sync_fn=_scheduler_sync_fn)
    _scheduler.start()
    _job_store = JobStore()
    _job_store.set_loop(asyncio.get_event_loop())
    _sync_loop = asyncio.get_event_loop()
    _log_loop = asyncio.get_event_loop()
    yield
    if _scheduler is not None:
        _scheduler.stop()


app = FastAPI(title="Siphon", lifespan=_lifespan)


@app.middleware("http")
async def _log_requests(request, call_next):
    logger.debug("%s %s", request.method, request.url.path)
    return await call_next(request)


# ------------------------------------------------------------------
# /playlists endpoints
# ------------------------------------------------------------------

@app.post("/playlists", status_code=201)
def api_add_playlist(body: PlaylistCreate):
    url = _normalise_url(body.url)
    output_dir = _resolve_output_dir(body.output_dir or _DEFAULT_OUTPUT_DIR)

    logger.info("Fetching playlist info…")
    info = _fetch_playlist_info(url)
    playlist_id = info.get("id") or info.get("playlist_id")
    playlist_name = info.get("title") or info.get("playlist_title")

    if not playlist_id or not playlist_name:
        raise HTTPException(status_code=422, detail="Could not retrieve playlist ID or title.")

    platform = sanitize_platform(info.get("extractor_key", "")) or None

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
            platform=platform,
            sponsorblock_categories=_resolve_sb_categories_for_create(body),
        )
    except ValueError:
        raise HTTPException(status_code=409, detail="Playlist already registered.")

    if _scheduler is not None:
        _scheduler.add_playlist(playlist_id)

    if body.download:
        mb_user_agent = registry.get_setting("mb_user_agent")
        _syncing_playlists.add(playlist_id)
        _broadcast_sync_event("sync_started", playlist_id)
        fresh_row = registry.get_playlist_by_id(playlist_id)
        t = threading.Thread(
            target=sync_parallel,
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
                noise_patterns=registry.get_noise_patterns(),
                on_sync_info=_on_sync_info,
                on_sync_done=_on_sync_done,
                sponsorblock_categories=registry.get_sponsorblock_categories(fresh_row),
            ),
            daemon=True,
        )
        t.start()

    row = registry.get_playlist_by_id(playlist_id)
    return _playlist_to_dict(row)


@app.get("/playlists")
def api_list_playlists():
    return [_playlist_to_dict(p) for p in registry.list_playlists()]


@app.get("/playlists/sync-events")
async def api_sync_events():
    """SSE stream that broadcasts sync_started / sync_done events."""
    logger.debug("SSE subscriber connected: /playlists/sync-events")
    q: asyncio.Queue = asyncio.Queue()
    _sync_event_queues.append(q)

    async def event_generator():
        try:
            while True:
                payload = await q.get()
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _sync_event_queues.remove(q)
            except ValueError:
                pass
            logger.debug("SSE subscriber disconnected: /playlists/sync-events")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/logs/stream")
async def api_log_stream():
    """SSE stream that broadcasts daemon log records to the browser console."""
    if not _browser_logs_enabled:
        raise HTTPException(status_code=503, detail="Browser logs are disabled.")
    logger.debug("SSE subscriber connected: /logs/stream")
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _log_queues.append(q)

    async def event_generator():
        try:
            while True:
                payload = await q.get()
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _log_queues.remove(q)
            except ValueError:
                pass
            logger.debug("SSE subscriber disconnected: /logs/stream")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/playlists/{playlist_id}")
def api_get_playlist(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    return _playlist_to_dict(row)


@app.delete("/playlists", status_code=204)
def api_delete_all_playlists():
    if _scheduler is not None:
        for pid in list(registry.list_playlists()):
            _scheduler.remove_playlist(pid["id"])
    registry.delete_all_playlists()


@app.post("/factory-reset", status_code=204)
def api_factory_reset():
    if _scheduler is not None:
        for pid in list(registry.list_playlists()):
            _scheduler.remove_playlist(pid["id"])
    registry.factory_reset()
    try:
        registry.delete_cookie_file_safe(_resolve_data_dir())
    except Exception:
        pass  # silently ignore if file absent or error


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
    if body.sponsorblock_enabled is not None or body.sponsorblock_categories is not None:
        _apply_sb_patch(playlist_id, body)
    if body.cookies_enabled is not None or "cookies_enabled" in body.model_fields_set:
        registry.set_playlist_cookies_enabled(playlist_id, body.cookies_enabled)
    if _scheduler is not None and (body.watched is not None or body.check_interval_secs is not None):
        _scheduler.reschedule_playlist(playlist_id)
    return _playlist_to_dict(registry.get_playlist_by_id(playlist_id))


@app.post("/playlists/{playlist_id}/sync", status_code=202)
def api_sync_playlist(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    _syncing_playlists.add(playlist_id)
    _broadcast_sync_event("sync_started", playlist_id)
    t = threading.Thread(
        target=sync_parallel,
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
            noise_patterns=registry.get_noise_patterns(),
            on_sync_info=_on_sync_info,
            on_sync_done=_on_sync_done,
            sponsorblock_categories=registry.get_sponsorblock_categories(row),
            cookie_file=_get_cookie_file_path(row),
        ),
        daemon=True,
    )
    t.start()
    return {"status": "sync started", "playlist_id": playlist_id}


@app.get("/playlists/{playlist_id}/items")
def api_get_playlist_items(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    return registry.list_items_for_playlist(playlist_id)


@app.put("/playlists/{playlist_id}/items/{video_id}/rename")
def api_rename_playlist_item(playlist_id: str, video_id: str, body: RenameRequest):
    """Rename a downloaded playlist item on disk and in the DB."""
    playlist = registry.get_playlist_by_id(playlist_id)
    if playlist is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")

    item = registry.get_item(video_id, playlist_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found in this playlist.")

    new_name = sanitize_name(body.new_name.strip())
    if not new_name:
        raise HTTPException(status_code=422, detail="New name is empty or contains only unsafe characters.")

    # Resolve paths.
    output_dir = _resolve_output_dir(playlist["output_dir"])
    safe_folder = sanitize_name(playlist["name"]) or playlist_id
    item_dir = os.path.join(output_dir, safe_folder)

    old_stem = item["renamed_to"] or item["title"]
    old_path = resolve_file_path(item_dir, old_stem)
    if old_path is None:
        raise HTTPException(status_code=404, detail=f"File not found on disk for '{old_stem}'.")

    _, ext = extract_extension(os.path.basename(old_path))
    new_path = os.path.join(item_dir, f"{new_name}{ext}")

    if os.path.exists(new_path) and not os.path.samefile(new_path, old_path):
        raise HTTPException(status_code=409, detail=f"A file named '{new_name}{ext}' already exists.")

    os.rename(old_path, new_path)
    update_title_metadata(new_path, new_name)
    registry.update_item_rename(video_id, playlist_id, new_name)

    updated = registry.get_item(video_id, playlist_id)
    return updated


@app.post("/playlists/{playlist_id}/sync-failed", status_code=202)
def api_sync_failed_playlist(playlist_id: str):
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Playlist not found.")
    t = threading.Thread(
        target=run_sync_failed_for_playlist,
        kwargs=dict(
            row=row,
            max_workers=_get_max_workers(),
            default_output_dir=_resolve_output_dir(_DEFAULT_OUTPUT_DIR),
            cookie_file=_get_cookie_file_path(row),
        ),
        daemon=True,
    )
    t.start()
    return {"status": "sync-failed started", "playlist_id": playlist_id}


# ------------------------------------------------------------------
# /settings endpoints
# ------------------------------------------------------------------

_COOKIE_FILE_MAX_BYTES = 1_048_576  # 1 MB


def _get_cookie_file_path(playlist_row=None) -> Optional[str]:
    """Return the effective cookie file path for a given playlist row, or None."""
    return registry.get_cookie_file(playlist_row)


def _validate_netscape_cookies(content: str) -> bool:
    """Return True if content contains at least one valid Netscape cookie line."""
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            continue
        # Fields 2 and 4 must be TRUE or FALSE; field 5 must be a non-negative integer
        if parts[1] not in ("TRUE", "FALSE"):
            continue
        if parts[3] not in ("TRUE", "FALSE"):
            continue
        try:
            if int(parts[4]) < 0:
                continue
        except ValueError:
            continue
        return True
    return False


@app.get("/settings/cookie-file")
def api_get_cookie_file():
    cookie_path = os.path.join(_resolve_data_dir(), "cookies.txt")
    return {"set": os.path.isfile(cookie_path)}


@app.post("/settings/cookie-file", status_code=204)
async def api_upload_cookie_file(request: Request):
    body = await request.body()
    if len(body) > _COOKIE_FILE_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 1 MB size limit.")
    try:
        content = body.decode("utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not decode file as text.")
    if not _validate_netscape_cookies(content):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid Netscape HTTP cookie file. "
                   "Expected tab-separated lines with 7 fields (domain, TRUE/FALSE, path, TRUE/FALSE, expiry, name, value).",
        )
    cookie_path = os.path.join(_resolve_data_dir(), "cookies.txt")
    tmp_path = cookie_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, cookie_path)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save cookie file: {exc}")
    logger.info("Cookie file uploaded and saved to %s", cookie_path)


@app.delete("/settings/cookie-file", status_code=204)
def api_delete_cookie_file():
    deleted = registry.delete_cookie_file_safe(_resolve_data_dir())
    if not deleted:
        raise HTTPException(status_code=404, detail="No cookie file is configured.")


@app.get("/settings")
def api_get_settings():
    conn = registry._get_conn()
    rows = conn.execute("SELECT key, value FROM settings ORDER BY key ASC").fetchall()
    return {r["key"]: r["value"] for r in rows}


@app.get("/settings/{key}")
def api_get_setting(key: str):
    db_key = _KNOWN_KEYS[key][0] if key in _KNOWN_KEYS else key
    value = registry.get_setting(db_key)
    return {"key": key, "value": value}


@app.put("/settings/{key}")
def api_put_setting(key: str, body: SettingWrite):
    if key not in _KNOWN_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown key '{key}'. Known keys: {', '.join(_KNOWN_KEYS)}.")
    if key in _ALLOWED_VALUES and body.value not in _ALLOWED_VALUES[key]:
        allowed = ", ".join(sorted(_ALLOWED_VALUES[key]))
        raise HTTPException(status_code=400, detail=f"Invalid value '{body.value}' for '{key}'. Allowed: {allowed}.")
    if key == "title-noise-patterns":
        import json as _json
        import re as _re
        try:
            patterns = _json.loads(body.value)
        except (_json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="title-noise-patterns must be a valid JSON array of strings.")
        if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
            raise HTTPException(status_code=400, detail="title-noise-patterns must be a JSON array of strings.")
        for p in patterns:
            try:
                _re.compile(p)
            except _re.error as exc:
                raise HTTPException(status_code=400, detail=f"Invalid regex pattern '{p}': {exc}")
    if key == "sb-cats":
        import json as _json
        try:
            cats = _json.loads(body.value)
        except (_json.JSONDecodeError, TypeError):
            raise HTTPException(status_code=400, detail="sb-cats must be a valid JSON array of strings.")
        invalid = [c for c in cats if c not in _VALID_SB_CATEGORIES]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid categories: {invalid}. Valid: {sorted(_VALID_SB_CATEGORIES)}")
    db_key = _KNOWN_KEYS[key][0]
    registry.set_setting(db_key, body.value)
    # Live propagation for log-level and browser-logs settings.
    if db_key == "log_level":
        logging.getLogger("siphon").setLevel(getattr(logging, body.value, logging.INFO))
    elif db_key == "browser_logs":
        global _browser_logs_enabled
        _browser_logs_enabled = body.value == "on"
    logger.info("Setting changed: %s → %s", key, body.value)
    return {"key": key, "value": body.value}


# ------------------------------------------------------------------
# /version endpoint
# ------------------------------------------------------------------

@app.get("/version")
def api_version():
    siphon_ver = os.environ.get("SIPHON_VERSION")
    if not siphon_ver:
        try:
            siphon_ver = importlib.metadata.version("siphon")
        except importlib.metadata.PackageNotFoundError:
            siphon_ver = "unknown"
    import yt_dlp.version as _ytv
    return {"siphon": siphon_ver, "yt_dlp": _ytv.__version__}


@app.get("/info")
def api_info():
    return {
        "download_dir": _resolve_output_dir(_DEFAULT_OUTPUT_DIR),
        "db_dir": _resolve_data_dir(),
        "logs_dir": _resolve_data_dir(),
    }


# ------------------------------------------------------------------
# /health endpoint
# ------------------------------------------------------------------

@app.get("/health")
def api_health():
    watched = len(registry.get_watched_playlists())
    return {"status": "ok", "watched_playlists": watched}


@app.get("/playlist-patterns")
def api_playlist_patterns():
    """Return yt-dlp-derived URL patterns that indicate a playlist/channel URL.

    Used by the frontend to show the Auto sync toggle when a playlist URL is entered.
    Computed once from yt-dlp extractor metadata and cached for the lifetime of the process.
    """
    return _compute_playlist_patterns()


# ------------------------------------------------------------------
# /jobs endpoints
# ------------------------------------------------------------------

@app.post("/jobs", status_code=202)
def api_create_job(body: JobCreate):
    url = _normalise_url(body.url)
    output_dir = _resolve_output_dir(body.output_dir or _DEFAULT_OUTPUT_DIR)

    try:
        info = _fetch_playlist_info(url)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not fetch URL info: {exc}")

    if not info:
        raise HTTPException(status_code=422, detail="Could not retrieve info for URL.")

    is_playlist = info.get("_type") == "playlist" or bool(info.get("entries"))
    existing_playlist = False

    if is_playlist:
        playlist_id = info.get("id") or info.get("playlist_id")
        playlist_name = info.get("title") or info.get("playlist_title")
        if not playlist_id or not playlist_name:
            raise HTTPException(status_code=422, detail="Could not retrieve playlist ID or title.")

        platform = sanitize_platform(info.get("extractor_key", "")) or None

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
                platform=platform,
                cookies_enabled=body.use_cookies if body.use_cookies else None,
            )
            existing_playlist = False
        except ValueError:
            existing_playlist = True  # already registered — sync new videos only

        if body.watched and _scheduler is not None:
            _scheduler.add_playlist(playlist_id)

        entries = enumerate_entries(url, cookie_file=_get_cookie_file_path() if body.use_cookies else None)
        entries = filter_entries(entries, playlist_id)
    else:
        # Single video
        video_id = info.get("id")
        if not video_id:
            raise HTTPException(status_code=422, detail="Could not retrieve video ID from URL.")
        playlist_id = None
        playlist_name = info.get("title") or video_id
        entries = [{"id": video_id, "url": url, "title": info.get("title") or video_id}]

    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized.")

    if not entries:
        if is_playlist and not existing_playlist:
            # We just registered this playlist but found nothing to download — roll back
            registry.delete_playlist(playlist_id)
            if _scheduler is not None:
                _scheduler.remove_playlist(playlist_id)
            raise HTTPException(
                status_code=422,
                detail="No downloadable videos found in this playlist.\nIt may only contain unavailable videos.",
            )
        if is_playlist and existing_playlist:
            raise HTTPException(status_code=422, detail="Playlist is already registered and up to date.")
        raise HTTPException(status_code=422, detail="Nothing new to download.")

    try:
        job_id = _job_store.create_job(playlist_id, playlist_name, entries, output_dir=output_dir, auto_rename=body.auto_rename)
    except ValueError as exc:
        if str(exc) == "active_job_exists":
            raise HTTPException(
                status_code=409,
                detail="A download is already in progress for this playlist.",
            )
        raise
    options = build_options(body.format, body.quality)
    sponsorblock_categories = _resolve_sb_categories_for_job(body)
    mb_user_agent = registry.get_setting("mb_user_agent")
    cookie_file = _get_cookie_file_path() if body.use_cookies else None

    t = threading.Thread(
        target=run_download_job,
        kwargs=dict(
            job_id=job_id,
            entries=entries,
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            options=options,
            output_dir=output_dir,
            mb_user_agent=mb_user_agent,
            max_workers=_get_max_workers(),
            auto_rename=body.auto_rename,
            noise_patterns=registry.get_noise_patterns(),
            job_store=_job_store,
            sponsorblock_categories=sponsorblock_categories,
            cookie_file=cookie_file,
        ),
        daemon=True,
    )
    t.start()

    return {"job_id": job_id, "existing_playlist": existing_playlist}


@app.get("/jobs")
def api_list_jobs():
    if _job_store is None:
        return []
    return [_job_to_dict(j) for j in _job_store.list_jobs()]


@app.get("/jobs/{job_id}/stream")
async def api_stream_job(job_id: str):
    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized.")
    job = _job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    logger.debug("SSE subscriber connected: /jobs/%s/stream", job_id)

    async def event_generator():
        # Subscribe first so we don't miss events that fire after we read state.
        q = _job_store.subscribe(job_id)
        try:
            # Send catch-up snapshot for items already past pending.
            current = _job_store.get_job(job_id)
            if current:
                for item in current.items:
                    if item.state != "pending":
                        data = json.dumps({
                            "job_id": job_id,
                            "video_id": item.video_id,
                            "state": item.state,
                            "title": item.title,
                            "renamed_to": item.renamed_to,
                            "error": item.error,
                        })
                        yield f"data: {data}\n\n"
                if current.is_terminal():
                    yield "event: done\ndata: {}\n\n"
                    return

            # Stream live events until terminal sentinel arrives.
            while True:
                event = await q.get()
                if event is None:  # terminal sentinel
                    yield "event: done\ndata: {}\n\n"
                    return
                if event.get("_type") == "progress":
                    payload = {k: v for k, v in event.items() if k != "_type"}
                    yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
                else:
                    yield f"data: {json.dumps(event)}\n\n"
        finally:
            _job_store.unsubscribe(job_id, q)
            logger.debug("SSE subscriber disconnected: /jobs/%s/stream", job_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.delete("/jobs/{job_id}", status_code=204)
def api_delete_job(job_id: str):
    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized.")
    try:
        found = _job_store.delete_job(job_id)
    except ValueError:
        raise HTTPException(status_code=409, detail="Job has items still in progress.")
    if not found:
        raise HTTPException(status_code=404, detail="Job not found.")


@app.put("/jobs/{job_id}/items/{video_id}/rename")
def api_rename_job_item(job_id: str, video_id: str, body: RenameRequest):
    """Rename a downloaded item within a job (single-video or playlist). Updates in-memory state + disk."""
    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized.")
    job = _job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    item = next((i for i in job.items if i.video_id == video_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found in this job.")
    if item.state != "done":
        raise HTTPException(status_code=409, detail="Item must be in done state to rename.")

    new_name = sanitize_name(body.new_name.strip())
    if not new_name:
        raise HTTPException(status_code=422, detail="New name is empty or contains only unsafe characters.")

    # Resolve the file on disk.
    if job.playlist_id is not None:
        playlist = registry.get_playlist_by_id(job.playlist_id)
        if playlist is None:
            raise HTTPException(status_code=404, detail="Playlist not found.")
        base_dir = _resolve_output_dir(playlist["output_dir"])
        safe_folder = sanitize_name(playlist["name"]) or job.playlist_id
        item_dir = os.path.join(base_dir, safe_folder)
    else:
        item_dir = _resolve_output_dir(job.output_dir or _DEFAULT_OUTPUT_DIR)

    old_stem = item.renamed_to or item.title
    old_path = resolve_file_path(item_dir, old_stem)
    if old_path is None:
        raise HTTPException(status_code=404, detail=f"File not found on disk for '{old_stem}'.")

    _, ext = extract_extension(os.path.basename(old_path))
    new_path = os.path.join(item_dir, f"{new_name}{ext}")

    if os.path.exists(new_path) and not os.path.samefile(new_path, old_path):
        raise HTTPException(status_code=409, detail=f"A file named '{new_name}{ext}' already exists.")

    os.rename(old_path, new_path)
    update_title_metadata(new_path, new_name)
    item.renamed_to = new_name
    item.rename_tier = "manual"

    # Also update DB for playlist items.
    if job.playlist_id is not None:
        registry.update_item_rename(video_id, job.playlist_id, new_name)

    return {
        "video_id": item.video_id,
        "title": item.title,
        "renamed_to": item.renamed_to,
        "rename_tier": item.rename_tier,
        "state": item.state,
    }


@app.post("/jobs/cancel-all")
def api_cancel_all_jobs():
    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized.")
    count = _job_store.cancel_all_jobs()
    return {"cancelled": count}


@app.post("/jobs/{job_id}/clear-done", status_code=200)
def api_clear_done_items(job_id: str, all: bool = False):
    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized.")
    removed = _job_store.clear_done_items(job_id, clear_all=all)
    return {"cleared": removed}


@app.post("/jobs/{job_id}/retry-failed")
def api_retry_failed_job(job_id: str):
    if _job_store is None:
        raise HTTPException(status_code=503, detail="Job store not initialized.")
    job = _job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    entries = _job_store.reset_failed_items(job_id)
    if not entries:
        return {"retried": 0}

    row = registry.get_playlist_by_id(job.playlist_id) if job.playlist_id else None
    fmt = row["format"] if row else "mp3"
    quality = (row["quality"] or "best") if row else "best"
    output_dir = (row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR)) if row else _resolve_output_dir(_DEFAULT_OUTPUT_DIR)
    auto_rename = bool(row["auto_rename"]) if row else False
    options = build_options(fmt, quality)
    mb_user_agent = registry.get_setting("mb_user_agent")
    sb_cats = registry.get_sponsorblock_categories(row) if row else list(registry._DEFAULT_SB_CATEGORIES)

    t = threading.Thread(
        target=run_download_job,
        kwargs=dict(
            job_id=job_id,
            entries=entries,
            playlist_id=job.playlist_id,
            playlist_name=job.playlist_name,
            options=options,
            output_dir=output_dir,
            mb_user_agent=mb_user_agent,
            max_workers=_get_max_workers(),
            auto_rename=auto_rename,
            noise_patterns=registry.get_noise_patterns(),
            job_store=_job_store,
            sponsorblock_categories=sb_cats,
        ),
        daemon=True,
    )
    t.start()
    return {"retried": len(entries)}


# ------------------------------------------------------------------
# Internal helpers for API handlers
# ------------------------------------------------------------------

def _resolve_sb_categories_for_create(body) -> Optional[str]:
    """Return the JSON-encoded categories string (or None) to store at create time.

    If sponsorblock_enabled=False → store "" (force-disable).
    If categories explicitly provided → JSON-encode them.
    Otherwise → store None (inherit global at sync time).
    """
    import json as _json
    if not body.sponsorblock_enabled:
        return ""
    if body.sponsorblock_categories is not None:
        return _json.dumps(body.sponsorblock_categories)
    return None


def _resolve_sb_categories_for_job(body) -> Optional[list]:
    """Resolve the effective SponsorBlock category list for a one-off job.

    Jobs have no DB row — resolve directly from the request body then global settings.
    Returns None if SponsorBlock should not be applied.
    """
    import json as _json
    if not body.sponsorblock_enabled:
        return None
    if body.sponsorblock_categories:
        return body.sponsorblock_categories
    # Fall back to global settings
    if registry.get_setting("sponsorblock_enabled") == "false":
        return None
    cats_raw = registry.get_setting("sponsorblock_categories")
    if cats_raw:
        try:
            cats = _json.loads(cats_raw)
            return cats if cats else None
        except Exception:
            pass
    return list(registry._DEFAULT_SB_CATEGORIES)


def _apply_sb_patch(playlist_id: str, body) -> None:
    """Apply sponsorblock_enabled / sponsorblock_categories from a PlaylistPatch."""
    import json as _json
    row = registry.get_playlist_by_id(playlist_id)
    if row is None:
        return
    if body.sponsorblock_enabled is False:
        registry.set_playlist_sponsorblock(playlist_id, "")
        return
    if body.sponsorblock_categories is not None:
        # Empty list → force-disable
        if not body.sponsorblock_categories:
            registry.set_playlist_sponsorblock(playlist_id, "")
        else:
            registry.set_playlist_sponsorblock(playlist_id, _json.dumps(body.sponsorblock_categories))
        return
    if body.sponsorblock_enabled is True:
        # Re-enable: if currently force-disabled, revert to global (NULL)
        if row["sponsorblock_categories"] == "":
            registry.set_playlist_sponsorblock(playlist_id, None)


def _playlist_to_dict(row) -> dict:
    if row is None:
        return {}
    d = dict(row)
    d["item_count"] = registry.count_items(row["id"])
    d["is_syncing"] = row["id"] in _syncing_playlists
    d["sync_info"] = _sync_info.get(row["id"])
    # Expose sponsorblock_enabled as a derived bool for the UI
    sb_cats = d.get("sponsorblock_categories")
    if sb_cats is None:
        # NULL = using global; reflect global enabled state
        d["sponsorblock_enabled"] = registry.get_setting("sponsorblock_enabled") != "false"
    else:
        d["sponsorblock_enabled"] = sb_cats != ""
    return d


def _job_to_dict(job: DownloadJob) -> dict:
    return {
        "job_id": job.job_id,
        "playlist_id": job.playlist_id,
        "playlist_name": job.playlist_name,
        "created_at": job.created_at,
        "auto_rename": job.auto_rename,
        "total": job.total,
        "original_total": job.original_total,
        "done": job.done_count,
        "failed": job.failed_count,
        "items": [
            {
                "video_id": item.video_id,
                "title": item.title,
                "state": item.state,
                "renamed_to": item.renamed_to,
                "rename_tier": item.rename_tier,
                "error": item.error,
            }
            for item in job.items
        ],
    }


# ---------------------------------------------------------------------------
# Static file serving (production only)
# API routes above are registered first; this mount must stay last so it never
# shadows an API path.
# ---------------------------------------------------------------------------

_UI_DIST = os.path.join(os.path.dirname(__file__), "..", "ui", "dist")
if os.path.isdir(_UI_DIST):
    app.mount("/", StaticFiles(directory=_UI_DIST, html=True), name="ui")


# ---------------------------------------------------------------------------
# Internal helpers used by routes and app.py
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
