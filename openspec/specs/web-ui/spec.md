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
The Dashboard SHALL display a download queue section below the URL input. The queue SHALL show all jobs created in the current daemon session (fetched via `GET /jobs` on page load, then updated via SSE). A summary line SHALL show total progress across the active job (e.g., "47 / 100 downloaded"). The queue SHALL display individual items sorted in this order from top: items with state `downloading`, then `pending`, then `done`, then `failed`. Items with state `failed` SHALL have a distinct red-tinted row background. Items with state `done` SHALL display a check mark indicator and, if auto-rename was active, SHALL show both the original YouTube title and the renamed filename. Items with state `downloading` SHALL display a visual activity indicator (e.g., spinner). A "Clear list" button SHALL be present; clicking it SHALL call `DELETE /jobs` to prune completed and failed jobs from the store and remove them from the UI. A "Retry failed" button SHALL be present; clicking it SHALL call `POST /jobs/{id}/retry-failed` to re-enqueue all failed items. Each individual failed item row SHALL also have a per-item "Retry" button.

#### Scenario: Item transitions to downloading
- **WHEN** an SSE event arrives with `state: "downloading"` for a given video_id
- **THEN** that item SHALL move to the top of the queue and display a spinner

#### Scenario: Item transitions to done
- **WHEN** an SSE event arrives with `state: "done"` for a given video_id
- **THEN** that item SHALL display a check mark; if `renamed_to` is present, the row SHALL show `yt_title → renamed_to`

#### Scenario: Item transitions to failed
- **WHEN** an SSE event arrives with `state: "failed"` for a given video_id
- **THEN** that item's row SHALL be highlighted red and SHALL show the error message; a per-row Retry button SHALL be visible

#### Scenario: Progress summary updates
- **WHEN** any item transitions to `done` or `failed`
- **THEN** the summary counter SHALL update to reflect the new counts

#### Scenario: Retry failed (global)
- **WHEN** the user clicks "Retry failed"
- **THEN** the UI SHALL POST to `/jobs/{id}/retry-failed` and all failed items SHALL transition back to `pending` state in the queue

#### Scenario: Clear list
- **WHEN** the user clicks "Clear list"
- **THEN** the UI SHALL call `DELETE /jobs/{id}` for jobs that are fully completed or fully failed and those rows SHALL be removed from the queue display

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
