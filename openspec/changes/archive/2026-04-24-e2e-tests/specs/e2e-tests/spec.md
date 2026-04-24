## ADDED Requirements

### Requirement: E2E test suite covers the full Siphon stack via HTTP API
The project SHALL have a pytest-based e2e test suite under `tests/e2e/` that drives a real running Siphon daemon through its HTTP API, with no mocking of yt-dlp, YouTube, or MusicBrainz.

#### Scenario: Suite requires a running daemon on port 8000
- **WHEN** `pytest tests/e2e/` is executed
- **THEN** the conftest session fixture starts a `siphon start` subprocess and polls `GET /health` until it returns 200 before any test runs

#### Scenario: Factory-reset wipes state before the session
- **WHEN** the session fixture starts
- **THEN** `POST /factory-reset` is called before any test, ensuring no leftover playlists or jobs from previous runs

#### Scenario: Pre-flight check warns on port conflict
- **WHEN** port 8000 is already in use at conftest startup
- **THEN** a warning is printed to stdout; on local runs (CI env var absent) the user is prompted to press Y to continue or Ctrl-C to abort; on CI the warning is logged and execution continues automatically

#### Scenario: Pre-flight check warns on existing downloads
- **WHEN** the `downloads/` directory contains any files at conftest startup
- **THEN** a warning is printed listing the affected subdirectory; execution continues after the Y confirmation (local) or automatically (CI)

#### Scenario: Download-heavy tests are marked slow
- **WHEN** a test performs a real file download
- **THEN** the test is decorated with `@pytest.mark.slow`; running `pytest tests/e2e/ -m "not slow"` skips it

### Requirement: Health and version endpoints are reachable
The daemon SHALL respond correctly to health and version checks.

#### Scenario: Health endpoint returns 200
- **WHEN** `GET /health` is called on a running daemon
- **THEN** the response status is 200

#### Scenario: Version endpoint returns a version string
- **WHEN** `GET /version` is called
- **THEN** the response body contains a non-empty `version` string

### Requirement: Playlist sync retrieves real items from YouTube
The e2e suite SHALL verify that adding a playlist and triggering a sync populates real items.

#### Scenario: Sync populates items from a real playlist URL
- **WHEN** a playlist is added via `POST /playlists` and `POST /playlists/{id}/sync` is called
- **THEN** `GET /playlists/{id}/items` returns a list with at least one item, each having a non-empty `video_id` and `title`

#### Scenario: Syncing twice does not create duplicate items
- **WHEN** `POST /playlists/{id}/sync` is called a second time on the same playlist
- **THEN** `GET /playlists/{id}/items` returns the same count as after the first sync (no duplicates)

### Requirement: Scheduler auto-syncs a watched playlist without manual trigger
The scheduler SHALL fire a sync automatically after the configured interval.

#### Scenario: Short-interval playlist auto-syncs
- **WHEN** a playlist is added with `watched=true` and `interval=15` (seconds)
- **THEN** after waiting 20 seconds, `GET /playlists/{id}/items` returns at least one item without any manual sync call

#### Scenario: Interval change takes effect on the next cycle
- **WHEN** a playlist's interval is updated via `PATCH /playlists/{id}` while a timer is pending
- **THEN** the next sync fires at the new interval, not the old one

### Requirement: Single video download produces a valid file on disk
The e2e suite SHALL verify that a single video download results in a readable file.

#### Scenario: File exists on disk after job completes
- **WHEN** `POST /jobs` is called with a real video URL and the job reaches `done` status
- **THEN** at least one `.mp3` (or `.mp4`) file exists under `downloads/`

#### Scenario: Downloaded audio file is valid
- **WHEN** a single video download job completes
- **THEN** mutagen can open the resulting file and reports a duration greater than 0 seconds

#### Scenario: Job transitions through expected states
- **WHEN** a download job is submitted
- **THEN** `GET /jobs` shows the job moving through `pending` → `downloading` → `done` (polled until terminal)

### Requirement: Job cancellation stops an in-progress download
The e2e suite SHALL verify that cancelling an active job halts the download.

#### Scenario: Cancelled job reaches cancelled state
- **WHEN** `POST /jobs/cancel-all` is called while a download job is in `downloading` state
- **THEN** `GET /jobs` shows cancelled items and no remaining `pending` items within 10 seconds

### Requirement: Auto-rename produces correctly formatted filenames
The e2e suite SHALL verify that `auto_rename=true` renames downloaded files to the expected format.

#### Scenario: Auto-rename on produces Artist - Title filename
- **WHEN** a download job is submitted with `auto_rename=true`
- **THEN** the downloaded file on disk has a filename matching the pattern `<Artist> - <Title>.<ext>`

#### Scenario: Auto-rename off leaves raw yt-dlp filename
- **WHEN** a download job is submitted with `auto_rename=false`
- **THEN** the downloaded filename is the raw yt-dlp output (video ID or original title, no artist prefix)

#### Scenario: Unsafe characters in title are replaced with visual equivalents
- **WHEN** a video title contains filesystem-unsafe characters (e.g. `/`, `:`, `?`)
- **THEN** the filename on disk uses the visual-equivalent Unicode substitutions (e.g. `⧸`, `꞉`, `？`) rather than stripping the characters

#### Scenario: Noise patterns are stripped from filenames
- **WHEN** a video title contains a noise suffix such as `(Official Music Video)` or `[Official Audio]`
- **THEN** the filename on disk does not include the noise suffix

### Requirement: Renamer tier is recorded in the database
The e2e suite SHALL verify that the MusicBrainz rename tier is stored when a known track is downloaded with `auto_rename=true`. Other tiers (`yt_metadata`, `yt_title`) are not independently testable with a single deterministic video URL.

#### Scenario: musicbrainz tier used for known tracks
- **WHEN** a well-known track video is downloaded with `mb_user_agent` configured and `auto_rename=true`
- **THEN** the item's `rename_tier` is `musicbrainz`

### Requirement: MusicBrainz lookup embeds original title in ID3 tag
The e2e suite SHALL verify that the original YouTube title is preserved in the file's ID3 tags.

#### Scenario: TXXX:original_title tag is embedded after rename
- **WHEN** a file is downloaded and renamed (any tier)
- **THEN** mutagen shows a `TXXX:original_title` frame in the ID3 tags containing the original YouTube video title

### Requirement: Missing secrets cause graceful test skip
Tests that require secrets SHALL skip cleanly when the required env var is not set.

#### Scenario: Test skips when playlist URL secret is absent
- **WHEN** `E2E_PLAYLIST_URL` is not set in the environment
- **THEN** tests depending on it are skipped with a clear skip message, not failed
