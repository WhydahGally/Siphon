### Requirement: `GET /version` endpoint
The daemon SHALL expose a `GET /version` endpoint that returns a JSON object with the fields `siphon` (the installed package version read via `importlib.metadata`) and `yt_dlp` (the yt-dlp library version).

#### Scenario: Version response
- **WHEN** `GET /version` is called
- **THEN** the response SHALL be `200 OK` with body `{ "siphon": "<semver>", "yt_dlp": "<date-ver>" }`

---

### Requirement: `DELETE /playlists` endpoint and `siphon delete-all-playlists` command
The daemon SHALL expose a `DELETE /playlists` endpoint that removes all rows from the `playlists`, `downloaded_items`, `failed_downloads`, and `ignored_items` tables and removes all watchers from the `PlaylistScheduler`. The `settings` table SHALL be left intact. The response SHALL be `204 No Content`. The CLI SHALL expose a `siphon delete-all-playlists` subcommand that calls this endpoint and prints a confirmation message on success.

#### Scenario: All playlists deleted via API
- **WHEN** `DELETE /playlists` is called with one or more playlists registered
- **THEN** all playlist rows and associated history SHALL be removed, the PlaylistScheduler SHALL have no remaining watchers, the `settings` table SHALL be unchanged, and the response SHALL be `204`

#### Scenario: No playlists exist
- **WHEN** `DELETE /playlists` is called with no registered playlists
- **THEN** the response SHALL still be `204` with no error

#### Scenario: CLI delete-all-playlists command
- **WHEN** `siphon delete-all-playlists` is run
- **THEN** `DELETE /playlists` SHALL be called on the daemon and a confirmation message SHALL be printed to stdout

---

### Requirement: `POST /factory-reset` endpoint and `siphon factory-reset` command
The daemon SHALL expose a `POST /factory-reset` endpoint that performs a full database wipe: all rows in `playlists`, `downloaded_items`, `failed_downloads`, `ignored_items`, and `settings` SHALL be deleted. All `PlaylistScheduler` watchers SHALL be removed. The response SHALL be `204 No Content`. The CLI SHALL expose a `siphon factory-reset` subcommand that calls this endpoint and prints a confirmation message on success.

#### Scenario: Factory reset via API
- **WHEN** `POST /factory-reset` is called
- **THEN** all DB tables SHALL be empty, the PlaylistScheduler SHALL have no watchers, and the response SHALL be `204`

#### Scenario: CLI factory-reset command
- **WHEN** `siphon factory-reset` is run
- **THEN** `POST /factory-reset` SHALL be called on the daemon and a confirmation message SHALL be printed to stdout

---

### Requirement: `auto-rename` global config key
`auto-rename` SHALL be added to `_KNOWN_KEYS` with db key `auto_rename_default`. Accepted values via `PUT /settings/auto-rename` SHALL be the strings `"true"` and `"false"`. The CLI `siphon config auto-rename [true|false]` SHALL read and write this key. If unset, the effective default SHALL be `"true"`.

#### Scenario: Read unset auto-rename
- **WHEN** `GET /settings/auto-rename` is called and the key has never been set
- **THEN** the response value SHALL be `null`

#### Scenario: Write auto-rename
- **WHEN** `PUT /settings/auto-rename` is called with value `"false"`
- **THEN** the value SHALL be stored and subsequent reads SHALL return `"false"`

#### Scenario: Invalid value rejected
- **WHEN** `PUT /settings/auto-rename` is called with a value other than `"true"` or `"false"`
- **THEN** the response SHALL be `400 Bad Request`

---

### Requirement: `theme` global config key
`theme` SHALL be added to `_KNOWN_KEYS` with db key `theme`. Accepted values via `PUT /settings/theme` SHALL be `"dark"` and `"light"`. If unset, the effective default SHALL be `"dark"`. The CLI `siphon config theme [dark|light]` SHALL read and write this key.

#### Scenario: Write theme
- **WHEN** `PUT /settings/theme` is called with value `"light"`
- **THEN** the value SHALL be stored and subsequent reads SHALL return `"light"`

#### Scenario: Invalid value rejected
- **WHEN** `PUT /settings/theme` is called with a value other than `"dark"` or `"light"`
- **THEN** the response SHALL be `400 Bad Request`

---

### Requirement: `title-noise-patterns` global config key
`title-noise-patterns` SHALL be added to `_KNOWN_KEYS` with db key `title_noise_patterns`. The value SHALL be stored as a JSON-encoded array of regex pattern strings. The CLI `siphon config title-noise-patterns` SHALL read and write this key. If unset, the effective value is `null` and the renamer SHALL use its built-in default pattern list.

`PUT /settings/title-noise-patterns` SHALL validate that the submitted value is a valid JSON array of strings. Each string SHALL be validated as a compilable Python regex before storing. If validation fails the response SHALL be `400 Bad Request` with a message identifying the invalid pattern.

#### Scenario: Read unset title-noise-patterns
- **WHEN** `GET /settings/title-noise-patterns` is called and the key has never been set
- **THEN** the response value SHALL be `null`

#### Scenario: Write valid patterns
- **WHEN** `PUT /settings/title-noise-patterns` is called with a valid JSON array of regex strings
- **THEN** the value SHALL be stored and subsequent reads SHALL return the same array

#### Scenario: Write invalid JSON rejected
- **WHEN** `PUT /settings/title-noise-patterns` is called with a value that is not valid JSON or not a JSON array
- **THEN** the response SHALL be `400 Bad Request`

#### Scenario: Write invalid regex rejected
- **WHEN** `PUT /settings/title-noise-patterns` is called with a JSON array containing a string that is not a valid Python regex
- **THEN** the response SHALL be `400 Bad Request` with a message identifying the offending pattern

---

### Requirement: Theme initialisation before Vue mount
`main.js` SHALL call `GET /settings/theme` before mounting the Vue application. If the returned value is `"light"`, it SHALL set `document.documentElement.dataset.theme = "light"` before calling `app.mount()`. If the daemon is unreachable or the value is `"dark"` / absent, no attribute SHALL be set and the dark default applies.

#### Scenario: Light theme persisted
- **WHEN** the user previously saved `theme = "light"` and reloads the page
- **THEN** the light colour scheme SHALL be applied before the first rendered frame (no flash of dark mode)

#### Scenario: Daemon unreachable on load
- **WHEN** the daemon is not running when the page loads
- **THEN** the page SHALL still mount and render in dark mode

---

### Requirement: Light mode CSS
`style.css` SHALL define a `[data-theme="light"]` rule block that overrides `--bg`, `--surface`, `--surface-2`, `--border`, `--text`, and `--text-muted` with light-appropriate values. The accent colour (`--accent`, `--accent-hover`) SHALL remain unchanged between themes.

#### Scenario: Light theme applied
- **WHEN** `document.documentElement.dataset.theme` is set to `"light"`
- **THEN** all background and text surfaces SHALL use the light palette and the accent colour SHALL remain the same

---

### Requirement: `DownloadForm` reads auto-rename default
On mount, `DownloadForm.vue` SHALL call `GET /settings/auto-rename`. If the returned value is `"false"`, the auto-rename checkbox SHALL default to unchecked. Otherwise (value is `"true"`, `null`, or the daemon is unreachable) it SHALL default to checked.

#### Scenario: Global default is false
- **WHEN** `auto-rename` is set to `"false"` and the user opens the Dashboard
- **THEN** the auto-rename checkbox on the Download form SHALL be unchecked by default

#### Scenario: Global default unset
- **WHEN** `auto-rename` has never been set
- **THEN** the auto-rename checkbox SHALL be checked by default
