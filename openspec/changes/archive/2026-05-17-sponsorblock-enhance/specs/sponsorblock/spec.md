## ADDED Requirements

### Requirement: sb_require_for_sync global setting
The system SHALL persist a global setting key `sb-require-for-sync` in the `settings` table. Valid values are `"true"` or `"false"`. When absent, the system SHALL default to `"false"`.

#### Scenario: Default value when absent
- **WHEN** `sb-require-for-sync` does not exist in the settings table
- **THEN** the system SHALL behave as if the value is `"false"`

#### Scenario: Setting persisted via API
- **WHEN** a PUT request is made to `/settings/sb-require-for-sync` with value `"true"`
- **THEN** the setting SHALL be stored and subsequent reads SHALL return `"true"`

### Requirement: Playlists table has warnings column
The `playlists` table SHALL have a nullable `warnings TEXT` column containing a JSON array of warning objects. Each object SHALL have `type` (string), `message` (string), and `timestamp` (ISO 8601 string). `NULL` or `"[]"` means no active warnings.

#### Scenario: Column exists after migration
- **WHEN** the application starts with an existing database
- **THEN** the `playlists` table SHALL contain the `warnings` column defaulting to `NULL`

#### Scenario: Warnings included in playlist API response
- **WHEN** a GET request is made to `/playlists` or `/playlists/<id>`
- **THEN** the response SHALL include the `warnings` field (parsed JSON array, or empty array if NULL)

### Requirement: Warning triangle shown in Library UI for playlists with warnings
The Library playlist list SHALL display a ⚠ icon next to playlists that have a non-empty `warnings` array. Hovering the icon SHALL show the warning messages as a tooltip.

#### Scenario: Warning icon visible
- **WHEN** a playlist has `warnings` containing one or more entries
- **THEN** a ⚠ icon SHALL be displayed in the playlist row

#### Scenario: No warning icon when clean
- **WHEN** a playlist has `warnings` that is `NULL` or empty
- **THEN** no ⚠ icon SHALL be displayed

#### Scenario: Tooltip shows warning details
- **WHEN** user hovers over the ⚠ icon
- **THEN** a tooltip SHALL display all warning messages from the `warnings` array

### Requirement: Settings UI exposes sb_require_for_sync toggle
The Settings page SponsorBlock section SHALL include a toggle row labelled "Require SponsorBlock for sync" below the existing SB enable toggle. The toggle SHALL read/write the `sb-require-for-sync` setting. It SHALL be disabled (greyed out) when the main SponsorBlock toggle is off.

#### Scenario: Toggle reflects current setting
- **WHEN** the Settings page loads AND `sb-require-for-sync` is `"true"`
- **THEN** the "Require SponsorBlock for sync" toggle SHALL be checked

#### Scenario: Toggle disabled when SB is off
- **WHEN** the main SponsorBlock enable toggle is off
- **THEN** the "Require SponsorBlock for sync" toggle SHALL be visually disabled and non-interactive

#### Scenario: Toggle writes setting on change
- **WHEN** user toggles "Require SponsorBlock for sync" to on
- **THEN** a PUT request SHALL be sent to `/settings/sb-require-for-sync` with value `"true"`
