## MODIFIED Requirements

### Requirement: Download queue display
The Dashboard SHALL display a download queue section below the URL input. The queue SHALL show all jobs created in the current daemon session (fetched via `GET /jobs` on page load, then updated via SSE). A summary line SHALL show total progress across the active job (e.g., "47 / 100 downloaded"); this counter SHALL be locked to the job's original total item count (returned as `original_total` in the `GET /jobs` response) and SHALL NOT change when items are cleared from the store. The queue SHALL display individual items sorted in this order from top: items with state `failed`, then `downloading`, then `pending`, then `cancelled`, then `done`. Items with state `failed` SHALL have a distinct red-tinted row background. Items with state `cancelled` SHALL have a distinct muted/grey row with reduced opacity. Items with state `done` SHALL display a check mark indicator and, if auto-rename was active, SHALL show both the original YouTube title and the renamed filename. Items with state `downloading` SHALL display a visual activity indicator (e.g., spinner). Items with state `cancelled` SHALL display a neutral/grey dash icon.

The queue header SHALL contain three action buttons always rendered in this order: **Abort**, **Retry**, **Clear**. The buttons SHALL always be visible (never hidden) and SHALL be enabled or disabled based on queue state as follows:

- **Abort**: enabled when any playlist job is non-terminal; disabled otherwise. On click, the button SHALL disable itself immediately and display `Aborting…` with a CSS pulse animation until all playlist jobs reach terminal state, then SHALL revert to `Abort` text and remain disabled. Tooltip: "Abort pending downloads".
- **Retry**: enabled when any item across all jobs is in `failed` or `cancelled` state; disabled otherwise. Tooltip: "Retry failed items".
- **Clear**: enabled when any item across all jobs is in a terminal state (`done`, `failed`, or `cancelled`); disabled otherwise. Clear has two modes determined by queue state:
  - **When `done` items exist** (mixed states): Clear SHALL call `POST /jobs/{id}/clear-done` for each job that has `done` items, removing only `done` items from the backend store. Failed and cancelled items SHALL remain. Tooltip: "Clear finished".
  - **When only `failed` or `cancelled` items remain** (no `done` items): Clear SHALL call `POST /jobs/{id}/clear-done?all=true` for each affected job, removing all terminal items from the backend store. Tooltip: "Clear failed".
  After clearing, the UI SHALL re-fetch `GET /jobs` to update the display with the authoritative backend state. If a job has no remaining items after clearing, the backend SHALL delete the job entirely and it SHALL disappear from the UI.

Clicking Retry SHALL call `POST /jobs/{id}/retry-failed` for the first job that has failed or cancelled items. Per-item Retry buttons SHALL be removed (the global Retry button replaces them).

#### Scenario: Item transitions to downloading
- **WHEN** an SSE event arrives with `state: "downloading"` for a given video_id
- **THEN** that item SHALL display a spinner

#### Scenario: Item transitions to done
- **WHEN** an SSE event arrives with `state: "done"` for a given video_id
- **THEN** that item SHALL display a check mark; if `renamed_to` is present, the row SHALL show `yt_title → renamed_to`

#### Scenario: Item transitions to failed
- **WHEN** an SSE event arrives with `state: "failed"` for a given video_id
- **THEN** that item's row SHALL be highlighted red and SHALL show the error message

#### Scenario: Item transitions to cancelled
- **WHEN** an SSE event arrives with `state: "cancelled"` for a given video_id
- **THEN** that item's row SHALL display with a muted/grey style and a neutral icon

#### Scenario: Progress summary does not change when done items are cleared
- **WHEN** the user clicks Clear and done items are removed from the display
- **THEN** the progress summary counter SHALL still reflect the job's original total item count

#### Scenario: Cancel button acknowledges click
- **WHEN** the user clicks Abort
- **THEN** the button SHALL immediately disable and display `Aborting…` with a pulse animation
- **AND** once all playlist jobs reach terminal state, the button text SHALL revert to `Abort` and remain disabled

#### Scenario: Retry button covers cancelled items
- **WHEN** some items are in `cancelled` state and no items are in `failed` state
- **THEN** the Retry button SHALL be enabled and clicking it SHALL reset cancelled items to `pending` and re-dispatch them

#### Scenario: Clear removes only done items when done items exist
- **WHEN** the user clicks Clear while the queue has a mix of `done` and `failed`/`cancelled` items
- **THEN** only `done` items SHALL be removed from the backend store; `failed`, `cancelled`, `downloading`, and `pending` items SHALL remain

#### Scenario: Clear removes all terminal items when only failed remain
- **WHEN** the user clicks Clear and the queue has no `done` items but has `failed` or `cancelled` items
- **THEN** all `failed` and `cancelled` items SHALL be removed from the backend store

#### Scenario: Job block disappears when all items cleared
- **WHEN** the user clicks Clear and all items in a job block were in `done` state
- **THEN** that job block SHALL disappear from the queue display entirely

#### Scenario: Cancel button disabled for single-video-only queue
- **WHEN** all active (non-terminal) jobs have `playlist_id` of null (single-video jobs only)
- **THEN** the Abort button SHALL remain disabled

#### Scenario: Retry failed (global)
- **WHEN** the user clicks Retry
- **THEN** the UI SHALL POST to `/jobs/{id}/retry-failed` for the job with failed or cancelled items and those items SHALL transition back to `pending` state in the queue

#### Scenario: Queue restored on page refresh
- **WHEN** the user refreshes the browser while the daemon is running
- **THEN** `GET /jobs` SHALL return all session jobs and the queue SHALL repopulate with their last-known state; if any job is still in progress, SSE SHALL be re-established for it
