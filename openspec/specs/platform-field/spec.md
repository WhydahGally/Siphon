### Requirement: Platform stored per playlist
The system SHALL store a `platform` field on each registered playlist, derived from yt-dlp's `extractor_key` at registration time. The value SHALL be sanitized to remove yt-dlp-internal suffixes (`Tab`, `Playlist`, `Channel`, `Album`, `User`, `Search`, `Feed`, `Tag`, `Set`, `IE`) so that only the human-readable platform name remains (e.g. `Youtube`, `Soundcloud`, `Bandcamp`).

#### Scenario: YouTube playlist is registered
- **WHEN** a YouTube playlist URL is submitted to `POST /playlists`
- **THEN** the playlist record SHALL have `platform = "Youtube"`

#### Scenario: Non-YouTube URL is registered
- **WHEN** a SoundCloud sets URL is submitted to `POST /playlists`
- **THEN** the playlist record SHALL have `platform = "Soundcloud"`

#### Scenario: Extractor key has yt-dlp suffix
- **WHEN** yt-dlp returns `extractor_key = "YoutubeTab"` for a channel URL
- **THEN** the stored `platform` value SHALL be `"Youtube"` (suffix stripped)

#### Scenario: Extractor key ends in `Set`
- **WHEN** yt-dlp returns `extractor_key = "SoundcloudSet"` for a sets URL
- **THEN** the stored `platform` value SHALL be `"Soundcloud"` (suffix stripped)

#### Scenario: Unrecognised extractor
- **WHEN** yt-dlp returns an `extractor_key` with no known suffix
- **THEN** the full `extractor_key` value SHALL be stored as-is

---

### Requirement: Platform stored for direct downloads
The system SHALL also extract and store `platform` when a URL is submitted directly to `POST /jobs` (ad-hoc download without pre-registering a playlist). The same `sanitize_platform()` logic applies.

#### Scenario: Direct download stores platform
- **WHEN** a URL is submitted to `POST /jobs`
- **THEN** the created playlist record SHALL have its `platform` populated using the same extractor-key sanitization as `POST /playlists`

---

### Requirement: Platform exposed in API responses
The `platform` field SHALL be included in every playlist object returned by the API (`GET /playlists`, `GET /playlists/{id}`, and all responses that embed playlist data).

#### Scenario: List playlists includes platform
- **WHEN** `GET /playlists` is called
- **THEN** each playlist object in the response SHALL include a `platform` key with the stored value (or `null` if not set)

---

### Requirement: Platform visible in library UI
The library tab playlist list SHALL display the `platform` value as part of the playlist meta area (alongside existing fields such as format and item count).

#### Scenario: Platform shown in meta area
- **WHEN** a playlist is displayed in the library tab
- **THEN** the playlist meta area SHALL show the platform name (e.g. "Youtube", "Soundcloud")

#### Scenario: Platform null or missing
- **WHEN** a playlist has no `platform` value (e.g. added before this change)
- **THEN** the platform field SHALL be hidden or shown as empty in the UI without error
