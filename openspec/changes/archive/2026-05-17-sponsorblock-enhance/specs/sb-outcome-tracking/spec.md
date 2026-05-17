## ADDED Requirements

### Requirement: Per-item SponsorBlock outcome recorded via postprocessor hooks
The system SHALL register a `postprocessor_hooks` callback on each `YoutubeDL` instance. After the `SponsorBlock` post-processor finishes for an item, the system SHALL determine the outcome and store it in the items table `sb_outcome` column.

#### Scenario: SB disabled for this download
- **WHEN** an item is downloaded with SponsorBlock disabled (toggle off or `sponsorblock_enabled = false`)
- **THEN** the `sb_outcome` column SHALL be set to `"disabled"`

#### Scenario: Segments found and removed
- **WHEN** the `SponsorBlock` post-processor finishes and `info_dict['sponsorblock_chapters']` is a non-empty list
- **THEN** the `sb_outcome` column SHALL be set to `"success"`

#### Scenario: No segments available for this video
- **WHEN** the `SponsorBlock` post-processor finishes and `info_dict['sponsorblock_chapters']` is empty or absent AND no SponsorBlock-related warning was logged
- **THEN** the `sb_outcome` column SHALL be set to `"no_segments"`

#### Scenario: SponsorBlock processing failed
- **WHEN** the `SponsorBlock` post-processor finishes and `info_dict['sponsorblock_chapters']` is empty or absent AND a SponsorBlock-related warning was captured by the logger
- **THEN** the `sb_outcome` column SHALL be set to `"failed"`

### Requirement: Items table has sb_outcome column
The `items` table SHALL have a nullable `sb_outcome TEXT` column. Valid values are `"disabled"`, `"success"`, `"no_segments"`, `"failed"`, or `NULL` (for items downloaded before this feature).

#### Scenario: Column exists after migration
- **WHEN** the application starts with an existing database
- **THEN** the `items` table SHALL contain the `sb_outcome` column with `NULL` default

### Requirement: Playlist warnings aggregated from item SB failures
After a sync or batch download completes, the system SHALL count items with `sb_outcome = "failed"` for that playlist. If count > 0, a warning entry `{type: "sponsorblock", message: "N items failed SponsorBlock processing", timestamp: "<ISO>"}` SHALL be appended to the playlist's `warnings` column. If count is 0, any existing `sponsorblock` warnings SHALL be cleared.

#### Scenario: Some items failed SB
- **WHEN** a sync completes and 3 items have `sb_outcome = "failed"`
- **THEN** the playlist's `warnings` column SHALL contain `[{"type": "sponsorblock", "message": "3 items failed SponsorBlock processing", "timestamp": "..."}]`

#### Scenario: All items succeeded
- **WHEN** a sync completes and 0 items have `sb_outcome = "failed"`
- **THEN** any existing `sponsorblock` entry in the playlist's `warnings` column SHALL be removed
