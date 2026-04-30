## ADDED Requirements

### Requirement: `cookies-enabled` global config key
`cookies-enabled` SHALL be added to `_KNOWN_KEYS` with db key `cookies_enabled`. Accepted values SHALL be the strings `"true"` and `"false"`. The CLI `siphon config cookies-enabled [true|false]` SHALL read and write this key. If unset, the effective default (resolved in `get_cookie_file()`) SHALL be `"true"`.

#### Scenario: Write cookies-enabled
- **WHEN** `PUT /settings/cookies-enabled` is called with value `"false"`
- **THEN** the value SHALL be stored and subsequent reads SHALL return `"false"`

#### Scenario: Invalid value rejected
- **WHEN** `PUT /settings/cookies-enabled` is called with a value other than `"true"` or `"false"`
- **THEN** the response SHALL be `400 Bad Request`

#### Scenario: CLI read
- **WHEN** `siphon config cookies-enabled` is run with no value argument
- **THEN** the current stored value SHALL be printed, or a message indicating it is unset (defaulting to enabled)
