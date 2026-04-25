## ADDED Requirements

### Requirement: Playlist detection via yt-dlp info type
The `download()` function SHALL determine whether a URL refers to a playlist or a single video by inspecting the `_type` field of the yt-dlp info dict (obtained via a lightweight `extract_flat` pre-flight call), NOT by parsing the URL string. A `_type` value of `"playlist"` or `"channel"` SHALL be treated as a playlist; all other values SHALL be treated as a single video.

#### Scenario: YouTube playlist URL
- **WHEN** `download()` is called with a YouTube playlist URL
- **THEN** yt-dlp's info dict SHALL return `_type = "playlist"` and the output template SHALL use `<output_dir>/<playlist_title>/<title>.<ext>`

#### Scenario: SoundCloud sets URL
- **WHEN** `download()` is called with a SoundCloud `/sets/` URL
- **THEN** yt-dlp's info dict SHALL return `_type = "playlist"` and the output template SHALL use `<output_dir>/<playlist_title>/<title>.<ext>`

#### Scenario: Single video URL from any platform
- **WHEN** `download()` is called with a single video URL (any platform)
- **THEN** yt-dlp's info dict SHALL return `_type = "video"` (or absent) and the output template SHALL use `<output_dir>/<title>.<ext>`

#### Scenario: Channel URL treated as playlist
- **WHEN** `download()` is called with a channel URL
- **THEN** yt-dlp's info dict SHALL return `_type = "channel"` and the output template SHALL use the playlist-style template

#### Scenario: No URL string parsing for platform detection
- **WHEN** `download()` is called with any URL
- **THEN** the detection logic SHALL NOT inspect the URL string for platform-specific patterns (no `"list=" in url` checks)
