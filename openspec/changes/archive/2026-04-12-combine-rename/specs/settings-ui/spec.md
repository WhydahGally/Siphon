## ADDED Requirements

### Requirement: MusicBrainz section — title noise patterns editor
The MusicBrainz section SHALL contain a collapsible noise patterns editor below the user-agent input. A labelled button ("Edit noise patterns") SHALL toggle the visibility of the editor. When expanded, the editor SHALL display a textarea pre-populated with the currently stored `title-noise-patterns` value (one pattern per line). If no value is stored, the textarea SHALL be empty and a muted description SHALL state that the built-in defaults are active. An explicit Save button SHALL call `PUT /settings/title-noise-patterns` and show a success toast. A Cancel button SHALL collapse the editor and discard unsaved changes. The editor SHALL be collapsed by default.

#### Scenario: Editor collapsed on page load
- **WHEN** the Settings page mounts
- **THEN** the noise patterns textarea SHALL NOT be visible; only the "Edit noise patterns" toggle button SHALL be shown

#### Scenario: Editor expands and loads stored patterns
- **WHEN** the user clicks "Edit noise patterns"
- **THEN** the textarea SHALL expand and be pre-populated with the value from `GET /settings/title-noise-patterns`, with each pattern on its own line

#### Scenario: Editor expands with no stored patterns
- **WHEN** the user clicks "Edit noise patterns" and no patterns are stored
- **THEN** the textarea SHALL be empty and a muted note SHALL indicate that built-in defaults are in use

#### Scenario: Save persists patterns
- **WHEN** the user edits the textarea and presses Save
- **THEN** `PUT /settings/title-noise-patterns` SHALL be called with the textarea content encoded as a JSON array (one pattern per non-empty line) and a success toast SHALL appear

#### Scenario: Cancel discards changes
- **WHEN** the user edits the textarea and presses Cancel
- **THEN** no API call SHALL be made, the textarea SHALL revert to its last saved value, and the editor SHALL collapse

#### Scenario: Save with invalid regex
- **WHEN** the user saves a pattern that the server rejects as an invalid regex
- **THEN** an error toast SHALL appear with the server's error message and the editor SHALL remain open
