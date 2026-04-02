"""
siphon.watcher — Playlist watcher and CLI entry point.

This module is the main entry point for Siphon. It manages the playlist
registry, drives incremental sync via yt-dlp archive files, and exposes
the `siphon` CLI (add / sync / list / delete / config).

A future UI layer should import from this module to access the same
business logic (add_playlist, sync, list) without going through the CLI.

Global configuration (stored in the DB settings table):
    mb-user-agent   MusicBrainz User-Agent string — set once via
                    `siphon config mb-user-agent "App/1.0 (you@example.com)"`.
                    Used automatically by add and sync for rename lookups.

CLI usage:
    siphon config <key> [<value>]
    siphon add <url> [--download] [--format mp3] [--output-dir ./downloads]
    siphon sync [<name>]
    siphon list
    siphon delete <name>
"""
import os
import sys
import argparse
import logging

from yt_dlp import YoutubeDL

from siphon import registry
from siphon.downloader import download, ItemRecord
from siphon.formats import DownloadOptions, VALID_AUDIO_FORMATS, VALID_VIDEO_FORMATS

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".data")
_DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "downloads")

_ALL_FORMATS = sorted(VALID_AUDIO_FORMATS | VALID_VIDEO_FORMATS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_data_dir() -> str:
    return os.path.abspath(_DATA_DIR)


def _resolve_output_dir(output_dir: str) -> str:
    return os.path.abspath(output_dir)


def _build_options(fmt: str) -> DownloadOptions:
    if fmt in VALID_AUDIO_FORMATS:
        return DownloadOptions(mode="audio", audio_format=fmt)
    return DownloadOptions(mode="video", quality="best", video_format=fmt)


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
            output_dir=_resolve_output_dir(args.output_dir),
        )
    except ValueError:
        print(
            f"Error: Playlist already registered. Use 'siphon sync' to fetch new items.",
            file=sys.stderr,
        )
        return 1

    print(f"Registered: {playlist_name}  (ID: {playlist_id})")

    if args.download:
        print(f"Starting download…")
        mb_user_agent = registry.get_setting("mb_user_agent")
        _sync_one(
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            url=url,
            fmt=args.format,
            output_dir=_resolve_output_dir(args.output_dir),
            mb_user_agent=mb_user_agent,
            data_dir=data_dir,
        )

    return 0


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

def _sync_one(
    playlist_id: str,
    playlist_name: str,
    url: str,
    fmt: str,
    output_dir: str,
    mb_user_agent: str,
    data_dir: str,
) -> None:
    archive = registry.archive_path(playlist_id)
    options = _build_options(fmt)

    def on_item(record: ItemRecord) -> None:
        registry.insert_item(record, playlist_id)

    # Patch yt-dlp opts to use the archive file.
    # We do this by temporarily monkeypatching the download call with extra ydl opts.
    # The cleanest way is to pass download_archive via a wrapper.
    before = registry.count_items(playlist_id)
    _download_with_archive(
        url=url,
        output_dir=output_dir,
        options=options,
        mb_user_agent=mb_user_agent,
        archive=archive,
        on_item_complete=on_item,
    )
    registry.update_last_synced(playlist_id)
    after = registry.count_items(playlist_id)
    new_items = after - before
    if new_items > 0:
        print(f"  {playlist_name}: {new_items} new item(s) added. ({after} total)")
    else:
        print(f"  {playlist_name}: Already up to date. ({after} total)")


def _download_with_archive(
    url: str,
    output_dir: str,
    options: DownloadOptions,
    mb_user_agent: str,
    archive: str,
    on_item_complete,
) -> None:
    """
    Thin wrapper around download() that injects the download_archive yt-dlp option.
    We rebuild the ydl_opts here rather than reach into downloader internals.
    """
    from siphon.formats import build_audio_postprocessors, build_video_format_selector, check_ffmpeg
    from siphon.downloader import _RenamePostProcessor, _YtdlpLogger, _make_hook
    from yt_dlp import YoutubeDL

    ffmpeg_needed = (
        (options.mode == "audio" and options.audio_format == "mp3")
        or (options.mode == "video" and options.video_format in {"mp4", "mkv"})
    )
    if ffmpeg_needed and not check_ffmpeg():
        raise RuntimeError(
            "ffmpeg was not found on PATH. "
            "Install it with: brew install ffmpeg  (macOS) or  apt install ffmpeg  (Linux)."
        )

    is_playlist = "list=" in url or "/playlist" in url
    if is_playlist:
        outtmpl = os.path.join(output_dir, "%(playlist_title)s", "%(title)s.%(ext)s")
    else:
        outtmpl = os.path.join(output_dir, "%(title)s.%(ext)s")

    ydl_opts: dict = {
        "outtmpl": outtmpl,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": False,
        "logger": _YtdlpLogger(),
        "progress_hooks": [_make_hook(options, None)],
        "download_archive": archive,
    }

    if options.mode == "video":
        ydl_opts["format"] = build_video_format_selector(options.quality)
        ydl_opts["merge_output_format"] = options.video_format
    elif options.mode == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = build_audio_postprocessors(options.audio_format)

    with YoutubeDL(ydl_opts) as ydl:
        ydl.add_post_processor(
            _RenamePostProcessor(mb_user_agent, on_item_complete=on_item_complete),
            when="after_move",
        )
        ydl.download([url])


def cmd_sync(args: argparse.Namespace) -> int:
    data_dir = _resolve_data_dir()
    registry.init_db(data_dir)

    playlists = registry.list_playlists()
    if not playlists:
        print("No playlists registered. Use 'siphon add <url>' to add one.")
        return 0

    name_filter = getattr(args, "name", None)

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
        output_dir = row["output_dir"] or _resolve_output_dir(_DEFAULT_OUTPUT_DIR)
        print(f"Syncing '{pname}'…")
        try:
            _sync_one(
                playlist_id=pid,
                playlist_name=pname,
                url=url,
                fmt=fmt,
                output_dir=output_dir,
                mb_user_agent=mb_user_agent,
                data_dir=data_dir,
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
    print(f"Archive:   {registry.archive_path(pid)}")
    print()
    print("This will remove the playlist and its archive file from the registry.")
    print("Your downloaded music files will NOT be deleted.")
    print()
    answer = input("Confirm deletion? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled. No changes made.")
        return 0

    registry.delete_playlist(pid)

    archive = registry.archive_path(pid)
    if os.path.exists(archive):
        os.remove(archive)
        print(f"Deleted archive: {archive}")

    print(f"Deleted playlist '{name}' from registry.")
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
}


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

    # Write mode
    registry.set_setting(db_key, args.value)
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
    p_add.add_argument("--output-dir", default=_DEFAULT_OUTPUT_DIR, help="Root directory for downloads.")

    # -- sync --
    p_sync = sub.add_parser("sync", help="Download new items for registered playlists.")
    p_sync.add_argument("name", nargs="?", default=None, help="Playlist name to sync (default: all).")

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
        "list": cmd_list,
        "delete": cmd_delete,
        "config": cmd_config,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
