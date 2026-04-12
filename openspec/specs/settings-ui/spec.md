### Requirement: Settings page sections
The Settings page SHALL be organised into five labelled sections rendered top-to-bottom: **Downloads**, **MusicBrainz**, **Appearance**, **About**, and **Danger Zone**. Each section SHALL have a section heading. The page SHALL be a single scrollable view with no tabs or sub-navigation.

#### Scenario: Settings page loads
- **WHEN** the user navigates to the Settings page
- **THEN** all five sections SHALL be visible in the correct order when the user scrolls the page

---

### Requirement: Downloads section — max concurrent downloads
The Downloads section SHALL contain a labelled dropdown to select the maximum number of concurrent downloads. The dropdown SHALL list integer options 1 through 10. The displayed value SHALL reflect the current `max-concurrent-downloads` setting loaded from `GET /settings/max-concurrent-downloads` on mount. When no value is stored, 5 SHALL be pre-selected as the default. Changing the dropdown value SHALL immediately call `PUT /settings/max-concurrent-downloads` and auto-save silently (no success toast).

#### Scenario: Default value displayed
- **WHEN** the Settings page loads and `max-concurrent-downloads` has never been set
- **THEN** the dropdown SHALL display 5

#### Scenario: Saved value displayed
- **WHEN** the Settings page loads and `max-concurrent-downloads` is stored as 3
- **THEN** the dropdown SHALL display 3

#### Scenario: Value changed
- **WHEN** the user selects a different value from the dropdown
- **THEN** `PUT /settings/max-concurrent-downloads` SHALL be called with the new value silently (no toast)

---

### Requirement: Downloads section — default sync interval
The Downloads section SHALL contain a labelled inline-editable interval field showing the current `interval` setting in DD:HH:MM:SS format. When no value is stored, the display SHALL show the equivalent of 86400 seconds. The edit pattern SHALL match the Library page interval editor: click to enter edit mode, type a DD:HH:MM:SS value, press Save to call `PUT /settings/interval`, or Cancel to discard. A human-readable summary (e.g., "Every day") SHALL be shown beneath the field.

#### Scenario: Default value displayed
- **WHEN** the Settings page loads and `interval` has never been set
- **THEN** the interval display SHALL show "01:00:00:00" and the summary SHALL read "Every day"

#### Scenario: Interval saved
- **WHEN** the user edits the interval field and presses Save with a valid DD:HH:MM:SS value
- **THEN** `PUT /settings/interval` SHALL be called with the converted seconds value and a success toast SHALL appear

#### Scenario: Invalid interval discarded
- **WHEN** the user types an invalid string and presses Save
- **THEN** no API call SHALL be made and the display SHALL revert to the previous value

---

### Requirement: Downloads section — global auto-rename default
The Downloads section SHALL contain a labelled toggle for the global auto-rename default. The toggle state SHALL reflect `auto-rename` from `GET /settings/auto-rename` on mount; if unset it SHALL default to `on`. Changing the toggle SHALL immediately call `PUT /settings/auto-rename` and auto-save silently (no success toast). A muted description SHALL explain that this sets the default checkbox state when adding a new download.

#### Scenario: Default state on first load
- **WHEN** `auto-rename` has never been set
- **THEN** the toggle SHALL be in the on/enabled state

#### Scenario: Toggle changed
- **WHEN** the user flips the toggle
- **THEN** `PUT /settings/auto-rename` SHALL be called with the new value silently (no toast)

---

### Requirement: MusicBrainz section — user-agent input
The MusicBrainz section SHALL contain a labelled text input for the `mb-user-agent` config value and an explicit Save button. The input SHALL be pre-filled with the current value from `GET /settings/mb-user-agent` on mount. The placeholder text SHALL be `Siphon/1.0 (you@example.com)`. A description SHALL state the field is required for MusicBrainz metadata lookups and SHALL note that the warning shown on the Dashboard will be dismissed once a value is set. Pressing Save SHALL call `PUT /settings/mb-user-agent` and show a success toast.

#### Scenario: Current value displayed on load
- **WHEN** the Settings page loads and `mb-user-agent` has a stored value
- **THEN** the text input SHALL display that value

#### Scenario: Save persists value
- **WHEN** the user types a new user-agent string and presses Save
- **THEN** `PUT /settings/mb-user-agent` SHALL be called with the new value and a success toast SHALL appear

---

### Requirement: MusicBrainz section — title noise patterns editor
The MusicBrainz section SHALL contain a collapsible noise patterns editor below the user-agent input. A labelled button ("Edit noise patterns") SHALL toggle the visibility of the editor. When expanded, the editor SHALL display a textarea pre-populated with the currently stored `title-noise-patterns` value (one pattern per line). Because the daemon seeds the default pattern list on first startup, the textarea will always be pre-populated on a running system. An explicit Save button SHALL call `PUT /settings/title-noise-patterns` and show a success toast. Saving an empty textarea SHALL store an empty JSON array `[]`, which disables noise filtering. A Cancel button SHALL collapse the editor and discard unsaved changes. The editor SHALL be collapsed by default.

#### Scenario: Editor collapsed on page load
- **WHEN** the Settings page mounts
- **THEN** the noise patterns textarea SHALL NOT be visible; only the "Edit noise patterns" toggle button SHALL be shown

