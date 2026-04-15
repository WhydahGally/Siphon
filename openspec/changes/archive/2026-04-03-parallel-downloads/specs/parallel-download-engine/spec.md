## ADDED Requirements

### Requirement: Playlist entry enumeration
The parallel engine SHALL enumerate all entries in a playlist before dispatching downloads. It SHALL use `extract_flat=True` to fetch only metadata (video IDs, titles, URLs) without downloading content.

#### Scenario: Playlist URL with entries
- **WHEN** a playlist URL is passed to the engine
- **THEN** the engine SHALL return a flat list of entry dicts (each with at minimum `id`, `url`, `title`)
- **THEN** no video content SHALL be downloaded during this step

#### Scenario: Empty or unavailable playlist
- **WHEN** `extract_flat` returns no entries or the playlist is unavailable
- **THEN** the engine SHALL log a warning and return an empty list without error

---

### Requirement: Pre-dispatch filtering
Before dispatching to the thread pool, the engine SHALL filter entries against the DB to skip work that does not need to be done.

#### Scenario: Entry already in items table
- **WHEN** a video ID from `extract_flat` already exists in the `items` table for that playlist
- **THEN** the engine SHALL skip that entry without dispatching it

#### Scenario: Entry in ignored_items table
- **WHEN** a video ID from `extract_flat` exists in `ignored_items` (either for this playlist or globally)
- **THEN** the engine SHALL skip that entry silently — no log, no download

#### Scenario: Entry in failed_downloads with attempt_count >= 3
- **WHEN** a video ID from `extract_flat` exists in `failed_downloads` with `attempt_count >= 3`
- **THEN** the engine SHALL skip that entry on regular sync and log a WARNING indicating it must be retried manually via `siphon sync-failed`

#### Scenario: Entry not in any exclusion list
- **WHEN** a video ID from `extract_flat` does not appear in `items`, `ignored_items`, or `failed_downloads` with count >= 3
- **THEN** the engine SHALL include it in the dispatch batch

---

### Requirement: Concurrent dispatch via thread pool
The engine SHALL dispatch filtered entries to a `ThreadPoolExecutor` with a configurable number of workers.

#### Scenario: Workers bounded by max-concurrent-downloads
- **WHEN** N entries are dispatched and `max-concurrent-downloads` is set to W
- **THEN** at most W downloads SHALL run simultaneously at any point in time

#### Scenario: Single failure does not stop other workers
- **WHEN** one worker thread encounters a download error
- **THEN** all other worker threads SHALL continue to completion unaffected

#### Scenario: All entries dispatched before any completes
- **WHEN** the thread pool is initialized with W workers and N > W entries
- **THEN** entries SHALL be picked up as workers become free, until all N entries are processed

---

### Requirement: Per-item result collection
The engine SHALL collect results from all workers after all futures complete and return an aggregate result.

#### Scenario: Aggregate result after sync
- **WHEN** all worker futures complete
- **THEN** the engine SHALL return a result containing: list of successful `ItemRecord`s, list of `FailureRecord`s (video_id, title, url, error_message)

#### Scenario: All items succeed
- **WHEN** every dispatched entry downloads without error
- **THEN** the failure list SHALL be empty

#### Scenario: All items fail
- **WHEN** every dispatched entry fails
- **THEN** the success list SHALL be empty and the failure list SHALL contain one entry per dispatched item

---

### Requirement: Overall sync progress reporting
The engine SHALL report overall progress as items complete, in the form of a running count (items completed / items total).

#### Scenario: Progress count during sync
- **WHEN** a worker completes an item (success or failure)
- **THEN** the progress display SHALL reflect the updated completed count out of total dispatched

#### Scenario: Progress at start
- **WHEN** dispatch begins with N items to download
- **THEN** the progress display SHALL show 0 / N

---

### Requirement: Worker thread DB isolation
Each worker thread SHALL open its own short-lived SQLite connection for all write operations. No connection SHALL be shared between threads.

#### Scenario: Concurrent DB writes from multiple workers
- **WHEN** two or more workers complete simultaneously and both attempt to write to the DB
- **THEN** both writes SHALL succeed (SQLite WAL serialises concurrent writers internally)
- **THEN** no `ProgrammingError` or `OperationalError` SHALL be raised from SQLite

#### Scenario: write contention
- **WHEN** a DB write encounters a lock (another writer is mid-transaction)
- **THEN** the engine SHALL wait up to 3000ms (`busy_timeout`) before raising an error

---

### Requirement: Per-playlist output subfolder

Each downloaded item SHALL be placed in a subdirectory named after the playlist, nested under the configured `output_dir`. The subdirectory name SHALL be the sanitized playlist name (filesystem-unsafe characters stripped via `renamer.sanitize`). If sanitization yields an empty string, the playlist ID SHALL be used as the fallback directory name.

#### Scenario: Normal playlist name
- **WHEN** a worker downloads a video for a playlist named `"My Playlist"`
- **THEN** the file SHALL be written to `<output_dir>/My Playlist/<filename>`, with the directory created if it does not exist

#### Scenario: Playlist name contains filesystem-unsafe characters
- **WHEN** the playlist name contains characters such as `/`, `:`, `*`, `?`, `"`, `<`, `>`, or `|`
- **THEN** those characters SHALL be stripped before the directory is created; the resulting sanitized name SHALL be used

#### Scenario: Sanitized name is empty
- **WHEN** after sanitization the playlist name is an empty string
- **THEN** the playlist ID SHALL be used as the subdirectory name
