## ADDED Requirements

### Requirement: SponsorBlock categories resolved at download time
The system SHALL resolve the effective SponsorBlock category list for a download job by checking the playlist's `sponsorblock_categories` field first. If it is `NULL`, the global `sponsorblock-categories` setting SHALL be used. If the global setting is absent, the default `["music_offtopic"]` SHALL be applied. If the resolved list is empty or `sponsorblock-enabled` is `false`, no `sponsorblock_remove` option SHALL be passed to yt-dlp.

#### Scenario: Per-playlist override used when set
- **WHEN** a playlist has `sponsorblock_categories = '["music_offtopic","intro"]'`
- **THEN** the downloader SHALL add `SponsorBlockPP` and `ModifyChaptersPP` post-processors with `remove_sponsor_segments={"music_offtopic", "intro"}` regardless of global settings

#### Scenario: Falls back to global when playlist has no override
- **WHEN** a playlist has `sponsorblock_categories = NULL` and global `sb-cats = ["music_offtopic"]`
- **THEN** the downloader SHALL add `SponsorBlockPP` and `ModifyChaptersPP` post-processors with `remove_sponsor_segments={"music_offtopic"}`

#### Scenario: SponsorBlock disabled when toggle is off
- **WHEN** global `sb-enabled = false`
- **THEN** the downloader SHALL NOT add any SponsorBlock post-processors

#### Scenario: SponsorBlock disabled when per-playlist categories empty
- **WHEN** a playlist has `sponsorblock_categories = ""`
- **THEN** the downloader SHALL NOT add any SponsorBlock post-processors

### Requirement: Global SponsorBlock settings persisted
The system SHALL persist two global settings keys in the `settings` table: `sb-enabled` (string `"true"` or `"false"`) and `sb-cats` (JSON-encoded array string, e.g. `'["music_offtopic"]'`). When absent, `sb-enabled` SHALL default to `"true"` and `sb-cats` SHALL default to `'["music_offtopic"]'`.

#### Scenario: Default applied on first use
- **WHEN** neither `sb-enabled` nor `sb-cats` exist in the settings table
- **THEN** the system SHALL behave as if `sb-enabled = true` and categories = `["music_offtopic"]`

#### Scenario: Settings persisted via API
- **WHEN** a PUT request is made to `/settings/sb-enabled` with value `"false"`
- **THEN** the setting SHALL be stored and subsequent reads SHALL return `"false"`

### Requirement: Per-playlist SponsorBlock column stored in DB
The `playlists` table SHALL have a nullable `sponsorblock_categories` TEXT column. `NULL` means use global. An empty string `""` means force-disabled for this playlist. A non-empty string SHALL be a JSON-encoded array of category keys.

#### Scenario: New playlist defaults to NULL
- **WHEN** a playlist is created without specifying `sponsorblock_categories`
- **THEN** `playlists.sponsorblock_categories` SHALL be `NULL`

#### Scenario: Per-playlist override stored on PATCH
- **WHEN** a PATCH request sets `sponsorblock_categories` to `["music_offtopic","intro"]`
- **THEN** the column SHALL be updated to the JSON string `'["music_offtopic","intro"]'`

### Requirement: SponsorBlock toggle in DownloadForm seeded from global default
The download form toggle labelled "SponsorBlock" SHALL be pre-populated from the global `sb-enabled` setting when the form loads. The selected category list is not shown in the form; it uses the global at submission time.

#### Scenario: Toggle seeded from global on mount
- **WHEN** the DownloadForm mounts and global `sb-enabled = true`
- **THEN** the "SponsorBlock" toggle SHALL be checked by default

#### Scenario: Toggle state committed at job submission
- **WHEN** user submits the form with the SponsorBlock toggle on
- **THEN** the job payload SHALL include `sponsorblock_enabled: true`

