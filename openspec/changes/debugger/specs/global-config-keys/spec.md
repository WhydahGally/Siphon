## ADDED Requirements

### Requirement: `browser-logs` global config key
`browser-logs` SHALL be added to `_KNOWN_KEYS` with db key `browser_logs`. Accepted values via `PUT /settings/browser-logs` SHALL be the strings `"on"` and `"off"`. The CLI `siphon config browser-logs [on|off]` SHALL read and write this key. If unset, the effective default SHALL be `"off"`.

#### Scenario: Read unset browser-logs
- **WHEN** `GET /settings/browser-logs` is called and the key has never been set
- **THEN** the response value SHALL be `null` (callers treat as `"off"`)

#### Scenario: Write browser-logs on
- **WHEN** `PUT /settings/browser-logs` is called with value `"on"`
- **THEN** the value SHALL be stored and subsequent reads SHALL return `"on"`

#### Scenario: Invalid value rejected
- **WHEN** `PUT /settings/browser-logs` is called with a value other than `"on"` or `"off"`
- **THEN** the response SHALL be `400 Bad Request`

#### Scenario: CLI read browser-logs
- **WHEN** `siphon config browser-logs` is run with no value argument
- **THEN** the current stored value SHALL be printed (or `"off"` if unset)

#### Scenario: CLI write browser-logs
- **WHEN** `siphon config browser-logs on` is run
- **THEN** `PUT /settings/browser-logs` SHALL be called with value `"on"`
