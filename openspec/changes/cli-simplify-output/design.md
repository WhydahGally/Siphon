## Context

`watcher.py` currently contains a `ParallelProgressRenderer` — a background daemon thread that rewrites N terminal lines at 10 Hz using ANSI cursor-up sequences, giving a live per-slot view of concurrent downloads (speed, percentage, ETA). This was designed to look polished during parallel downloads, but the CLI's actual job is developer debugging. The renderer suppresses useful observability (rename tier, error detail), adds ~130 lines of non-trivial threading code, and provides value only for an audience (end users watching a terminal) who will eventually use a UI instead. The change removes it entirely and replaces it with append-only, per-item log lines.

## Goals / Non-Goals

**Goals:**
- Print a numbered list of items planned for download before any download starts.
- Print a result block per item when it completes — success (filename, size, time) or failure (title, error message) — grouped and flushed atomically so lines from concurrent threads do not interleave.
- Add one `logger.info` in the renamer so rename outcomes (old name → new name, tier) surface at INFO level without requiring DEBUG.
- Delete all renderer-related code and dead helpers.

**Non-Goals:**
- Live progress (percentage, speed, ETA).
- A `--verbose` flag (log level flags already exist).
- Any changes to `downloader.py` or `progress.py`.
- Changing the parallel execution model (ThreadPoolExecutor stays).

## Decisions

### D1: Per-item output grouped with a print lock

**Decision:** `_download_one` accumulates all output lines for one item into a local `list[str]`, then acquires a shared `threading.Lock` and prints them all in one block before releasing. The lock is created in `download_parallel` and passed into each worker.

**Rationale:** With N threads printing independently, individual `print()` calls from different threads can interleave at the line boundary (two threads' lines mixed together), but not within a single `print()` call (the GIL makes individual writes atomic on CPython). Grouping all lines for one item and holding the lock for the duration of the entire group guarantees clean, readable output — all lines for item A, then all lines for item B, regardless of completion order.

**Alternative considered:** A shared queue with a single dedicated printer thread — rejected as unnecessary complexity for what is just `print()` calls.

---

### D2: Size and elapsed time from ItemRecord / exception timing

**Decision:** `_download_one` records `time.monotonic()` at entry and at completion to compute elapsed seconds. File size is read with `os.path.getsize()` on `record.rename_result.new_path` (or `renamed_to` resolved to disk), falling back to "?" if unavailable. Both are appended to the success output line.

**Rationale:** Elapsed time catches slow downloads without needing a live display. Size confirms something real was written. Both are available after the download completes without any changes to `downloader.py`.

---

### D3: One `logger.info` in renamer, at the point of successful rename

**Decision:** Replace the four separate `logger.debug("renamer: tier X resolved…")` calls in `rename_file` with a single `logger.info` call emitted after the `RenameResult` is constructed, containing original title, final name, and tier. All other renamer log calls stay at `DEBUG`.

**Rationale:** The tier and names are only known after resolution succeeds. A single INFO-level log at that point is the minimal change: it surfaces the rename outcome when the caller runs with `--log-level info` (or the default if INFO is the floor), and costs nothing extra for callers running at WARNING or above.

**Note:** The CLI print path in `_download_one` also prints rename info from `ItemRecord.rename_tier` and `ItemRecord.renamed_to` — that is independent of this log. The INFO log covers file-based and piped-log use cases; the print covers interactive terminal use.

---

### D4: `_make_cli_progress_callback` removed (dead code)

**Decision:** Delete `_make_cli_progress_callback` without replacement.

**Rationale:** It is defined in `watcher.py` with the comment "Not used in the parallel sync path" and has no callers in the codebase. It implemented the same `\r` cursor-overwrite pattern as the renderer; deleting it is consistent with the goal of removing all in-place-rewrite output.

## Risks / Trade-offs

**[Output order is completion order, not playlist order]** Items print as threads finish, which may differ from playlist order. → Acceptable — the planned-items list at the top is in playlist order, giving the user the full ordered view before any downloads start. Completion order is genuinely more useful for debugging (you see what finished first).

**[No live feedback during long downloads]** A 200 MB video download shows nothing to the terminal until it completes. → Acceptable for the stated use case (debugging, not watching). If this becomes a pain point, a simple `logger.debug` from the yt-dlp progress hook already emits per-tick data at DEBUG level.

**[Print lock is a Python-level bottleneck on completion]** All N threads contend on the lock when they finish. → Negligible: the lock is held only for the duration of 2–4 `print()` calls per item, measured in microseconds against download times measured in seconds or minutes.

## Migration Plan

No data migration required. No CLI flags change. The only user-visible difference is the terminal output format during `siphon sync` and `siphon sync-failed`.
