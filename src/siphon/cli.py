"""
siphon.cli — Thin HTTP client commands that talk to the Siphon daemon.

Every subcommand (except ``start``/``watch``) sends HTTP requests to the
daemon running on localhost:8000.
"""
import argparse
import logging
import sys
from typing import Any, Optional

import requests as _requests

from siphon.formats import VALID_AUDIO_FORMATS, VALID_VIDEO_FORMATS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants shared with the daemon
# ---------------------------------------------------------------------------

_ALL_FORMATS = sorted(VALID_AUDIO_FORMATS | VALID_VIDEO_FORMATS)
_DEFAULT_MAX_WORKERS = 5
_MAX_WORKERS_CEILING = 10
_DEFAULT_OUTPUT_DIR_SENTINEL = None  # resolved at argparse time by app.py
_DEFAULT_INTERVAL = 86400  # 24 hours

DAEMON_URL = "http://localhost:8000"


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


def _print_table(rows: list, headers: list, col_widths: list) -> None:
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*[str(v) if v is not None else "never" for v in row]))


# ---------------------------------------------------------------------------
# Daemon HTTP helpers
# ---------------------------------------------------------------------------

def _daemon_get(path: str) -> Any:
    """GET from the daemon. Exits with error if daemon is not reachable."""
    try:
        resp = _requests.get(f"{DAEMON_URL}{path}", timeout=10)
        resp.raise_for_status()
        return resp.json()
    except _requests.exceptions.ConnectionError:
        print("Siphon daemon is not running. Start it with 'siphon start'.", file=sys.stderr)
        sys.exit(1)


def _daemon_post(path: str, json: Optional[dict] = None, *, expect_status: int = 200) -> Any:
    """POST to the daemon. Returns parsed JSON or None for 204."""
    try:
        resp = _requests.post(f"{DAEMON_URL}{path}", json=json or {}, timeout=60)
        if resp.status_code == expect_status:
            return resp.json() if resp.content else None
        _daemon_handle_error(resp)
        return None
    except _requests.exceptions.ConnectionError:
        print("Siphon daemon is not running. Start it with 'siphon start'.", file=sys.stderr)
        sys.exit(1)


def _daemon_delete(path: str) -> None:
    """DELETE on the daemon."""
    try:
        resp = _requests.delete(f"{DAEMON_URL}{path}", timeout=10)
        if resp.status_code not in (200, 204):
            _daemon_handle_error(resp)
    except _requests.exceptions.ConnectionError:
        print("Siphon daemon is not running. Start it with 'siphon start'.", file=sys.stderr)
        sys.exit(1)


def _daemon_patch(path: str, json: dict) -> Any:
    """PATCH on the daemon."""
    try:
        resp = _requests.patch(f"{DAEMON_URL}{path}", json=json, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except _requests.exceptions.ConnectionError:
        print("Siphon daemon is not running. Start it with 'siphon start'.", file=sys.stderr)
        sys.exit(1)


def _daemon_put(path: str, json: dict) -> Any:
    """PUT on the daemon."""
    try:
        resp = _requests.put(f"{DAEMON_URL}{path}", json=json, timeout=10)
        if resp.status_code == 400:
            data = resp.json()
            print(f"Error: {data.get('detail', resp.text)}", file=sys.stderr)
            sys.exit(1)
        resp.raise_for_status()
        return resp.json()
    except _requests.exceptions.ConnectionError:
        print("Siphon daemon is not running. Start it with 'siphon start'.", file=sys.stderr)
        sys.exit(1)


def _daemon_handle_error(resp) -> None:
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text
    print(f"Error: {detail}", file=sys.stderr)
    sys.exit(1)


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
        resp = _requests.post(f"{DAEMON_URL}/playlists", json=body, timeout=120)
    except _requests.exceptions.ConnectionError:
        print("Siphon daemon is not running. Start it with 'siphon start'.", file=sys.stderr)
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


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------

def cmd_cancel(args: argparse.Namespace) -> int:
    result = _daemon_post("/jobs/cancel-all")
    if result is None:
        return 1
    count = result.get("cancelled", 0)
    if count == 0:
        logger.info("No active downloads to cancel.")
    else:
        logger.info("Cancelled %d pending item(s).", count)
    return 0


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

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
# delete-all-playlists
# ---------------------------------------------------------------------------

def cmd_delete_all_playlists(args: argparse.Namespace) -> int:
    playlists = _daemon_get("/playlists")
    count = len(playlists)
    print(f"This will remove all {count} playlist(s) and their sync history from the registry.")
    print("Your downloaded files will NOT be deleted.")
    print()
    answer = input("Confirm? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. No changes made.")
        return 0
    _daemon_delete("/playlists")
    print("All playlists removed.")
    return 0


# ---------------------------------------------------------------------------
# factory-reset
# ---------------------------------------------------------------------------

def cmd_factory_reset(args: argparse.Namespace) -> int:
    print("This will wipe ALL playlists, sync history, and settings.")
    print("Your downloaded files will NOT be deleted.")
    print()
    answer = input("Confirm factory reset? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. No changes made.")
        return 0
    _daemon_post("/factory-reset", expect_status=204)
    print("Factory reset complete.")
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
    "auto-rename": (
        "auto_rename_default",
        "Global default for the auto-rename toggle when adding a new download. "
        "Accepted values: true, false. Default: true.",
    ),
    "theme": (
        "theme",
        "UI colour theme. Accepted values: dark, light. Default: dark.",
    ),
    "browser-logs": (
        "browser_logs",
        "Stream daemon logs to the browser developer console via SSE. "
        "Accepted values: on, off. Default: off.",
    ),
    "title-noise-patterns": (
        "title_noise_patterns",
        "JSON array of regex pattern strings for stripping YouTube title noise "
        "(e.g. '(Official Video)', '[Lyric Video]') from filenames and MB query inputs. "
        "Each string must be a valid Python regex. When unset, built-in defaults are used.",
    ),
}

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}

