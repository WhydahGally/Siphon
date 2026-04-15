## Context

`watcher.py` currently contains a `ParallelProgressRenderer` — a background daemon thread that rewrites N terminal lines at 10 Hz using ANSI cursor-up sequences, giving a live per-slot view of concurrent downloads (speed, percentage, ETA). This was designed to look polished during parallel downloads, but the CLI's actual job is developer debugging. The renderer suppresses useful observability (rename tier, error detail), adds ~130 lines of non-trivial threading code, and provides value only for an audience (end users watching a terminal) who will eventually use a UI instead. The change removes it entirely and replaces it with append-only, per-item log lines.

## Goals / Non-Goals

**Goals:**
- Print a numbered list of items planned for download before any download starts.
- Emit a result log per item when it completes — success (filename, size, time) or failure (title, error message) — via `logger.info` / `logger.warning`.
- Surface rename outcomes (old name → new name, tier) at INFO level from `_download_worker` in `watcher.py`.
- Delete all renderer-related code and dead helpers.

**Non-Goals:**
- Live progress (percentage, speed, ETA).
- A `--verbose` flag (log level flags already exist).
- Any changes to `downloader.py` or `progress.py`.
- Changing the parallel execution model (ThreadPoolExecutor stays).

## Decisions

### D1: Per-item output via sequential logger calls (no lock)

**Decision:** `_download_worker` calls `logger.info` / `logger.warning` directly for each output line — one call for the `✓` / `✗` line and, when a rename occurred, a second `logger.info` call for the rename line. No shared lock and no line accumulation. The `threading` import is removed from `watcher.py`.

**Rationale:** Each individual `logging` call is serialised internally by the logging framework (the root handler acquires its own lock). Rare interleaving between the two log lines of a single item is acceptable for a debug-focused CLI — the planned-items list printed at the top gives a full ordered view before anything starts. Eliminating the lock and line-list simplifies the code with no meaningful cost to readability.

**Alternative considered:** A shared `threading.Lock` with line accumulation — prototyped and then reverted; the added complexity was not justified for a debug tool.

---

### D2: Size and elapsed time from ItemRecord / exception timing

**Decision:** `_download_worker` records `time.monotonic()` at entry and at completion to compute elapsed seconds. File size is read with `os.path.getsize()` on `record.rename_result.new_path` (or `renamed_to` resolved to disk), falling back to "?" if unavailable. Both are appended to the success output line.

**Rationale:** Elapsed time catches slow downloads without needing a live display. Size confirms something real was written. Both are available after the download completes without any changes to `downloader.py`.

---

### D3: Rename outcome logged at INFO level from `_download_worker` in `watcher.py`

**Decision:** After `download()` returns, `_download_worker` checks `record.rename_tier`; if a rename occurred it calls `logger.info('    Renamed: "%s" → "%s"  [%s]', yt_title, renamed_to, tier)`. The four `logger.debug("renamer: tier X resolved…")` calls inside `renamer.rename_file()` remain unchanged at DEBUG level.

**Rationale:** Surfacing rename info from `_download_worker` avoids a duplicate-log problem: if `renamer.py` emits INFO and `_download_worker` also logs the same data, the user sees two rename lines per item. Keeping renamer at DEBUG and logging from `_download_one` once — after all post-processing is complete — is the simpler, cleaner approach. The rename tier and final path are available on `ItemRecord` after `download()` returns.

**Alternative considered:** Single `logger.info` inside `renamer.rename_file()` — prototyped and then reverted due to the duplicate-log issue when combined with the `_download_worker` output path.

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
