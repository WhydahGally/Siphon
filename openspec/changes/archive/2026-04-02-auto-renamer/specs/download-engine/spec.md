## MODIFIED Requirements

### Requirement: Consistent per-item lifecycle
Every downloaded item (whether from a playlist or a single-video call) SHALL pass through the same per-item processing steps: resolve output path → download via yt-dlp → run all postprocessors → invoke renamer hook with full metadata.

#### Scenario: Item from playlist goes through lifecycle
- **WHEN** an item is downloaded as part of a playlist
- **THEN** the renamer hook SHALL be called with the full yt-dlp `info_dict` after all postprocessors (including ffmpeg) have completed

#### Scenario: Single video goes through lifecycle
- **WHEN** a single video is downloaded
- **THEN** the renamer hook SHALL be called with the full yt-dlp `info_dict` after all postprocessors have completed

---

## ADDED Requirements

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
