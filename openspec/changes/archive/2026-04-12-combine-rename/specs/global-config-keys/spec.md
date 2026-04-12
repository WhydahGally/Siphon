## ADDED Requirements

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