# Keys whose values must be one of a fixed set.
_ALLOWED_VALUES: dict = {
    "log-level": {"DEBUG", "INFO", "WARNING", "ERROR"},
    "auto-rename": {"true", "false"},
    "theme": {"dark", "light"},
    "browser-logs": {"on", "off"},
}

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
        data = _daemon_get(f"/settings/{key_arg}")
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
    _daemon_put(f"/settings/{key_arg}", {"value": value})
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
        print(f"interval:    {interval if interval is not None else f'{_DEFAULT_INTERVAL} (global default)'}")
        print(f"auto-rename: {bool(match.get('auto_rename', False))}")
        return 0

    if args.key not in _PLAYLIST_KNOWN_KEYS:
        logger.error("Unknown key '%s'. Known keys: %s", args.key, ", ".join(sorted(_PLAYLIST_KNOWN_KEYS)))
        return 1

    if args.value is None:
        # Read mode for a specific key
        if args.key == "interval":
            val = match.get("check_interval_secs")
            print(f"interval: {val if val is not None else f'{_DEFAULT_INTERVAL} (global default)'}")
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
# playlist-items
# ---------------------------------------------------------------------------

def cmd_playlist_items(args: argparse.Namespace) -> int:
    playlists = _daemon_get("/playlists")
    match = next((p for p in playlists if p["name"] == args.name), None)
    if match is None:
        logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", args.name)
        return 1

    items = _daemon_get(f"/playlists/{match['id']}/items")
    if not items:
        print(f"No items downloaded yet for '{args.name}'.")
        return 0

    print(f"{args.name} — {len(items)} item(s)")
    print()
    for item in items:
        if item.get("renamed_to"):
            print(f"  {item['yt_title']} → {item['renamed_to']}")
        else:
            print(f"  {item['yt_title']}")
    return 0


def cmd_rename_item(args: argparse.Namespace) -> int:
    """Rename a downloaded item within a playlist."""
    playlists = _daemon_get("/playlists")
    match = next((p for p in playlists if p["name"] == args.playlist), None)
    if match is None:
        logger.error("No playlist named '%s'. Run 'siphon list' to see registered playlists.", args.playlist)
        return 1

    # Find the item by matching current-name against renamed_to or yt_title.
    items = _daemon_get(f"/playlists/{match['id']}/items")
    item = next(
        (i for i in items if (i.get("renamed_to") or i["yt_title"]) == args.current_name),
        None,
    )
    if item is None:
        logger.error("No item named '%s' in playlist '%s'.", args.current_name, args.playlist)
        return 1

    try:
        resp = _requests.put(
            f"{DAEMON_URL}/playlists/{match['id']}/items/{item['video_id']}/rename",
            json={"new_name": args.new_name},
            timeout=10,
        )
    except _requests.exceptions.ConnectionError:
        print("Siphon daemon is not running. Start it with 'siphon start'.", file=sys.stderr)
        return 1

    if resp.status_code != 200:
        _daemon_handle_error(resp)
        return 1

    print(f'Renamed: "{args.current_name}" → "{args.new_name}"')
    return 0
