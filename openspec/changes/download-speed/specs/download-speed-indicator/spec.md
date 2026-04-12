## ADDED Requirements

### Requirement: SSE progress event broadcasts speed
The backend SHALL broadcast a named SSE event `progress` on the job stream (`/jobs/{job_id}/stream`) containing the current download speed whenever a yt-dlp progress tick with `status == "downloading"` is received.

#### Scenario: Active download emits speed
- **WHEN** yt-dlp fires a progress tick with `status == "downloading"` and `speed` is not `None`
- **THEN** the backend SHALL send an SSE event with `event: progress` and `data: {"speed": <float>}` to all subscribers of that job's stream

#### Scenario: Speed is unknown
- **WHEN** yt-dlp fires a progress tick with `status == "downloading"` and `speed` is `None`
- **THEN** the backend SHALL send an SSE event with `event: progress` and `data: {"speed": null}`

### Requirement: Queue header displays live speed
The `DownloadQueue` component SHALL display the current download speed next to the download count text (e.g. `3/10 downloaded · 1.2 MB/s`) while at least one item is actively downloading.

#### Scenario: Speed is available
- **WHEN** a `progress` SSE event is received with a non-null `speed` value
- **THEN** the queue header SHALL display the speed formatted as human-readable bytes/sec (e.g. `1.2 MB/s`, `800 KB/s`)

#### Scenario: Speed becomes null
- **WHEN** a `progress` SSE event is received with `speed: null`
- **THEN** the speed indicator SHALL be hidden (not shown as `0 B/s`)

#### Scenario: No active download
- **WHEN** no job has items in `downloading` state
- **THEN** the speed indicator SHALL not be displayed

### Requirement: Speed format
The frontend SHALL format speed in bytes/sec to a human-readable string using the nearest appropriate unit (B/s, KB/s, MB/s, GB/s) with at most one decimal place.

#### Scenario: Sub-megabyte speed
- **WHEN** speed is 512000 bytes/sec
- **THEN** the display SHALL show `500.0 KB/s`

#### Scenario: Megabyte-range speed
- **WHEN** speed is 1258291 bytes/sec
- **THEN** the display SHALL show `1.2 MB/s`
