## MODIFIED Requirements

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

## MODIFIED Requirements

### Requirement: Job eviction at capacity
The `JobStore` SHALL store at most 50 jobs; when the limit is reached the oldest job whose all items are in terminal state (`done`, `failed`, or `cancelled`) SHALL be evicted to make room.

#### Scenario: Job eviction at capacity
- **WHEN** the `JobStore` already holds 50 jobs and a new job is created
- **THEN** the oldest job whose all items are in terminal state (`done`, `failed`, or `cancelled`) SHALL be removed to make room

---

## MODIFIED Requirements

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
