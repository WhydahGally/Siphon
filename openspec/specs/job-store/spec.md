### Requirement: JobStore — in-memory session job tracking
The daemon SHALL maintain an in-memory `JobStore` keyed by UUID `job_id`. The `JobStore` SHALL be a module-level singleton initialised at daemon startup. It SHALL NOT be persisted to SQLite. All data in the `JobStore` SHALL be lost if the daemon process restarts; this is expected behaviour. The `JobStore` SHALL store at most 50 jobs; when the limit is reached the oldest completed or failed job SHALL be evicted to make room.

#### Scenario: New job created
- **WHEN** `POST /jobs` is called with a valid URL
- **THEN** a new `DownloadJob` SHALL be created in the `JobStore` with a UUID `job_id`, `created_at` timestamp, and all items in `pending` state

#### Scenario: Job eviction at capacity
- **WHEN** the `JobStore` already holds 50 jobs and a new job is created
- **THEN** the oldest job whose all items are in terminal state (`done` or `failed`) SHALL be removed to make room

#### Scenario: Daemon restart clears store
- **WHEN** the daemon process is restarted
- **THEN** the `JobStore` SHALL be empty; no previous job data SHALL be accessible

---

### Requirement: JobItem state machine
Each `JobItem` within a `DownloadJob` SHALL have a `state` field that follows this transition graph: `pending → downloading → done`, `pending → downloading → failed`, or `pending → cancelled`. `cancelled` is a valid terminal state reachable directly from `pending` only (not from `downloading`). `cancelled` SHALL be considered terminal: a job where all items are in `done | failed | cancelled` SHALL be treated as terminal. State transitions SHALL be applied by the download worker thread (for `downloading`, `done`, `failed`) or by `cancel_all_jobs()` (for `cancelled`), and SHALL notify SSE subscribers via an `asyncio.Queue`.

#### Scenario: Successful item download
- **WHEN** a download worker begins processing an item
- **THEN** the item state SHALL transition to `downloading`
- **WHEN** the download completes successfully
- **THEN** the item state SHALL transition to `done` and `renamed_to` SHALL be populated if auto-rename is active

#### Scenario: Failed item download
- **WHEN** a download worker encounters an exception for an item
- **THEN** the item state SHALL transition to `failed` and `error` SHALL be populated with the exception message

#### Scenario: Pending item cancelled
- **WHEN** `POST /jobs/cancel-all` is called and an item is in `pending` state
- **THEN** the item state SHALL transition directly to `cancelled` without entering `downloading`

#### Scenario: Terminal state includes cancelled
- **WHEN** all items in a job are in `done`, `failed`, or `cancelled` state
- **THEN** the job SHALL be considered terminal and the SSE `done` event SHALL be emitted

---

### Requirement: `POST /jobs` endpoint
The daemon SHALL expose `POST /jobs` which accepts a JSON body containing: `url` (required string), `format` (default: mp3), `quality` (default: best), `auto_rename` (default: false), `watched` (default: true, ignored for single-video URLs), `check_interval_secs` (optional int, ignored for single-video URLs). The endpoint SHALL probe the URL to determine if it is a playlist or single video, register a playlist in the DB if it is a new playlist URL, create a `DownloadJob` in the `JobStore`, enqueue all items as `pending`, and dispatch the download to a background thread. The endpoint SHALL return 202 with `{ "job_id": "<uuid>" }` immediately.

#### Scenario: Playlist URL submitted
- **WHEN** `POST /jobs` is called with a playlist URL not already registered
- **THEN** the playlist SHALL be registered in the DB, a DownloadJob SHALL be created with all playlist items as pending, background download SHALL start, and the response SHALL be `202 { job_id }`

#### Scenario: Already-registered playlist URL
- **WHEN** `POST /jobs` is called with a playlist URL already registered
- **THEN** no duplicate registry entry SHALL be created; a new DownloadJob SHALL be created and only items not already in the `items` table SHALL be queued; response SHALL be `202 { "job_id": "<uuid>", "existing_playlist": true }`

#### Scenario: Single-video URL submitted
- **WHEN** `POST /jobs` is called with a single-video URL
- **THEN** a DownloadJob SHALL be created with one item, `playlist_id` SHALL be None, no scheduler timer SHALL be armed, and the response SHALL be `202 { job_id }`

