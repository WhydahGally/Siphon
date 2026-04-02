## ADDED Requirements

### Requirement: Single public download function
The engine SHALL expose one public function `download(url, output_dir, options, progress_callback=None, mb_user_agent=None, auto_rename=False, on_item_complete=None)`. The `on_item_complete` parameter is an optional callable that receives an `ItemRecord` after each item is fully downloaded and renamed.

`ItemRecord` fields:
- `video_id` (str)
- `playlist_id` (str | None): the YT playlist ID if this download is part of a playlist, else None
- `yt_title` (str)
- `renamed_to` (str | None): final filename stem; None if renamer returned None
- `rename_tier` (str | None)
- `uploader` (str | None)
- `channel_url` (str | None)
- `duration_secs` (int | None)

#### Scenario: Playlist URL is provided
- **WHEN** a playlist URL is passed to `download()`
- **THEN** the engine SHALL fetch playlist metadata and download each video item in sequence under `<output_dir>/<playlist_title>/`

#### Scenario: Single video URL is provided
- **WHEN** a single video URL is passed to `download()`
- **THEN** the engine SHALL download that one video directly into `<output_dir>/`

#### Scenario: Playlist URL with on_item_complete provided
- **WHEN** a playlist URL is passed and `on_item_complete` is a callable
- **THEN** after each item is fully processed (downloaded + renamed), the engine SHALL invoke `on_item_complete` with a populated `ItemRecord`. Errors raised inside the callback SHALL be caught, logged as WARNING, and SHALL NOT abort the download.

#### Scenario: Playlist URL without on_item_complete
- **WHEN** a playlist URL is passed and `on_item_complete` is None
- **THEN** the engine SHALL behave exactly as before — no callback is invoked

#### Scenario: Single video URL with on_item_complete provided
- **WHEN** a single video URL is passed and `on_item_complete` is a callable
- **THEN** the engine SHALL invoke `on_item_complete` with a populated `ItemRecord` after the item is processed. `ItemRecord.playlist_id` SHALL be None.

---

### Requirement: Consistent per-item lifecycle
Every downloaded item (whether from a playlist or a single-video call) SHALL pass through the same per-item processing steps: resolve output path → download via yt-dlp → run all postprocessors → invoke renamer hook with full metadata.

#### Scenario: Item from playlist goes through lifecycle
- **WHEN** an item is downloaded as part of a playlist
- **THEN** the renamer hook SHALL be called with the full yt-dlp `info_dict` after all postprocessors (including ffmpeg) have completed

#### Scenario: Single video goes through lifecycle
- **WHEN** a single video is downloaded
- **THEN** the renamer hook SHALL be called with the full yt-dlp `info_dict` after all postprocessors have completed

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

---

### Requirement: PostProcessor registration for renaming
The engine SHALL register a yt-dlp `PostProcessor` subclass (`_RenamePostProcessor`) via `ydl.add_post_processor(..., when="after_move")`. This fires once per video after all postprocessors (including ffmpeg) have completed and the file has been moved to its final output path, providing a complete `info_dict` including the final `filepath`.

Note: yt-dlp's `post_hooks` list was considered but rejected — it receives only a filename string, not the full `info_dict` required by the rename chain.

#### Scenario: PostProcessor fires after all postprocessors
- **WHEN** yt-dlp completes all postprocessors for a video (e.g. ffmpeg transcoding)
- **THEN** `_RenamePostProcessor.run(info)` SHALL be called with the complete `info_dict` and SHALL invoke `renamer.rename_file(info_dict)`

#### Scenario: PostProcessor does not interfere with progress_hooks
- **WHEN** a download is in progress
- **THEN** the `progress_hooks` SHALL continue to fire independently of the PostProcessor

---

### Requirement: MB User-Agent CLI argument
The engine's `__main__` entry point SHALL accept an optional `--mb-user-agent` argument whose value is passed through to the rename chain for each video in the session.

#### Scenario: --mb-user-agent provided
- **WHEN** `python -m siphon.downloader --url <url> --format mp3 --mb-user-agent "Siphon/1.0 (example.com)"`
- **THEN** the engine SHALL pass the User-Agent string to the renamer for use in MusicBrainz lookups

#### Scenario: --mb-user-agent omitted
- **WHEN** `python -m siphon.downloader --url <url> --format mp3` is run without `--mb-user-agent`
- **THEN** the engine SHALL pass `None` as the User-Agent and the renamer SHALL skip the MusicBrainz tier

---

### Requirement: Auto-rename CLI argument
The engine's `__main__` entry point SHALL accept an optional `--auto-rename` boolean flag. When absent the rename chain does not run and download behaviour is unchanged.

#### Scenario: --auto-rename provided
- **WHEN** `python -m siphon.downloader --url <url> --format mp3 --auto-rename` is passed
- **THEN** the engine SHALL register `_RenamePostProcessor` and run the four-tier rename chain for every file in the session

#### Scenario: --auto-rename omitted
- **WHEN** `python -m siphon.downloader --url <url> --format mp3` is run without `--auto-rename`
- **THEN** no PostProcessor SHALL be registered and all downloaded files SHALL retain their yt-dlp output template names
