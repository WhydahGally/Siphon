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

### D1: Per-item output via logger, ordered within each item

**Decision:** `_download_one` emits all result lines via `logger.info`/`logger.warning` after `download()` returns. On success: `✓ <filename>  [<size> · <elapsed>s]` first, then `Renamed: "<original>" → "<final>"  [<tier>]` if auto_rename is active. On failure: `✗ <title> — <error>`.

**Rationale:** All output goes through the logging system — timestamps, log level, and logger name are consistent across every line. The `✓` and `Renamed:` lines for the same item are always in the correct order because they are emitted sequentially from `_download_one` after `download()` returns. Cross-item interleaving is best-effort (see Risks).

**Alternative considered:** A shared `threading.Lock` + `print()` grouped output — initially implemented, then removed to eliminate duplicate output caused by renamer also emitting independently. The current approach avoids duplication by keeping all emission in `_download_one` using `ItemRecord.rename_tier`/`renamed_to` (populated by the PostProcessor).

---

### D2: Size and elapsed time from ItemRecord / exception timing

**Decision:** `_download_one` records `time.monotonic()` at entry and at completion to compute elapsed seconds. File size is read with `os.path.getsize()` on `record.rename_result.new_path` (or `renamed_to` resolved to disk), falling back to "?" if unavailable. Both are appended to the success output line.

**Rationale:** Elapsed time catches slow downloads without needing a live display. Size confirms something real was written. Both are available after the download completes without any changes to `downloader.py`.

---

### D3: Rename outcome logged from `_download_one` via `ItemRecord`

**Decision:** After `download()` returns, `_download_one` reads `record.rename_tier` and `record.renamed_to` from the `ItemRecord` (populated by the PostProcessor inside `download()`) and emits the `Renamed:` line. The four `logger.debug("renamer: tier X resolved…")` calls in `renamer.py` remain at DEBUG level.

**Rationale:** `ItemRecord` already carries all the rename outcome data needed for the log line. Emitting from `_download_one` avoids coupling renamer to the parallel engine and keeps renamer's own logging at DEBUG where it belongs. The rename tier and names are visible at INFO level via the `_download_one` log without any changes to renamer internals.

**Open question:** There is a desire to have the rename log originate from `siphon.renamer` in the logger name (for filtering). This is deferred — rework pending.

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
