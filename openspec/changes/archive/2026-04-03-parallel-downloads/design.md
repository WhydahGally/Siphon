## Context

Siphon currently passes a playlist URL directly to `YoutubeDL.download()`, which processes items sequentially inside yt-dlp's internal loop. There is no opportunity to interleave downloads. The `download_archive` text file is used to track already-downloaded items.

The change makes the download engine item-aware: enumerate playlist entries first via `extract_flat`, then dispatch individual video URLs to a thread pool. The DB replaces the archive file. This unblocks concurrent downloads without requiring a full async rewrite.

This change is designed to stay CLI-first while keeping the path clear for a future long-running server (aiohttp/FastAPI + WebSocket progress events). See `openspec/notes/parallelism-concurrency.md`.

## Goals / Non-Goals

**Goals:**
- Download N items from a playlist concurrently (N configurable, default 5, max 10).
- Use DB as the sole source of truth for "already downloaded" — no archive file.
- Persist per-item failures in DB for later retry via `siphon sync-failed`.
- Provide a multi-slot CLI progress display suitable for parallel output.
- Keep the `download()` function testable in isolation (single video URL in, result out).

**Non-Goals:**
- Long-running server process / daemon mode (future change).
- Per-item cancellation from CLI (future — requires process-based worker isolation).
- Level-A parallelism (multiple playlists concurrently) — not needed for the target use case.
- Playlist-level archive file migration or cleanup tooling.

## Decisions

### D1: ThreadPoolExecutor over ProcessPoolExecutor

**Decision:** Use `concurrent.futures.ThreadPoolExecutor`.

**Rationale:** Downloads are I/O-bound (network + yt-dlp + ffmpeg subprocess). The GIL is not a bottleneck for I/O-bound work. Threads share the MusicBrainz rate-limiting lock and logging context without any IPC overhead. Process spawn cost on macOS (where developers run this) is meaningfully higher than Linux.

**Alternative considered:** `multiprocessing.ProcessPoolExecutor` — rejected for now. Processes are the right call when individual download cancellation from a UI is needed (killing a thread is unsafe; SIGTERM to a process cleanly takes ffmpeg with it). See `openspec/notes/parallelism-concurrency.md` for the future migration path. The worker function is designed to be pure so the switch is a one-line change when needed.

---

### D2: Drop archive file; DB is sole truth

**Decision:** Remove all `download_archive` yt-dlp option usage. The `items` table is authoritative.

**Rationale:** The archive file was yt-dlp's mechanism for deduplication within its own loop. Once we enumerate entries ourselves (D3), we apply the dedup filter before dispatching — yt-dlp never sees already-downloaded IDs. Eliminating the file removes a redundant state store, a class of race conditions (concurrent appends from N threads), and the complexity of managing archive file paths per playlist.

**Migration:** Existing `.data/archives/*.txt` files become inert. No automatic deletion — they can be removed manually. No data is lost since the DB is already the authoritative completed-downloads record.

---

### D3: extract_flat pre-enumeration

**Decision:** Before dispatching to the thread pool, enumerate all playlist entries using `extract_flat=True` (metadata only, no download). Filter the resulting entry list against:
1. Items already in the `items` table for this playlist → skip.
2. Items in the `ignored_items` table → skip silently.
3. Items in `failed_downloads` with `attempt_count >= 3` → skip (log a warning).

Only the remaining entries are dispatched.

**Rationale:** This is the architectural prerequisite for per-item parallelism. It also gives us the total item count upfront (`N of M downloaded`), and puts dedup logic under our control rather than yt-dlp's.

---

### D4: Per-thread SQLite connections with WAL mode

**Decision:** Enable WAL mode on the database. Every write operation (insert item, insert failure, update failure count) opens a short-lived `sqlite3.connect()` in the calling thread with `PRAGMA busy_timeout = 3000`.

**Rationale:** SQLite's default `check_same_thread=True` prevents sharing a single connection across threads. A global write lock would serialize all DB writes and negate the benefit of parallelism. WAL mode allows concurrent readers and serializes writers internally, so no Python-level lock is needed. Short-lived connections are slightly heavier than a shared connection but negligible compared to download latency (milliseconds vs minutes per download).

**Alternative considered:** Shared connection + `threading.Lock()` — rejected because it creates a Python-level bottleneck and requires careful lock management in every write path.

---

### D5: Failure persistence model

**Decision:** Failures are written to a `failed_downloads` table. A failure record is created on first failure and updated (incrementing `attempt_count`) on subsequent failures. A successful retry deletes the record. Records are never automatically cleared by a new sync run.

**Rationale:** The user explicitly chose Option A — records persist until a successful retry clears them. This supports the future UI use case where a user can see all outstanding failures across runs and selectively retry or ignore them.

The `attempt_count` field enables a soft cap: items with `attempt_count >= 3` are skipped by default on regular sync (they still appear in `siphon sync-failed` output for manual retry).

---

### D6: Ignore list design

**Decision:** `ignored_items(video_id, playlist_id, reason, ignored_at)`. `playlist_id` can be NULL for a global ignore (skipped across all playlists). Filter applied at enumeration time, before dispatch.

**Rationale:** The future UI "Ignore" button needs a clean insert target. CLI can expose `siphon ignore <video-id> [--playlist <name>]` in a later change. For now, the table is created and the filter is applied, but no CLI write path is built (the table starts empty).

