## ADDED Requirements

### Requirement: Browser logs toggle in Settings UI
The Settings page SHALL include a labelled toggle for "Browser logs" in a new **Debugging** section placed between **Appearance** and **About**. The toggle state SHALL reflect `browser-logs` from `GET /settings/browser-logs` on mount; if unset it SHALL default to off. Changing the toggle SHALL immediately call `PUT /settings/browser-logs` and auto-save silently (no success toast). A muted description SHALL explain that enabling this streams daemon logs to the browser's developer console.

#### Scenario: Default state on first load
- **WHEN** `browser-logs` has never been set
- **THEN** the toggle SHALL be in the off/disabled state

#### Scenario: Toggle enabled
- **WHEN** the user flips the toggle to on
- **THEN** `PUT /settings/browser-logs` SHALL be called with value `"on"` silently (no toast)

#### Scenario: Toggle disabled
- **WHEN** the user flips the toggle to off
- **THEN** `PUT /settings/browser-logs` SHALL be called with value `"off"` silently (no toast)

### Requirement: Updated console info message
The `console.info` line in `App.vue` that prints the DB directory SHALL be updated to read `"[siphon] DB & logs directory:"` followed by the directory path.

#### Scenario: Console message on page load
- **WHEN** the app loads and `/info` returns successfully
- **THEN** the browser console SHALL show `[siphon] DB & logs directory: {path}`
