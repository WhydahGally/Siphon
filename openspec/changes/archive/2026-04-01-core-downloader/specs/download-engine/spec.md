## ADDED Requirements

### Requirement: Single public download function
The engine SHALL expose one public function `download(url, output_dir, options, progress_callback=None)` that accepts a YouTube URL (playlist or single video), an output directory path, a format/quality options object, and an optional progress callback.

#### Scenario: Playlist URL is provided
- **WHEN** a playlist URL is passed to `download()`
- **THEN** the engine SHALL fetch playlist metadata and download each video item in sequence under `<output_dir>/<playlist_title>/`

#### Scenario: Single video URL is provided
- **WHEN** a single video URL is passed to `download()`
- **THEN** the engine SHALL download that one video directly into `<output_dir>/`

---

### Requirement: Consistent per-item lifecycle
Every downloaded item (whether from a playlist or a single-video call) SHALL pass through the same per-item processing steps: resolve output path → download via yt-dlp → invoke renamer hook.

#### Scenario: Item from playlist goes through lifecycle
- **WHEN** an item is downloaded as part of a playlist
- **THEN** the renamer hook SHALL be called with the completed file path after download

#### Scenario: Single video goes through lifecycle
- **WHEN** a single video is downloaded
- **THEN** the renamer hook SHALL be called with the completed file path after download

---

### Requirement: Unavailable video handling
When a video in a playlist is unavailable (private, deleted, region-blocked), the engine SHALL log a warning and continue downloading the remaining items. It SHALL NOT abort the entire playlist.

#### Scenario: One video in playlist is unavailable
- **WHEN** yt-dlp reports a video as unavailable during a playlist download
- **THEN** the engine SHALL log a WARNING with the video title/ID and continue to the next item

---

### Requirement: Missing resolution fallback
When the requested video resolution is not available for a specific video, the engine SHALL log a warning and allow yt-dlp to fall back to the next best available resolution.

#### Scenario: Requested resolution not found
- **WHEN** a video does not have the requested resolution (e.g., no 4K stream)
- **THEN** the engine SHALL log a WARNING and download the best available resolution instead

---

### Requirement: No direct output in engine
The engine SHALL NOT call `print()` or write directly to stdout/stderr. All user-facing output is the responsibility of the caller via the progress callback and Python logging.

#### Scenario: Download in progress
- **WHEN** a download is in progress
- **THEN** the engine SHALL emit progress via the callback and write to the logger only — never to stdout directly

---

### Requirement: ffmpeg presence check for MP3 mode and video remuxing
When MP3 audio format is requested, the engine SHALL verify that `ffmpeg` is available on the system PATH before starting any downloads. ffmpeg is also required when `video_format` is `mp4` or `mkv`, as yt-dlp uses it to remux the merged streams.

#### Scenario: MP3 requested but ffmpeg missing
- **WHEN** `options.audio_format` is `mp3` and `ffmpeg` is not found on PATH
- **THEN** the engine SHALL raise a clear error immediately, before any download begins

#### Scenario: MP3 requested and ffmpeg present
- **WHEN** `options.audio_format` is `mp3` and `ffmpeg` is found on PATH
- **THEN** the engine SHALL proceed normally

#### Scenario: mp4 or mkv video format requested but ffmpeg missing
- **WHEN** `options.video_format` is `mp4` or `mkv` and `ffmpeg` is not found on PATH
- **THEN** the engine SHALL raise a clear error immediately, before any download begins

---

### Requirement: Runnable entry point for testing
The module SHALL include a `__main__` block that accepts CLI arguments (`url`, `--output-dir`, `--format`, `--quality`) and invokes `download()` with a simple stdout progress callback.

#### Scenario: Run as script
- **WHEN** the module is executed with `python -m siphon.downloader <url> --format mp3`
- **THEN** it SHALL parse arguments and begin downloading, printing progress to stdout
