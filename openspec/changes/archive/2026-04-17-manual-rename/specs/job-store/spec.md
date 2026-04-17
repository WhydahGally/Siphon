## MODIFIED Requirements

### Requirement: JobItem state machine
Each `JobItem` within a `DownloadJob` SHALL have a `state` field that follows this transition graph: `pending → downloading → done`, `pending → downloading → failed`, or `pending → cancelled`. `cancelled` is a valid terminal state reachable directly from `pending` only (not from `downloading`). `cancelled` SHALL be considered terminal: a job where all items are in `done | failed | cancelled` SHALL be treated as terminal. State transitions SHALL be applied by the download worker thread (for `downloading`, `done`, `failed`) or by `cancel_all_jobs()` (for `cancelled`), and SHALL notify SSE subscribers via an `asyncio.Queue`.

`JobItem` SHALL also have mutable `renamed_to` and `rename_tier` fields. These fields are initially set during download (by the auto-renamer if active, otherwise NULL). After download completes (`done` state), `renamed_to` and `rename_tier` MAY be updated by the manual rename endpoint without changing the item's `state`.

### Requirement: DownloadJob carries auto_rename flag
Each `DownloadJob` SHALL have an `auto_rename` boolean field (default `False`) that records whether auto-rename was enabled when the job was created. This field SHALL be set during `JobStore.create_job()` and SHALL be included in the `GET /jobs` response via `_job_to_dict()`. The UI uses this flag to decide whether to show the arrow format and tier badge for completed items.

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

#### Scenario: Manual rename updates renamed_to in done state
- **WHEN** `PUT /jobs/{job_id}/items/{video_id}/rename` is called for an item in `done` state
- **THEN** `JobItem.renamed_to` SHALL be updated to the new name and `JobItem.rename_tier` SHALL be set to `'manual'` without changing the item's `state`

#### Scenario: Manual rename rejected for non-done state
- **WHEN** a rename is attempted on an item not in `done` state
- **THEN** the operation SHALL be rejected with HTTP 409
