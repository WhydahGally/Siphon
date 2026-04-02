## Why

Siphon downloads playlists as one-shot operations — there is no way to keep a local copy in sync as new videos are added to a YouTube playlist. Users must manually re-run downloads and risk duplicates or missed items.

## What Changes

- Introduce a `.data/` folder at the project root to store persistent, git-ignored state: the SQLite registry (`siphon.db`) and per-playlist yt-dlp archive files.
- Add a SQLite registry (`siphon.db`) created on first startup, storing registered playlists, per-item download records (original YT title, renamed filename, rename tier, metadata), and a settings table for future use.
- Add a CLI entry point (`siphon`) with four subcommands: `add`, `sync`, `list`.
- `siphon add <url>` registers a playlist (fetches its name from YT); `--download` flag triggers an immediate full download.
- `siphon sync [name]` fetches new items for one or all registered playlists and downloads only what's new, using both a yt-dlp archive file and the DB.
- `siphon list` shows all registered playlists with their item counts and last synced time.
- Modify the renamer to return a `RenameResult` (original title, final name, tier) instead of `None`, so the downloader can capture and persist rename outcomes.
- Add an `on_item_complete` callback to `download()` so callers can receive per-item records after rename, without coupling the download engine to storage.

## Capabilities

### New Capabilities

- `playlist-registry`: SQLite-backed registry of watched playlists and downloaded items, created on first startup at `.data/siphon.db`. Stores playlist metadata, per-item download records, and a settings table.
- `playlist-watcher-cli`: `siphon` CLI entry point with `add`, `sync`, and `list` subcommands. Manages the registry, drives yt-dlp archive-based incremental sync, handles error cases (non-existent playlist, deleted/privated playlist, already up-to-date).

### Modified Capabilities

- `auto-renamer`: `rename_file()` currently returns `None`. It will now return a `RenameResult` dataclass containing `original_title`, `final_name`, `tier`, and `new_path`.
- `download-engine`: `download()` gains an `on_item_complete` callback parameter. `_RenamePostProcessor` captures the `RenameResult` and invokes the callback with a populated `ItemRecord`.

## Impact

- `src/siphon/renamer.py`: `rename_file()` signature changes (return type `None` → `RenameResult`). **BREAKING** for any caller expecting no return value — currently only `_RenamePostProcessor`.
- `src/siphon/downloader.py`: `download()` gains optional `on_item_complete` parameter; `_RenamePostProcessor.run()` updated to capture and forward `RenameResult`.
- `src/siphon/cli.py`: New file. Entry point for `siphon` command.
- `src/siphon/registry.py`: New file. SQLite schema init, playlist CRUD, item insert, duplicate detection.
- `.data/`: New git-ignored folder. Created at runtime. Contains `siphon.db` and `archives/<playlist_id>.txt`.
- `pyproject.toml`: Add `[project.scripts]` entry: `siphon = "siphon.cli:main"`.
- No new third-party dependencies (uses stdlib `sqlite3` and `argparse`).
