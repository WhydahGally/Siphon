## 1. Project Scaffolding

- [x] 1.1 Add `.data/` to `.gitignore` at project root
- [x] 1.2 Add `[project.scripts]` entry `siphon = "siphon.watcher:main"` to `pyproject.toml`

## 2. RenameResult and Renamer Changes

- [x] 2.1 Define `RenameResult` dataclass in `renamer.py` with fields: `original_title`, `final_name`, `tier`, `new_path`
- [x] 2.2 Update `_do_rename()` to return the new path so callers can populate `RenameResult.new_path`
- [x] 2.3 Update each tier branch in `rename_file()` to return a `RenameResult` instead of returning `None`
- [x] 2.4 Preserve the early-return `None` path when no filepath is available (existing behaviour)

## 3. ItemRecord and Download Engine Changes

- [x] 3.1 Define `ItemRecord` dataclass in `downloader.py` with fields: `video_id`, `playlist_id`, `yt_title`, `renamed_to`, `rename_tier`, `uploader`, `channel_url`, `duration_secs`
- [x] 3.2 Update `_RenamePostProcessor.run()` to capture the `RenameResult` returned by `rename_file()`
- [x] 3.3 Add `on_item_complete` optional parameter to `download()` and thread it through to `_RenamePostProcessor`
- [x] 3.4 In `_RenamePostProcessor.run()`, build an `ItemRecord` from `info` + `RenameResult` and invoke `on_item_complete` if set; catch and log any callback errors

## 4. Registry Module

- [x] 4.1 Create `src/siphon/registry.py` with `init_db(data_dir)` that creates `.data/`, `.data/archives/`, `.data/.gitignore` (containing `*`), and initialises the three-table schema
- [x] 4.2 Implement `add_playlist(id, name, url)` — raises `ValueError` if already exists
- [x] 4.3 Implement `list_playlists()` — returns all playlists ordered by `added_at`
- [x] 4.4 Implement `get_playlist_by_name(name)` — returns row or `None`
- [x] 4.5 Implement `update_last_synced(playlist_id)`
- [x] 4.6 Implement `insert_item(item_record)` with INSERT OR IGNORE semantics
- [x] 4.7 Implement `find_duplicates()` — returns video IDs appearing in more than one playlist
- [x] 4.8 Implement `set_setting(key, value)` and `get_setting(key)`
- [x] 4.9 Implement `delete_playlist(playlist_id)` — deletes items then playlist row in a single transaction

## 5. CLI Module

- [x] 5.1 Create `src/siphon/watcher.py` with `main()` entry point and `argparse` subparsers for `add`, `sync`, `list`, `delete`, `config`
- [x] 5.2 Implement `cmd_add`: validate URL has `list=` param, call `yt-dlp extract_info` with `download=False` to fetch playlist title and ID, register via registry, print confirmation
- [x] 5.3 Implement `--download` flag on `cmd_add`: after registration, call `download()` with archive path and `on_item_complete` wired to registry `insert_item`
- [x] 5.4 Implement `cmd_sync` (no name arg): iterate all registered playlists, sync each using archive file, persist items, update `last_synced_at`; handle already-up-to-date and unavailable playlist cases
- [x] 5.5 Implement `cmd_sync` (with name arg): look up playlist by name, error with helpful message if not found, then sync that playlist
- [x] 5.6 Implement `cmd_list`: query registry, print formatted table (NAME, URL, ITEMS, LAST SYNCED); handle empty registry
- [x] 5.7 Wire `--format`, `--mb-user-agent`, and `--output-dir` options onto `add` and `sync` subcommands
- [x] 5.9 Add `--quality` arg to `siphon add` (choices: `best`, `2160`, `1080`, `720`, `480`, `360`; default: `best`); persist as `quality` column in `playlists` table; pass through to `_sync_one` and `_build_options` on every sync
- [x] 5.8 Implement `cmd_delete`: look up playlist by name (error if not found), print confirmation prompt with playlist name and item count, on confirm call `registry.delete_playlist()` and delete `.data/archives/<playlist_id>.txt` if it exists, on cancel print "Cancelled."

## 6. Verification

- [x] 6.1 Run `pip install -e .` and confirm `siphon --help` works
- [x] 6.2 Run `siphon add <playlist_url>` on a real playlist, confirm DB row created and name fetched from YT
- [x] 6.3 Run `siphon add <playlist_url> --download --format mp3`, confirm items downloaded and DB populated with `renamed_to` and `rename_tier`
- [x] 6.4 Run `siphon sync` after adding a playlist, confirm "Already up to date." output and `last_synced_at` updated
- [x] 6.5 Run `siphon sync "Nonexistent"` and confirm error message and non-zero exit
- [x] 6.6 Run `siphon list` and confirm table output with correct item counts and timestamps
- [x] 6.7 Confirm `.data/` directory is not tracked by git (gitignore working)
- [x] 6.8 Run `siphon delete <name>`, confirm prompt appears, cancel and verify nothing changed, confirm and verify DB rows and archive file removed but music files intact