#### Scenario: Invalid URL
- **WHEN** `POST /jobs` is called with a URL that yt-dlp cannot resolve to any video or playlist
- **THEN** the endpoint SHALL return 422 with a descriptive error message

---

### Requirement: `GET /jobs` endpoint
The daemon SHALL expose `GET /jobs` which returns a JSON array of all jobs currently in the `JobStore`, ordered by `created_at` descending. Each entry SHALL include: `job_id`, `playlist_id`, `playlist_name`, `created_at`, `total` (item count), `done` (count of items in done state), `failed` (count of items in failed state), and `items` (array of JobItem summaries).

#### Scenario: Active and completed jobs returned
- **WHEN** `GET /jobs` is called while the daemon has jobs in the store
- **THEN** all jobs SHALL be returned with current item states

#### Scenario: Empty store
- **WHEN** `GET /jobs` is called and no jobs exist
- **THEN** the response SHALL be an empty JSON array `[]`

---

### Requirement: `GET /jobs/{id}/stream` SSE endpoint
The daemon SHALL expose `GET /jobs/{id}/stream` as an SSE endpoint. The response SHALL have `Content-Type: text/event-stream`. Each SSE event SHALL be a JSON object containing: `job_id`, `video_id`, `state`, `yt_title`, `renamed_to` (or null), `error` (or null). The connection SHALL remain open until the job reaches terminal state (all items done or failed), at which point the server SHALL send a final `event: done` message and close the stream.

#### Scenario: SSE stream delivers state transition
- **WHEN** an item transitions state during a download
- **THEN** the SSE stream for that job SHALL emit a JSON event within one second of the transition

#### Scenario: SSE stream closes on job completion
- **WHEN** all items in a job have reached a terminal state (done or failed)
- **THEN** the SSE endpoint SHALL emit a final `event: done` message and close the connection

#### Scenario: SSE stream for unknown job
- **WHEN** `GET /jobs/{id}/stream` is called with a job_id not in the store
- **THEN** the endpoint SHALL return 404

---

### Requirement: `DELETE /jobs/{id}` endpoint
The daemon SHALL expose `DELETE /jobs/{id}` which removes a job from the `JobStore` only if all its items are in a terminal state. If the job has items still in `pending` or `downloading` state, the endpoint SHALL return 409.

#### Scenario: Delete completed job
- **WHEN** `DELETE /jobs/{id}` is called for a job where all items are done or failed
- **THEN** the job SHALL be removed from the `JobStore` and the response SHALL be 204

#### Scenario: Delete in-progress job
- **WHEN** `DELETE /jobs/{id}` is called for a job with pending or downloading items
- **THEN** the endpoint SHALL return 409 with an error message

---

### Requirement: `POST /jobs/{id}/retry-failed` endpoint
The daemon SHALL expose `POST /jobs/{id}/retry-failed` which resets all `failed` **and `cancelled`** items in the job back to `pending` state and re-dispatches them to the download worker pool. For playlist jobs (`playlist_id` is set), the existing `failed_downloads` DB record is NOT cleared before retry; instead `insert_failed` is called again on the next failure, incrementing the attempt count. For single-video jobs (`playlist_id` is None), no DB failure tracking occurs — failure state is in-memory only and the attempt count is not persisted.

#### Scenario: Retry all failed and cancelled items
- **WHEN** `POST /jobs/{id}/retry-failed` is called for a job with one or more failed or cancelled items
- **THEN** those items SHALL transition back to `pending`, download SHALL be re-dispatched, and the SSE stream SHALL resume emitting events for those items

#### Scenario: Retry increments attempt count (playlist jobs only)
- **WHEN** a retried playlist item fails again
- **THEN** `insert_failed` SHALL be called again, incrementing the attempt count in `failed_downloads`; after 3 total failures the item will be skipped by `_filter_entries` on future syncs

#### Scenario: No failed or cancelled items to retry
- **WHEN** `POST /jobs/{id}/retry-failed` is called and no items are in failed or cancelled state
- **THEN** the endpoint SHALL return 200 with `{ "retried": 0 }`
