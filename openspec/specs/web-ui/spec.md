### Requirement: Navigation bar
The web UI SHALL render a persistent top navigation bar on every page. The left edge SHALL display the "Siphon" logo/text. The centre SHALL contain two navigation buttons: Dashboard and Library. A settings gear icon button SHALL be positioned at the right edge and SHALL navigate to the Settings page. The active page SHALL be visually distinguished from inactive pages (active underline for centre buttons; accent colour for the gear icon when Settings is active). The default page on first load SHALL be Dashboard.

#### Scenario: Initial load shows Dashboard
- **WHEN** the user opens the web UI in a browser
- **THEN** the Dashboard page SHALL be displayed and the Dashboard navigation button SHALL be in its active/selected state

#### Scenario: Navigation between pages
- **WHEN** the user clicks a navigation button (e.g., Library)
- **THEN** the corresponding page SHALL replace the current page content and the clicked button SHALL transition to its active state

---

### Requirement: URL input and format controls
The Dashboard SHALL present a URL input field and a Download button. To the right of the URL input SHALL be a Format dropdown and a Quality selector. The Format dropdown SHALL list audio formats (mp3, opus) and video formats (mp4, mkv, webm) with a visual separator between the audio and video groups. The Quality selector SHALL be interactive only when a video format is selected; when an audio format is selected the Quality selector SHALL display "best" in a disabled/non-interactive state and SHALL show a tooltip on hover reading "Audio is always downloaded at the best quality available."

#### Scenario: Audio format selected — quality locked
- **WHEN** the user selects an audio format (mp3 or opus) from the Format dropdown
- **THEN** the Quality selector SHALL display "best" and SHALL NOT respond to clicks; hovering over it SHALL reveal the tooltip text

#### Scenario: Video format selected — quality interactive
- **WHEN** the user selects a video format (mp4, mkv, or webm) from the Format dropdown
- **THEN** the Quality selector SHALL become interactive and SHALL offer the options: best, 2160, 1080, 720, 480, 360

#### Scenario: Default format and quality on load
- **WHEN** the Dashboard loads for the first time
- **THEN** the Format dropdown SHALL default to mp3 and the Quality selector SHALL display "best" in its disabled state

---

### Requirement: Auto-rename and auto-sync toggles
Below the URL input and format controls the Dashboard SHALL display two toggle switches: "Auto rename" and "Auto sync", both enabled by default. When "Auto rename" is enabled and the global `mb-user-agent` config value is not set, a warning icon SHALL appear adjacent to the toggle; hovering over it SHALL display a tooltip explaining that MusicBrainz lookups require `mb-user-agent` to be configured. When "Auto sync" is enabled AND the entered URL is detected as a playlist URL (contains `list=`), a numeric interval input SHALL appear defaulting to 86400 seconds (displayed as a human-readable hint, e.g., "24 hours"). When the entered URL is a single-video URL, the "Auto sync" toggle SHALL be hidden entirely.

#### Scenario: Auto-rename warning when mb-user-agent unset
- **WHEN** "Auto rename" is toggled on and `GET /settings/mb-user-agent` returns a null value
- **THEN** a warning icon SHALL appear next to the toggle
- **WHEN** the user hovers over the warning icon
- **THEN** a tooltip SHALL appear explaining that MusicBrainz lookups require mb-user-agent to be set via `siphon config mb-user-agent`

#### Scenario: Interval input shown for playlist URL with auto-sync on
- **WHEN** the URL input contains a playlist URL (contains `list=`) AND "Auto sync" is toggled on
- **THEN** an interval input field SHALL appear with a default value of 86400 and a placeholder or hint reading "24 hours"

#### Scenario: Auto-sync hidden for single-video URL
- **WHEN** the URL input contains a URL that does not contain `list=`
- **THEN** the "Auto sync" toggle SHALL not be visible

#### Scenario: Defaults on load
- **WHEN** the Dashboard loads
- **THEN** both "Auto rename" and "Auto sync" toggles SHALL be in their enabled state

---

### Requirement: Download button submission
When the user clicks Download, the UI SHALL POST to `POST /jobs` with the URL, format, quality, auto_rename flag, and (for playlists) watched and check_interval_secs derived from the auto-sync toggle and interval input. The UI SHALL disable the Download button and show a loading state during the request. On success (202) the UI SHALL receive a `job_id` and immediately open an SSE connection to `GET /jobs/{job_id}/stream`.

#### Scenario: Successful job submission
- **WHEN** the user enters a valid URL and clicks Download
- **THEN** the UI SHALL POST to `/jobs`, receive a job_id in the response, and begin streaming item events from `/jobs/{job_id}/stream`

#### Scenario: Empty URL submission
- **WHEN** the user clicks Download with an empty URL input
- **THEN** no request SHALL be made and a toast error message SHALL be shown

#### Scenario: Daemon unavailable
- **WHEN** the `POST /jobs` request fails due to a network error
- **THEN** the UI SHALL display a toast error message and re-enable the Download button

---

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

---

### Requirement: Library page — fully implemented
The Library page SHALL display all registered playlists fetched from `GET /playlists`. It SHALL not be a stub. It SHALL be rendered when the user navigates to the Library tab.

#### Scenario: Library tab selected
- **WHEN** the user clicks the Library nav button
- **THEN** the Library page content SHALL be shown and the nav button SHALL be in its active state

---

### Requirement: Download queue excludes sync jobs
The Dashboard download queue (`GET /jobs` and the queue display) SHALL NOT include sync operations triggered via `POST /playlists/{id}/sync`. Sync operations SHALL only be visible in the Library tab via the `is_syncing` flag and sync-events SSE channel.

#### Scenario: Library sync does not appear in Dashboard queue
- **WHEN** the user triggers a sync from the Library tab
- **THEN** no new item SHALL appear in the Dashboard's download queue
