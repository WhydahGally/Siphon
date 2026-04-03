## Why

The `2026-04-03-parallel-downloads` change introduced a `ParallelProgressRenderer` — a background render thread using ANSI cursor rewrites — to display live per-slot download progress. This is overkill for a CLI whose primary audience is the developer debugging locally. The renderer added ~130 lines of complexity, required a threading lock and a 10 Hz redraw loop, and suppressed useful logs (e.g. rename tier) in favour of live byte-progress meters that are not needed. The future interface for end users will be a UI, not the CLI.

## What Changes

- **Remove** `ParallelProgressRenderer` class and all supporting infrastructure (`_make_slot_callback`, `_make_cli_progress_callback`) from `watcher.py`.
- **Replace** the per-slot live display with plain append-only print lines, grouped per download item and flushed atomically when the item completes (via a shared `threading.Lock`).
- **Print a planned-items list** in `_sync_one` before downloads begin: the filtered entries list (already computed from `extract_flat`) is printed as a numbered list of titles.
- **Print a per-item result block** when each item finishes: success line with file size and time taken, or failure line with error message.
- **Add one `logger.info` call** in `renamer.rename_file` to log the old name, new name, and tier used. All other renamer logs stay at `DEBUG`.
- **Delete dead code**: `_make_cli_progress_callback` is currently unreferenced and will be removed.

## Capabilities

### New Capabilities

*(none — this change removes a capability and replaces it with simpler behaviour)*

### Modified Capabilities

- `download-engine`: The `progress_callback` parameter is no longer used in the parallel sync path (passed as `None`). The `_download_one` worker signature changes to remove `slot_index` and `renderer`, gaining `print_lock` instead.
- `parallel-download-engine`: `download_parallel` no longer creates or manages a `ParallelProgressRenderer`. Output is plain log lines grouped per item.
- `playlist-watcher-cli`: CLI output changes from a live rewriting display to a sequential log format: planned items list → per-item result blocks as they complete → summary line.

## Impact

- `src/siphon/watcher.py` — primary change file; ~130 lines of renderer code deleted, `_download_one` and `download_parallel` signatures updated.
- `src/siphon/renamer.py` — one `logger.debug` at the point of successful rename replaced with `logger.info`.
- `src/siphon/progress.py` — no changes; `ProgressEvent` and `make_progress_event` remain (used by `downloader.py`'s hook).
- `src/siphon/downloader.py` — no changes.
- No new dependencies. No CLI flags added or removed.
