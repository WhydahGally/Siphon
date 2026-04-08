## ADDED Requirements

### Requirement: Library page renders playlist list
The Library page SHALL fetch all registered playlists from `GET /playlists` on mount and display them as a vertical list. Each playlist row SHALL display: playlist name, item count, registration date (derived from `added_at`), last-synced time (derived from `last_synced_at`, shown as "never synced" if null), and a syncing spinner when `is_syncing` is true.

#### Scenario: Library mounts with playlists registered
- **WHEN** the user navigates to the Library tab
- **THEN** the Library SHALL call `GET /playlists` and render one row per playlist in the response

#### Scenario: Library mounts with no playlists
- **WHEN** the user navigates to the Library tab and `GET /playlists` returns an empty array
- **THEN** the Library SHALL display an empty-state message (e.g. "No playlists yet. Add one from the Dashboard.")

#### Scenario: Playlist row shows metadata
- **WHEN** a playlist row is rendered
- **THEN** it SHALL display the playlist name, item count, registration date formatted as a human-readable relative or absolute date, and last-synced time or "never synced"

#### Scenario: Daemon unreachable on mount
- **WHEN** `GET /playlists` fails (network error or non-2xx)
- **THEN** the Library SHALL display an error state and SHALL NOT crash

---

### Requirement: Per-row sync control
Each playlist row SHALL include a "Sync now" button. Clicking it SHALL call `POST /playlists/{id}/sync`. While the sync is in progress the button SHALL be replaced by a spinner animation and a "Syncing…" label. The Sync Now button SHALL be re-enabled only when the sync completes (via SSE `sync_done` event).

#### Scenario: User triggers sync
- **WHEN** the user clicks "Sync now" on a playlist row
- **THEN** the UI SHALL call `POST /playlists/{id}/sync` and immediately replace the button with a spinner

#### Scenario: Sync completes
- **WHEN** a `sync_done` SSE event is received for that `playlist_id`
- **THEN** the spinner SHALL be removed, the Sync Now button SHALL reappear, and `last_synced_at` SHALL be updated by re-fetching that playlist row via `GET /playlists/{id}`

#### Scenario: Sync already in progress on page load
- **WHEN** the Library mounts and `GET /playlists` returns `is_syncing: true` for a playlist
- **THEN** the row SHALL immediately display the spinner without waiting for a `sync_started` event

---

### Requirement: Per-row Auto Rename toggle
Each playlist row SHALL include a toggle labelled "Auto rename". Its initial state SHALL reflect the `auto_rename` field from the playlist response. Toggling it SHALL call `PATCH /playlists/{id}` with `{ "auto_rename": <new_value> }`.

#### Scenario: Toggle auto rename on
- **WHEN** the user toggles Auto Rename to on
- **THEN** the UI SHALL call `PATCH /playlists/{id}` with `auto_rename: true` and update the toggle to on state on success

#### Scenario: Toggle auto rename off
- **WHEN** the user toggles Auto Rename to off
- **THEN** the UI SHALL call `PATCH /playlists/{id}` with `auto_rename: false` and update the toggle to off state on success

---

### Requirement: Per-row Auto Sync toggle
Each playlist row SHALL include a toggle labelled "Auto sync". Its initial state SHALL reflect the `watched` field from the playlist response. Toggling it SHALL call `PATCH /playlists/{id}` with `{ "watched": <new_value> }`.

#### Scenario: Toggle auto sync on
- **WHEN** the user toggles Auto Sync to on
- **THEN** the UI SHALL call `PATCH /playlists/{id}` with `watched: true`

#### Scenario: Toggle auto sync off
- **WHEN** the user toggles Auto Sync to off
- **THEN** the UI SHALL call `PATCH /playlists/{id}` with `watched: false`

---

### Requirement: Per-row inline interval editor
Each playlist row SHALL display the current sync interval as human-readable text (e.g. "every 24h", "every 10m", "every 45s", "every 5d"). Clicking this text SHALL open an inline `<input>` pre-populated with the interval in `DD:HH:MM:SS` format. Pressing Enter or blurring the field SHALL parse the input to seconds and call `PATCH /playlists/{id}` with `{ "check_interval_secs": <seconds> }`. Pressing Escape SHALL revert to display mode without saving. The input field SHALL have a placeholder of `DD:HH:MM:SS`.

#### Scenario: User opens interval editor
- **WHEN** the user clicks the interval display text
- **THEN** an input field SHALL appear in place of the text, pre-populated with the current interval in DD:HH:MM:SS format

#### Scenario: User saves new interval
- **WHEN** the user types a valid DD:HH:MM:SS value and presses Enter or blurs the field
- **THEN** the UI SHALL convert the value to seconds and call `PATCH /playlists/{id}` with `check_interval_secs: <seconds>`, then revert to display mode showing the new human-readable value

#### Scenario: User cancels interval edit
- **WHEN** the user presses Escape while the interval input is active
- **THEN** the input SHALL close and the original display text SHALL be restored with no API call made

#### Scenario: Human-readable interval display (seconds to text)
- **WHEN** `check_interval_secs` is 1
- **THEN** the display SHALL read "Every second"
- **WHEN** `check_interval_secs` is less than 60 and not 1
- **THEN** the display SHALL read "Every X seconds" where X is the raw seconds value
- **WHEN** `check_interval_secs` is exactly 60
- **THEN** the display SHALL read "Every minute"
- **WHEN** `check_interval_secs` is between 61 and 3599 (inclusive) and `floor(secs / 60)` is not 1
- **THEN** the display SHALL read "Every X minutes" where X is `floor(secs / 60)`
- **WHEN** `check_interval_secs` is between 3600 and 86399 (inclusive) and `floor(secs / 3600)` is 1
- **THEN** the display SHALL read "Every hour"
- **WHEN** `check_interval_secs` is between 3600 and 86399 (inclusive) and `floor(secs / 3600)` is not 1
- **THEN** the display SHALL read "Every X hours" where X is `floor(secs / 3600)`
- **WHEN** `check_interval_secs` is 86400 or greater and `floor(secs / 86400)` is 1
- **THEN** the display SHALL read "Every day"
- **WHEN** `check_interval_secs` is 86400 or greater and `floor(secs / 86400)` is not 1
- **THEN** the display SHALL read "Every X days" where X is `floor(secs / 86400)`

---

### Requirement: Per-row delete with split-confirm
Each playlist row SHALL include a delete control implemented using `ConfirmButton.vue`. In default state it SHALL show a single "Delete" button. On first click it SHALL split into "Confirm" and "Cancel" buttons. Clicking Confirm SHALL call `DELETE /playlists/{id}` and, on success (204), remove the row from the list with a fade-out transition. Clicking Cancel SHALL revert to the single Delete button state.

#### Scenario: Delete confirmed
- **WHEN** the user clicks Delete then Confirm
- **THEN** the UI SHALL call `DELETE /playlists/{id}` and on 204 response remove the playlist row from the rendered list

#### Scenario: Delete cancelled
- **WHEN** the user clicks Delete then Cancel
- **THEN** the row SHALL revert to its normal state with no API call made

#### Scenario: Delete auto-reverts if inactive
- **WHEN** the user clicks Delete but does not click Confirm or Cancel within 5 seconds
- **THEN** the split buttons SHALL automatically revert to the single Delete button state
