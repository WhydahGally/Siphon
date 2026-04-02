## ADDED Requirements

### Requirement: Progress callback interface
The engine SHALL call the `progress_callback` with a single dict argument on each yt-dlp progress event. The callback is optional; if not provided, progress events are silently dropped.

#### Scenario: Callback provided
- **WHEN** a `progress_callback` is passed to `download()` and a download is in progress
- **THEN** the engine SHALL call it with a dict on each progress tick

#### Scenario: No callback provided
- **WHEN** `progress_callback` is `None`
- **THEN** the engine SHALL proceed without error and emit no progress output

---

### Requirement: Progress event shape
Each progress event dict passed to the callback SHALL contain the following fields:

- `status`: one of `"downloading"`, `"finished"`, `"error"`
- `filename`: the local file path being written (str)
- `downloaded_bytes`: bytes downloaded so far (int, may be None if unknown)
- `total_bytes`: total expected bytes (int, may be None if unknown)
- `speed`: download speed in bytes/sec (float, may be None)
- `eta`: estimated seconds remaining (int, may be None)

#### Scenario: Downloading event
- **WHEN** a file download is in progress
- **THEN** the callback SHALL receive a dict with `status="downloading"` and available byte/speed/eta fields

#### Scenario: Finished event
- **WHEN** a file download completes
- **THEN** the callback SHALL receive a dict with `status="finished"` and the final `filename`

#### Scenario: Error event
- **WHEN** yt-dlp reports a download error for an item
- **THEN** the callback SHALL receive a dict with `status="error"` and `filename` set to the attempted path

---

### Requirement: Callback error isolation
If the progress callback raises an exception, the engine SHALL catch it, log a WARNING, and continue the download. A misbehaving callback SHALL NOT abort a download.

#### Scenario: Callback raises an exception
- **WHEN** the progress callback throws any exception
- **THEN** the engine SHALL log a WARNING and continue downloading the current item
