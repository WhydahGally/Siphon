## ADDED Requirements

### Requirement: SB unavailable modal shown before download when SB is enabled
When a user initiates a download (single or playlist) with SponsorBlock enabled, the UI SHALL call `GET /health/sponsorblock` first. If the response is unhealthy, a modal dialog SHALL appear informing the user and presenting action choices.

#### Scenario: SB healthy — download proceeds
- **WHEN** user clicks Download with SB enabled AND `/health/sponsorblock` returns healthy
- **THEN** the download SHALL proceed normally without any modal

#### Scenario: SB unhealthy — modal shown
- **WHEN** user clicks Download with SB enabled AND `/health/sponsorblock` returns unhealthy
- **THEN** a modal SHALL appear with title "SponsorBlock Unavailable", body text explaining the issue, and two action buttons

#### Scenario: User clicks "Register only"
- **WHEN** the SB unavailable modal is shown AND user clicks "Register only"
- **THEN** the playlist/video SHALL be registered in the library without downloading any files
- **THEN** the modal SHALL close

#### Scenario: User clicks "Download anyway"
- **WHEN** the SB unavailable modal is shown AND user clicks "Download anyway"
- **THEN** the download SHALL proceed with `sponsorblock_enabled = false` for that playlist
- **THEN** the playlist's `sponsorblock_enabled` SHALL be persisted as `false`
- **THEN** the modal SHALL close

#### Scenario: User dismisses modal via overlay or ✕
- **WHEN** the SB unavailable modal is shown AND user clicks the overlay or ✕ button
- **THEN** the modal SHALL close and no download or registration SHALL occur

### Requirement: Scheduler respects sb_require_for_sync setting
When `sb_require_for_sync` is `"true"`, the scheduler SHALL check SB health before each sync cycle. If unhealthy, the sync SHALL be skipped and a warning appended to the playlist.

#### Scenario: Setting ON and SB healthy
- **WHEN** `sb_require_for_sync` is `"true"` AND the scheduler triggers a sync AND SB health check returns healthy
- **THEN** the sync SHALL proceed normally

#### Scenario: Setting ON and SB unhealthy
- **WHEN** `sb_require_for_sync` is `"true"` AND the scheduler triggers a sync AND SB health check returns unhealthy
- **THEN** the sync SHALL be skipped
- **THEN** a warning `{type: "sponsorblock", message: "Sync skipped: SponsorBlock unavailable"}` SHALL be appended to the playlist's `warnings`

#### Scenario: Setting OFF (default)
- **WHEN** `sb_require_for_sync` is `"false"` or absent
- **THEN** the scheduler SHALL NOT perform an SB health check before syncing