### Requirement: SponsorBlock toggle in PlaylistRow with immediate PATCH
The playlist row in the Library SHALL show a "SponsorBlock" toggle between "Auto rename" and "Sync". Clicking it SHALL immediately send a PATCH to `/playlists/<id>` updating `sponsorblock_enabled`. Toggle order SHALL be: Auto rename → SponsorBlock → Sync.

#### Scenario: Toggle fires immediate PATCH
- **WHEN** user clicks the "SponsorBlock" toggle in a playlist row
- **THEN** a PATCH request SHALL be sent immediately with `{ sponsorblock_enabled: <new state> }`

#### Scenario: Toggle reverts on API error
- **WHEN** the PATCH request fails
- **THEN** the toggle SHALL revert to its previous state

### Requirement: SponsorBlock section in Settings with enable toggle and category picker
The Settings page SHALL have a "SponsorBlock" section containing: (1) an enable/disable toggle row seeding `sb-enabled`; (2) a collapsible "Categories" row with chip toggles for each removable category. The chevron SHALL be disabled and greyed out when the toggle is off. Deselecting all chips SHALL automatically disable the toggle and close the chevron. A hyperlink to `https://sponsor.ajay.app` SHALL appear in the toggle row description.

#### Scenario: Chevron disabled when toggle is off
- **WHEN** the SponsorBlock toggle is off
- **THEN** the categories chevron SHALL be visually greyed out and non-interactive

#### Scenario: All chips deselected auto-disables toggle
- **WHEN** user deselects the last active chip
- **THEN** the toggle SHALL flip to off, the chevron SHALL close, and `sb-enabled` SHALL be saved as `"false"`

### Requirement: CLI config-playlist supports sb-cats key
`siphon config-playlist <name> sb-cats [<value>]` SHALL read or write the per-playlist `sponsorblock_categories` column. Accepted write values: a comma-separated category list (e.g. `"music_offtopic,intro"`) or a JSON array (e.g. `'["music_offtopic"]'`), both stored as a JSON array. An empty string and an empty array are both **rejected** — the user must run `siphon config-playlist <name> sponsorblock false` to disable SponsorBlock for a playlist. Unrecognised category keys SHALL be rejected with an error listing valid keys.

#### Scenario: Read shows current per-playlist categories
- **WHEN** user runs `siphon config-playlist "My Playlist" sb-cats` with no value
- **THEN** the current `sponsorblock_categories` value SHALL be printed, or `"(using global)"` if `NULL`

#### Scenario: Write stores JSON array
- **WHEN** user runs `siphon config-playlist "My Playlist" sb-cats "music_offtopic,intro"`
- **THEN** `sponsorblock_categories` SHALL be updated to `'["music_offtopic","intro"]'`

#### Scenario: Empty string rejected
- **WHEN** user runs `siphon config-playlist "My Playlist" sb-cats ""`
- **THEN** the CLI SHALL print an error directing the user to use `siphon config-playlist <name> sponsorblock false` and return exit code 1

#### Scenario: Invalid category rejected
- **WHEN** user runs `siphon config-playlist "My Playlist" sb-cats "fake_category"`
- **THEN** the CLI SHALL print an error listing valid category keys and return exit code 1

### Requirement: CLI config supports sponsorblock global keys
`siphon config sb-enabled [<value>]` and `siphon config sb-cats [<value>]` SHALL read or write the respective global settings keys. Valid values for `sb-enabled` are `true`/`false`. Valid values for `sb-cats` are a comma-separated list of valid category keys or a JSON array. Empty string and empty array are rejected; the user must use `sponsorblock false` to disable.

#### Scenario: Read global enabled state
- **WHEN** user runs `siphon config sb-enabled`
- **THEN** the current value SHALL be printed, defaulting to `true` if unset

#### Scenario: Write global categories
- **WHEN** user runs `siphon config sb-cats "music_offtopic,outro"`
- **THEN** the setting SHALL be stored as `'["music_offtopic","outro"]'`
