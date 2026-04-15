## 1. Registry — Schema & WAL

- [x] 1.1 Enable WAL mode in `registry.init_db()` via `PRAGMA journal_mode=WAL`
- [x] 1.2 Add `PRAGMA busy_timeout = 3000` to all per-thread write helpers
- [x] 1.3 Add `failed_downloads` table to `_SCHEMA` (video_id, playlist_id, yt_title, url, error_message, attempt_count, last_attempted_at)
- [x] 1.4 Add `ignored_items` table to `_SCHEMA` (video_id, playlist_id, reason, ignored_at)
- [x] 1.5 Add schema migration stmts in `init_db()` for both new tables on existing DBs
- [x] 1.6 Remove `.data/archives/` directory creation from `init_db()`
- [x] 1.7 Remove `archive_path()` function

## 2. Registry — New Write/Read Helpers

- [x] 2.1 Implement `insert_failed(video_id, playlist_id, yt_title, url, error_message)` — upsert with `attempt_count` increment
- [x] 2.2 Implement `get_failed(playlist_id) -> list[Row]` — query all failures for a playlist
- [x] 2.3 Implement `clear_failed(video_id, playlist_id)` — delete on successful retry
- [x] 2.4 Implement `insert_ignored(video_id, playlist_id=None, reason=None)` — INSERT OR IGNORE
- [x] 2.5 Implement `is_ignored(video_id, playlist_id) -> bool` — check global + playlist-scoped rows
- [x] 2.6 Update `insert_item()` to open a short-lived per-call connection (remove reliance on module-level `_conn` for writes from threads)
- [x] 2.7 Update `delete_playlist()` to also delete rows from `failed_downloads` and `ignored_items` for the deleted playlist

## 3. Download Engine — Thread Safety

- [x] 3.1 Confirm `download()` creates a fresh `YoutubeDL` instance per call (no shared yt-dlp state) — add a comment documenting thread-safety contract
- [x] 3.2 Remove `download_archive` option from `_build_ydl_opts()` (no archive file written)
- [x] 3.3 Remove `_download_with_archive()` from `watcher.py`

## 4. Parallel Download Engine — Core

- [x] 4.1 Implement `enumerate_entries(url) -> list[dict]` in `watcher.py` — uses `extract_flat=True`, returns list of entry dicts
- [x] 4.2 Implement pre-dispatch filter: exclude entries already in `items`, in `ignored_items`, and in `failed_downloads` with `attempt_count >= 3` (log WARNING for the last group)
- [x] 4.3 Define `FailureRecord` dataclass (video_id, title, url, error_message)
- [x] 4.4 Implement `download_parallel(entries, options, ..., max_workers) -> (list[ItemRecord], list[FailureRecord])` — `ThreadPoolExecutor`, submits one future per entry
- [x] 4.5 Implement single-entry worker function `_download_one(entry, options, output_dir, mb_user_agent) -> ItemRecord` — calls `download()` with the entry's video URL, extracts `ItemRecord` from `on_item_complete` callback
- [x] 4.6 In `_download_one`: on success write to DB via `registry.insert_item()` (short-lived connection), call `registry.clear_failed()` if a failure record existed
- [x] 4.7 In `_download_one`: on exception write failure via `registry.insert_failed()`, re-raise or return a sentinel so the caller can collect the `FailureRecord`
- [x] 4.8 Collect results from all futures; aggregate into `(successes, failures)` lists

## 5. Progress Display — Parallel Renderer

- [x] 5.1 Implement `ParallelProgressRenderer` class: holds N slots (one per worker), a shared dict of latest status per slot, a `threading.Lock` for terminal writes
- [x] 5.2 Implement renderer background thread: wakes at ~10 Hz, draws all slots using ANSI cursor-up
- [x] 5.3 Implement slot-bound progress callback factory: `make_slot_callback(slot_index, renderer) -> Callable` — posts to renderer's slot dict
- [x] 5.4 Implement completed-item print: on success print `✓ <filename>` above slot area; on failure print `✗ <title> — <error>` above slot area
- [x] 5.5 Implement overall progress line: `Syncing '<name>': X / N downloaded` — updated on each item completion
- [x] 5.6 Ensure renderer stops cleanly when all slots are idle (no dangling background thread)
- [x] 5.7 Remove old single-slot `\r` progress callback (`_make_cli_progress_callback()`) or keep for standalone `download()` use outside of sync

## 6. Watcher — Sync Command Rewrite

- [x] 6.1 Rewrite `_sync_one()` to: call `enumerate_entries()`, apply pre-dispatch filter, call `download_parallel()`, write archive IDs to disk at end (success cases only)
- [x] 6.2 Wire `ParallelProgressRenderer` into `_sync_one()` — create renderer with `max_workers` slots, pass slot callbacks to `download_parallel()`
- [x] 6.3 Read `max-concurrent-downloads` from registry settings in `_sync_one()`; default to 5 if unset
- [x] 6.4 After parallel run completes: print failure summary if any failures exist (title + error per item)
- [x] 6.5 Update `cmd_add --download` path to use `download_parallel()` instead of the old serial `download()` call

## 7. Watcher — `sync-failed` Command

- [x] 7.1 Implement `cmd_sync_failed(args)` in `watcher.py`
- [x] 7.2 Handle no-argument case: iterate all playlists, skip those with no failures
- [x] 7.3 Handle named playlist case: resolve playlist by name, error if not found
- [x] 7.4 For each playlist with failures: call `registry.get_failed(playlist_id)`, convert rows to entry dicts, dispatch via `download_parallel()`
- [x] 7.5 Register `sync-failed` subcommand in the CLI argument parser (`argparse`)

## 8. Config — `max-concurrent-downloads` Key

- [x] 8.1 Add `max-concurrent-downloads` to the known config keys list in `watcher.py`
- [x] 8.2 Add validation: must be integer, 1–10 inclusive; print error and exit non-zero on invalid value
- [x] 8.3 Add key to the help text / error message listing known keys

## 9. Registry — Delete Cleanup

- [x] 9.1 Update `delete_playlist()` to delete from `failed_downloads` and `ignored_items` in the same transaction as `items` and `playlists` row deletion
- [x] 9.2 Remove archive file deletion from `cmd_delete` in `watcher.py`

## 10. Testing & Validation

- [x] 10.1 Smoke test: `siphon sync` on a small playlist (3–5 items) with `max-concurrent-downloads 3` — verify all items download and appear in DB
- [x] 10.2 Verify no `.data/archives/` directory is created on a fresh install
- [x] 10.3 Verify `siphon sync` on already-synced playlist shows `Already up to date.` without re-downloading
- [x] 10.4 Simulate a failure (invalid video URL in test playlist) — verify `failed_downloads` row is created and failure report is printed
- [x] 10.5 Run `siphon sync-failed <name>` after the above — verify retry attempt increments `attempt_count` on second failure
- [x] 10.6 Verify `siphon config max-concurrent-downloads 3` persists and is used by next sync
- [x] 10.7 Verify `siphon delete <name>` removes all associated `failed_downloads` rows
- [x] 10.8 Verify progress display renders cleanly with N concurrent downloads (no garbled output)
