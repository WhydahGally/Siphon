## ADDED Requirements

### Requirement: Dashboard download section is always positioned at the top
The Dashboard SHALL render the `DownloadForm` at the top of the page at all times, regardless of whether any download jobs exist. No centering, animation, or conditional layout class SHALL be applied based on job state.

#### Scenario: Dashboard loaded with no jobs
- **WHEN** the user navigates to the Dashboard and no download jobs are present
- **THEN** the `DownloadForm` is rendered at the top of the viewport with standard padding, not vertically centered

#### Scenario: Dashboard loaded with existing jobs
- **WHEN** the user navigates to the Dashboard and download jobs are already present
- **THEN** the `DownloadForm` remains at the top with the same layout as when no jobs are present

#### Scenario: First job created in a session
- **WHEN** the user submits the download form for the first time in a session
- **THEN** the layout does not shift or animate — the `DownloadForm` stays at the top and the queue appears below it

### Requirement: Download form toggles row does not shift when playlist controls appear
The `.toggles-row` in `DownloadForm` SHALL maintain a fixed minimum height at all times. Appending the Auto sync toggle and interval control when a playlist URL is detected SHALL NOT increase the row height or shift elements below it.

#### Scenario: Non-playlist URL entered
- **WHEN** the user types or pastes a URL without `list=`
- **THEN** only the Auto rename toggle is shown and the row height is unchanged

#### Scenario: Playlist URL entered
- **WHEN** the user types or pastes a URL containing `list=`
- **THEN** the Auto sync toggle and interval control appear without changing the row height or moving the Download button

### Requirement: Download queue is scrollable and does not cause page-level scrolling
The download queue section SHALL scroll internally when its content exceeds the available viewport height. The main page SHALL NOT show a scrollbar regardless of how many items are in the queue. Browser scrollbars SHALL be hidden globally across all scrollable regions.

#### Scenario: Many items in queue
- **WHEN** the queue contains more items than fit in the viewport
- **THEN** the queue body scrolls within its container and no page-level scrollbar appears

#### Scenario: Dashboard height
- **WHEN** the dashboard is rendered
- **THEN** its total height SHALL NOT exceed `calc(100vh - 56px)` (viewport minus navbar)

### Requirement: Failed download items appear at the top of the queue
Within each job block, items SHALL be sorted so that `failed` items appear first, followed by `downloading`, `pending`, and `done`.

#### Scenario: Mix of states in a job
- **WHEN** a job contains items in multiple states including failed
- **THEN** failed items are rendered at the top of the list

### Requirement: Playlist synced and added timestamps show granular relative time
The library playlist row SHALL display relative times with sub-day resolution for both the "Added" and "Synced" metadata labels.

#### Scenario: Synced less than a minute ago
- **WHEN** `last_synced_at` is less than 60 seconds in the past
- **THEN** the label reads "Synced less than a minute ago"

#### Scenario: Synced within the same hour
- **WHEN** `last_synced_at` is between 1 minute and 1 hour in the past
- **THEN** the label reads "Synced Xm ago"

#### Scenario: Synced within the same day
- **WHEN** `last_synced_at` is between 1 hour and 24 hours in the past
- **THEN** the label reads "Synced Xh ago"

### Requirement: Dashboard interval input uses the same interaction pattern as Settings
The sync interval control in the download form SHALL use the same DD:HH:MM:SS text input with pen-icon display, inline Save button, Enter-to-save, Escape-to-cancel, and click-outside-to-cancel behaviour as the settings page interval control. The displayed value SHALL be human-readable (e.g. "Every day").

#### Scenario: Interval displayed before editing
- **WHEN** the playlist interval control is shown
- **THEN** it displays a human-readable string with a pencil icon

#### Scenario: Editing the interval
- **WHEN** the user clicks the pencil icon
- **THEN** a text input pre-filled with DD:HH:MM:SS appears with an inline Save button; clicking outside or pressing Escape cancels without saving

### Requirement: Interval input fields have a format tooltip
Both the dashboard and settings interval text inputs SHALL show a native browser tooltip reading "Format: DD:HH:MM:SS" when hovered.

#### Scenario: Hovering the interval input
- **WHEN** the user hovers over the interval text input in either the dashboard or settings
- **THEN** a tooltip reading "Format: DD:HH:MM:SS" is displayed by the browser

### Requirement: Download and DB directory paths are logged to the browser console on startup
On application mount, the web UI SHALL fetch `GET /info` from the daemon and log the resolved `download_dir` and `db_dir` paths to the browser console as `[siphon]` prefixed INFO messages. This SHALL occur only once per page load.

#### Scenario: Daemon is reachable on load
- **WHEN** the Vue app mounts and the daemon is running
- **THEN** two `console.info` lines are printed: one for the download directory and one for the DB directory

#### Scenario: Daemon is not reachable on load
- **WHEN** the Vue app mounts and the daemon is not running
- **THEN** no error is thrown and no console messages are printed

### Requirement: Application uses a custom funnel favicon and navbar logo
The web application SHALL use a custom flat funnel SVG as its favicon and display the same funnel icon to the left of the "Siphon" wordmark in the navigation bar. The icon SHALL use the app accent colour and SHALL glow on hover alongside the wordmark.

#### Scenario: Browser tab
- **WHEN** the application is open in a browser tab
- **THEN** the tab displays the purple funnel favicon

#### Scenario: Navbar hover
- **WHEN** the user hovers over the logo area in the navbar
- **THEN** both the funnel icon and the "Siphon" text glow with the accent colour
