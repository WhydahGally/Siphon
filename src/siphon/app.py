"""
siphon.app — Entry point for the Siphon CLI.

``siphon start`` launches the FastAPI daemon; all other subcommands are thin
HTTP clients defined in :mod:`siphon.cli`.
"""
import argparse
import logging
import logging.handlers
import os
import sys

from siphon import registry
from siphon.formats import VALID_AUDIO_FORMATS, VALID_VIDEO_FORMATS, VALID_RESOLUTIONS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".data")
_DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")
_ALL_FORMATS = sorted(VALID_AUDIO_FORMATS | VALID_VIDEO_FORMATS)


def _resolve_data_dir() -> str:
    return os.path.abspath(_DATA_DIR)


# ---------------------------------------------------------------------------
# siphon start — daemon entry point
# ---------------------------------------------------------------------------

def cmd_start(_args: argparse.Namespace) -> int:
    import uvicorn
    from siphon.api import app

    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
    )
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    from siphon.cli import (
        cmd_add, cmd_cancel, cmd_sync, cmd_sync_failed, cmd_list,
        cmd_delete, cmd_delete_all_playlists, cmd_factory_reset,
        cmd_config, cmd_config_playlist, cmd_playlist_items,
        cmd_rename_item, _KNOWN_KEYS,
    )
    from siphon.api import _SSELogHandler

    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.WARNING,
        format=log_format,
        stream=sys.stderr,
    )

    # Apply log-level from DB if already set; fall back to INFO on a fresh install.
    try:
        stored_level = registry.get_setting("log_level") or "INFO"
    except RuntimeError:
        stored_level = "INFO"
    siphon_logger = logging.getLogger("siphon")
    siphon_logger.setLevel(getattr(logging, stored_level, logging.INFO))

    # Rolling log file — 5 MB max, 1 backup, alongside the DB.
    data_dir = _resolve_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(data_dir, "siphon.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=1,
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    siphon_logger.addHandler(file_handler)

    # SSE log handler for browser console streaming.
    sse_handler = _SSELogHandler()
    sse_handler.setFormatter(logging.Formatter("%(message)s"))
    siphon_logger.addHandler(sse_handler)

    # Cache browser-logs setting.
    import siphon.api as _api
    try:
        _api._browser_logs_enabled = registry.get_setting("browser_logs") == "on"
    except RuntimeError:
        _api._browser_logs_enabled = False

    parser = argparse.ArgumentParser(
        prog="siphon",
        description="Siphon — manage and sync local copies of YouTube playlists.",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # -- start --
    sub.add_parser("start", help="Start the Siphon daemon (required for all other commands).")

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
    p_add.add_argument("--sponsorblock", dest="sponsorblock", action="store_true", default=False,
                       help="Enable SponsorBlock segment removal for this playlist.")

    # -- cancel --
    sub.add_parser("cancel", help="Cancel all active download jobs.")

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

    # -- delete-all-playlists --
    sub.add_parser("delete-all-playlists", help="Remove all playlists and sync history from the registry.")

    # -- factory-reset --
    sub.add_parser("factory-reset", help="Wipe all playlists, history, and settings. Downloaded files are not affected.")

    # -- config --
    p_cfg = sub.add_parser("config", help="Get or set a global configuration value.")
    p_cfg.add_argument("key", choices=list(_KNOWN_KEYS) + ["cookie-file"], help="Config key to read or write.")
    p_cfg.add_argument("value", nargs="?", default=None, help="Value to set. Omit to read the current value.")

    # -- config-playlist --
    p_cfgp = sub.add_parser("config-playlist", help="Get or set a per-playlist configuration value.")
    p_cfgp.add_argument("name", help="Playlist name to configure.")
    p_cfgp.add_argument("key", nargs="?", default=None, metavar="key",
                        help="Setting to read or write: interval, auto-rename, watched, sponsorblock, sb-cats, cookies. Omit to show all.")
    p_cfgp.add_argument("value", nargs="?", default=None, help="Value to set. Omit to read the current value.")

    # -- playlist-items --
    p_pi = sub.add_parser("playlist-items", help="List all downloaded items for a playlist.")
    p_pi.add_argument("name", help="Name of the playlist.")

    # -- rename-item --
    p_ri = sub.add_parser("rename-item", help="Rename a downloaded item in a playlist.")
    p_ri.add_argument("playlist", help="Name of the playlist.")
    p_ri.add_argument("current_name", metavar="current-name", help="Current name of the item (renamed_to or title).")
    p_ri.add_argument("new_name", metavar="new-name", help="New name for the item.")

    args = parser.parse_args()

    dispatch = {
        "start": cmd_start,
        "add": cmd_add,
        "cancel": cmd_cancel,
        "sync": cmd_sync,
        "sync-failed": cmd_sync_failed,
        "list": cmd_list,
        "delete": cmd_delete,
        "delete-all-playlists": cmd_delete_all_playlists,
        "factory-reset": cmd_factory_reset,
        "config": cmd_config,
        "config-playlist": cmd_config_playlist,
        "playlist-items": cmd_playlist_items,
        "rename-item": cmd_rename_item,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
