## Why

Downloads within a playlist are currently sequential — each item waits for the previous to complete before starting. On a large playlist this makes the sync operation unnecessarily slow given that the bottleneck is network I/O, not CPU. We also have no visibility into what failed during a sync or any way to retry failures.

## What Changes

- Replace yt-dlp's internal playlist-loop with an `extract_flat` pre-enumeration step so individual video URLs can be dispatched independently.
- Dispatch playlist items to a `ThreadPoolExecutor` for concurrent downloads (configurable worker count, default 5, max 10).
- **BREAKING**: Remove yt-dlp `download_archive` file management. The `items` DB table becomes the sole truth for what has been downloaded. Existing archive files are no longer read or written.
- Add WAL mode to SQLite and open a short-lived per-thread connection for every DB write, removing all `check_same_thread` constraints.
- Add a `failed_downloads` table to the registry to persist per-item download failures. Failures are kept until a successful retry clears them.
- Add an `ignored_items` table to the registry so users can mark specific videos to be permanently skipped on future syncs.
- Add `siphon sync-failed [<name>]` CLI command to retry all persisted failures for a playlist (or all playlists).
- Replace the single-line `\r` CLI progress with a multi-slot fixed-line display: one line per active download, updated in place using ANSI cursor movement.
- Add `max-concurrent-downloads` to the `siphon config` key space (integer, default 5, validated 1–10).

## Capabilities

### New Capabilities
- `parallel-download-engine`: Concurrent per-item download dispatcher — extract_flat enumeration, ThreadPoolExecutor execution, per-thread DB connections, aggregate result collection.
- `failed-downloads`: Persistence and retry of per-item download failures. Includes DB schema, failure recording on error, and `siphon sync-failed` command.
- `ignored-items`: DB-backed ignore list. Items on the list are silently skipped during sync enumeration. Designed for UI-facing "ignore" action (future).

### Modified Capabilities
- `download-engine`: Removes archive-file dependency; `download()` now operates on a single video URL rather than a playlist URL; added concurrency context (called from thread pool).
- `playlist-registry`: New tables (`failed_downloads`, `ignored_items`), WAL mode, archive path helpers removed, new write helpers for failures and ignore list.
- `playlist-watcher-cli`: `sync` command redesigned around parallel engine; new `sync-failed` command; `max-concurrent-downloads` config key; progress display replaced.
- `progress-events`: CLI progress renderer replaced with multi-slot parallel display; progress event type unchanged but renderer is concurrency-aware.

## Impact

- `src/siphon/downloader.py` — `download()` signature change (single video URL, no archive), `_download_with_archive` removed.
- `src/siphon/watcher.py` — `_sync_one` and `_download_with_archive` replaced; new parallel engine logic; new `cmd_sync_failed`.
- `src/siphon/registry.py` — WAL pragma, new tables, archive helpers removed, new `insert_failed`, `get_failed`, `clear_failed`, `insert_ignored`, `is_ignored` functions.
- `requirements.txt` — no new dependencies (stdlib `concurrent.futures`, `threading`, `sqlite3`).
- Existing `.data/archives/` files — no longer written; existing files are inert and can be deleted manually.