#### Scenario: Editor expands and loads stored patterns
- **WHEN** the user clicks "Edit noise patterns"
- **THEN** the textarea SHALL expand and be pre-populated with the value from `GET /settings/title-noise-patterns`, with each pattern on its own line

#### Scenario: Editor expands with no stored patterns
- **WHEN** the user clicks "Edit noise patterns" and no patterns are stored
- **THEN** the textarea SHALL be empty and a muted note SHALL indicate that built-in defaults are in use

#### Scenario: Save with empty textarea — disables noise filtering
- **WHEN** the user clears the textarea and presses Save
- **THEN** `PUT /settings/title-noise-patterns` SHALL be called with `"[]"` and a success toast SHALL appear; subsequent downloads SHALL have no noise patterns stripped

#### Scenario: Save persists patterns
- **WHEN** the user edits the textarea and presses Save
- **THEN** `PUT /settings/title-noise-patterns` SHALL be called with the textarea content encoded as a JSON array (one pattern per non-empty line) and a success toast SHALL appear

#### Scenario: Cancel discards changes
- **WHEN** the user edits the textarea and presses Cancel
- **THEN** no API call SHALL be made, the textarea SHALL revert to its last saved value, and the editor SHALL collapse

#### Scenario: Save with invalid regex
- **WHEN** the user saves a pattern that the server rejects as an invalid regex
- **THEN** an error toast SHALL appear with the server's error message and the editor SHALL remain open

---

### Requirement: Appearance section — dark/light mode toggle
The Appearance section SHALL contain a labelled dark/light mode toggle. The initial state SHALL be loaded from `GET /settings/theme` on page load via the theme-init mechanism (see `global-config-keys` spec). Changing the toggle SHALL call `PUT /settings/theme` with `"dark"` or `"light"`, update the `data-theme` attribute on `<html>` immediately, and auto-save silently (no success toast).

#### Scenario: Dark mode active
- **WHEN** the stored theme is `"dark"` (or unset)
- **THEN** `document.documentElement.dataset.theme` SHALL NOT be set to `"light"` and the toggle SHALL reflect the dark state

#### Scenario: Switching to light mode
- **WHEN** the user activates the light mode toggle
- **THEN** `document.documentElement.dataset.theme` SHALL be set to `"light"`, `PUT /settings/theme` SHALL be called with `"light"`, and the UI SHALL immediately switch to the light colour scheme

#### Scenario: Switching back to dark mode
- **WHEN** the user activates the dark mode toggle
- **THEN** `document.documentElement.dataset.theme` SHALL be removed or set to `"dark"`, `PUT /settings/theme` SHALL be called with `"dark"`, and the UI SHALL immediately switch to the dark colour scheme

---

### Requirement: About section
The About section SHALL display: the Siphon version, the yt-dlp version, a hyperlink to the project repository, and a labelled dropdown to choose the log level. Version data SHALL be loaded from `GET /version`. The project link SHALL open `https://github.com/WhydahGally/Siphon` in a new browser tab. The log level dropdown SHALL list `DEBUG`, `INFO`, `WARNING`, `ERROR`; the current value SHALL be loaded from `GET /settings/log-level` on mount and SHALL default to `INFO` if unset. Changing the log level SHALL immediately call `PUT /settings/log-level` and auto-save silently (no success toast).

#### Scenario: Versions displayed
- **WHEN** the Settings page loads and the daemon is reachable
- **THEN** both the Siphon version and yt-dlp version SHALL be displayed as returned by `GET /version`

#### Scenario: Project link opens repository
- **WHEN** the user clicks the project link
- **THEN** the browser SHALL open `https://github.com/WhydahGally/Siphon` in a new tab

#### Scenario: Log level changed
- **WHEN** the user selects a new log level from the dropdown
- **THEN** `PUT /settings/log-level` SHALL be called with the selected value silently (no toast)

---

### Requirement: Danger Zone section — delete all playlists
The Danger Zone section SHALL contain a "Delete Playlists" action using the `ConfirmButton` component (initial label "Delete Playlists", confirm label "Yes, delete all"). A description SHALL state that all playlists and sync history are removed but settings and downloaded files are kept. Confirming SHALL call `DELETE /playlists` and show a success toast.

#### Scenario: Confirmation required
- **WHEN** the user clicks "Delete Playlists"
- **THEN** the button SHALL split into "Yes, delete all" and "Cancel" before any action is taken

#### Scenario: Confirmed
- **WHEN** the user confirms the action
- **THEN** `DELETE /playlists` SHALL be called and a success toast SHALL appear

---

### Requirement: Danger Zone section — factory reset
The Danger Zone section SHALL contain a "Factory Reset" action using the `ConfirmButton` component (initial label "Factory Reset", confirm label "Yes, reset everything"). A description SHALL state that all playlists, history, and settings are wiped, and that downloaded files are not affected. Confirming SHALL call `POST /factory-reset` and show a success toast followed by a full page reload after a short delay (to re-read clean settings).

#### Scenario: Confirmation required
- **WHEN** the user clicks "Factory Reset"
- **THEN** the button SHALL split into "Yes, reset everything" and "Cancel" before any action is taken

#### Scenario: Confirmed
- **WHEN** the user confirms the factory reset
- **THEN** `POST /factory-reset` SHALL be called, a success toast SHALL appear, and the page SHALL reload after ~1.5 seconds