---

### D7: CLI progress — multi-slot fixed-line renderer

**Decision:** A `ParallelProgressRenderer` holds N fixed display slots (one per worker). Each tick from a worker thread posts a status update to a shared dict (keyed by slot index). A dedicated renderer thread wakes at ~10 Hz, acquires a print lock, moves the cursor up N lines, and redraws all slots.

On completion of each item (success or failure), a "finished" line is printed above the slot area and the slot is cleared.

**Rationale:** Log-per-event floods stdout with interleaved lines from N threads. The fixed-slot approach is clean and readable. The renderer is decoupled from the download hooks — workers post events to a dict, the renderer reads independently. This decoupling is intentional: when the server + UI is built, the renderer is replaced with a WebSocket broadcaster with no changes to the event-posting side.

---

### D8: `siphon sync-failed` design

**Decision:** Two modes:
- `siphon sync-failed <name>` — retry failures for a specific playlist.
- `siphon sync-failed` (no name) — retry failures for all registered playlists.

Internally: query `failed_downloads` for the playlist, dispatch entries through the same parallel engine as `sync`. On success, delete the failure record and insert into `items`. On failure, increment `attempt_count`.

**Rationale:** Consistent with the existing `siphon sync [<name>]` pattern. In the future UI, each sync operation's failure list feeds a per-run retry view; the `failed_downloads` table feeds the per-playlist "retry all failures" button in playlist settings.

## Risks / Trade-offs

**[Thread safety of yt-dlp internals]** yt-dlp is not explicitly documented as thread-safe. Multiple concurrent `YoutubeDL` instances (each in its own thread) accessing shared yt-dlp module-level state could cause subtle issues. → Mitigation: each thread creates its own `YoutubeDL` instance with no shared state. Monitor for issues in testing; fallback is to reduce default max-workers.

**[ffmpeg CPU contention]** With MP3 transcoding (ffmpeg process per item) and max-workers=5, up to 5 ffmpeg processes run simultaneously. On low-CPU systems this could cause slowdowns or OOM. → Mitigation: worker count is user-configurable and defaults to 5, which is safe for most home server hardware. Document in config help text.

**[Partial file on crash]** A kill mid-download leaves a `.part` file on disk. On next sync, yt-dlp resumes from the `.part` file (continuedl=True by default). If the `.part` file is corrupt, yt-dlp may produce a broken output. → Mitigation: yt-dlp's existing error handling + `ignoreerrors=True` covers this. No additional handling needed.

**[extract_flat latency on large playlists]** The `extract_flat` pass hits YouTube's API to enumerate all entries. For a 400-item playlist this is one network request and is fast. For very large playlists (1000+), yt-dlp may paginate. → Acceptable; this was always the case when yt-dlp processed playlists internally.

## Migration Plan

1. Run `siphon sync` after upgrade — the archive file is ignored; the DB is the source of truth. Any item in the archive but not in the DB will be re-downloaded once. Items already in the DB are correctly skipped.
2. Old archive files in `.data/archives/` can be deleted manually. No tooling provided.
3. WAL mode is applied at `init_db()` time — transparent, no user action required.

## Open Questions

*(none — all design decisions resolved in exploration)*

---

## Post-Implementation Additions

The following decisions were made during the verify/fix cycle after initial implementation and are recorded here for completeness.

### D9: Per-playlist `auto_rename` setting

**Decision:** Each playlist row in the `playlists` table stores an `auto_rename INTEGER NOT NULL DEFAULT 0` column. The rename chain is opt-in: disabled by default, enabled via `siphon add --auto-rename`. The setting is read from the DB row on every `sync` and `sync-failed` run — no global override.

**Rationale:** The original `2026-04-02-auto-renamer` change made `auto_rename` an opt-in parameter on `download()` (default `False`). This change preserves that contract while adding per-playlist persistence so the choice does not need to be repeated on every sync. The future UI will expose this as a toggle during `add` and as an editable setting in the library view per playlist.

**Implementation:** `registry.add_playlist()` gains `auto_rename: bool = False`. `siphon add --auto-rename` sets it to `True`. `_sync_one`, `download_parallel`, and `_download_one` all accept and propagate `auto_rename`. Existing DBs migrated via `ALTER TABLE … ADD COLUMN auto_rename INTEGER NOT NULL DEFAULT 0`.

### D10: Output subfolder per playlist

**Decision:** `_download_one` places each item into `<output_dir>/<sanitized_playlist_name>/` rather than directly into `output_dir`. The folder name is the playlist name with filesystem-unsafe characters stripped, falling back to the playlist ID if the sanitized name is empty.

**Rationale:** The original `download()` function places items from a playlist URL into `<output_dir>/<playlist_title>/` via yt-dlp's `%(playlist_title)s` template. In the parallel path, individual video URLs are passed (not the playlist URL), so yt-dlp has no playlist context and would place files flat. The subfolder is created by `_download_one` to match the expected directory structure.

**Implementation:** `_download_one` receives `playlist_name`, computes `safe_folder = renamer.sanitize(playlist_name) or playlist_id`, creates the directory, and passes it as `output_dir` to `download()`. `renamer._sanitize` was renamed to `renamer.sanitize` (public) as part of this change.
