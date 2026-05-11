## ADDED Requirements

### Requirement: Downloads section — Cookies row
The Downloads section SHALL contain a **Cookies** row positioned after the Auto rename row. The row SHALL contain:
- A label "Cookies"
- A description explaining that a cookie file enables downloading private, age-restricted, and members-only content, with a warning that linking an account may result in a temporary or permanent YouTube ban, and a hyperlink "Follow this guide ↗" linking to `https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies` to safely export cookies (matching the style of the SponsorBlock hyperlink)
- On the right control column: an upload button (when no file is configured), or a replace button + configured badge + ConfirmButton delete (when a file is configured)
- A `cookies-enabled` toggle (described in the next requirement)

The upload and replace buttons SHALL trigger a hidden `<input type="file" accept=".txt">` element, opening the native OS file dialog. After the user selects a file, the UI SHALL POST it to `POST /settings/cookie-file`. If the server returns `400`, a warning toast SHALL be shown with the server's error message. If the server returns `413`, a warning toast SHALL state the file is too large. On success (`204`), `cookieFileSet` SHALL be updated to `true` and a success toast SHALL appear.

The ConfirmButton delete SHALL call `DELETE /settings/cookie-file`. On `204`, `cookieFileSet` SHALL be updated to `false` and a success toast SHALL appear.

#### Scenario: No cookie file configured — upload button shown
- **WHEN** the Settings page loads and `GET /settings/cookie-file` returns `{"set": false}`
- **THEN** only the upload button SHALL be visible in the Cookies row control column (no delete button, no badge)

#### Scenario: Cookie file configured — replace, badge, and delete shown
- **WHEN** the Settings page loads and `GET /settings/cookie-file` returns `{"set": true}`
- **THEN** the replace button, a "Configured" badge, and the ConfirmButton delete SHALL be visible

#### Scenario: Upload opens native file dialog
- **WHEN** the user clicks the upload or replace button
- **THEN** the OS native file picker SHALL open

#### Scenario: Valid file uploaded successfully
- **WHEN** the user selects a valid `.txt` cookie file and the server returns `204`
- **THEN** a success toast SHALL appear and the row SHALL update to show the replace, badge, and delete controls

#### Scenario: Invalid file shows warning toast
- **WHEN** the server returns `400` in response to the upload
- **THEN** a warning toast SHALL display the server's error message and the row state SHALL not change

#### Scenario: File too large shows warning toast
- **WHEN** the server returns `413`
- **THEN** a warning toast SHALL state the file exceeds the size limit

#### Scenario: Delete confirms before acting
- **WHEN** the user clicks the delete button
- **THEN** the ConfirmButton SHALL require a second click before calling `DELETE /settings/cookie-file`

#### Scenario: Delete succeeds
- **WHEN** the user confirms the delete and the server returns `204`
- **THEN** a success toast SHALL appear and the row SHALL revert to showing only the upload button

---

### Requirement: Downloads section — cookies-enabled toggle
The Cookies row SHALL include a toggle for the `cookies-enabled` global setting. When no cookie file is configured (`cookieFileSet = false`), the toggle SHALL be visually disabled (greyed out) and a tooltip "Upload a cookie file to enable this setting." SHALL appear on hover. When a cookie file is configured, the toggle SHALL be interactive. The toggle state SHALL reflect `cookies-enabled` from `GET /settings` on mount, defaulting to on if unset. Changing the toggle SHALL call `PUT /settings/cookies-enabled` and auto-save silently (no toast).

#### Scenario: Toggle disabled when no cookie file
- **WHEN** the Settings page loads and `cookieFileSet` is false
- **THEN** the `cookies-enabled` toggle SHALL be visually disabled and non-interactive; hovering SHALL show the tooltip

#### Scenario: Toggle becomes active after upload
- **WHEN** a cookie file is successfully uploaded
- **THEN** the `cookies-enabled` toggle SHALL become interactive without a page reload

#### Scenario: Toggle change saves silently
- **WHEN** the user flips the cookies-enabled toggle (with a cookie file configured)
- **THEN** `PUT /settings/cookies-enabled` SHALL be called with the new value and no toast SHALL appear

---

### Requirement: Dashboard and Library — conditional Cookies toggle
The Dashboard (DownloadForm) SHALL include a "Cookies" toggle in the toggles row, rendered only when `cookieFileSet` is `true` (from `useSettings()`). The toggle SHALL be seeded from the global `cookiesEnabled` default. The Library (PlaylistRow) SHALL include a "Cookies" toggle in both desktop and mobile layouts, rendered only when `cookieFileSet` is `true`. The toggle state SHALL reflect the per-playlist `cookies_enabled` value (NULL treated as following the global default). Changing the per-playlist toggle SHALL immediately PATCH the playlist.

#### Scenario: Toggle hidden when no cookie file
- **WHEN** `cookieFileSet` is `false`
- **THEN** no Cookies toggle SHALL appear in the Dashboard form or in any PlaylistRow

#### Scenario: Toggle visible when cookie file configured
- **WHEN** `cookieFileSet` is `true`
- **THEN** a "Cookies" toggle SHALL appear in the Dashboard form and in each PlaylistRow

#### Scenario: Per-playlist toggle PATCH on change
- **WHEN** the user flips the Cookies toggle in a PlaylistRow
- **THEN** `PATCH /playlists/{id}` SHALL be called with `{"cookies_enabled": <bool>}` and the toggle SHALL revert on error

---

## MODIFIED Requirements

### Requirement: Danger Zone section — factory reset
The Danger Zone section SHALL contain a "Factory Reset" action using the `ConfirmButton` component (initial label "Factory Reset", confirm label "Yes, reset everything"). A description SHALL state that all playlists, history, cookies and all settings are wiped, and that downloaded files are not affected. Confirming SHALL call `POST /factory-reset` and show a success toast followed by a full page reload after a short delay (to re-read clean settings).

#### Scenario: Confirmation required
- **WHEN** the user clicks "Factory Reset"
- **THEN** the button SHALL split into "Yes, reset everything" and "Cancel" before any action is taken

#### Scenario: Confirmed
- **WHEN** the user confirms the factory reset
- **THEN** `POST /factory-reset` SHALL be called, a success toast SHALL appear, and the page SHALL reload after ~1.5 seconds
