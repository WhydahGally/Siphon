## ADDED Requirements

### Requirement: Video format with quality selection
When downloading in video mode, the engine SHALL accept a `quality` option (video height) from a defined set and pass the appropriate yt-dlp format selector.

#### Scenario: Valid quality requested
- **WHEN** `options.mode` is `video` and `options.quality` is one of `best`, `2160`, `1080`, `720`, `480`, `360`
- **THEN** the engine SHALL use a yt-dlp format string that targets that height (e.g., `bestvideo[height<=1080]+bestaudio/best[height<=1080]`)

#### Scenario: Quality is `best`
- **WHEN** `options.quality` is `best`
- **THEN** the engine SHALL use `bestvideo+bestaudio/best` as the yt-dlp format selector

---

### Requirement: Video container format selection
When downloading in video mode, the engine SHALL accept a `video_format` option that controls the output container. Supported values are `mp4`, `mkv`, and `webm`. The default SHALL be `mp4`.

#### Scenario: mp4 container requested
- **WHEN** `options.video_format` is `mp4`
- **THEN** the engine SHALL pass `merge_output_format="mp4"` to yt-dlp, remuxing merged streams into an MP4 container

#### Scenario: mkv container requested
- **WHEN** `options.video_format` is `mkv`
- **THEN** the engine SHALL pass `merge_output_format="mkv"` to yt-dlp

#### Scenario: webm container requested
- **WHEN** `options.video_format` is `webm`
- **THEN** the engine SHALL pass `merge_output_format="webm"` to yt-dlp

#### Scenario: No video_format specified
- **WHEN** `options.video_format` is not set
- **THEN** the engine SHALL default to `mp4`

---

### Requirement: Audio format — opus mode
When `options.mode` is `audio` and `options.format` is `opus`, the engine SHALL remux the source Opus/WebM stream without transcoding.

#### Scenario: Opus audio download
- **WHEN** `options.mode` is `audio` and `options.format` is `opus`
- **THEN** the engine SHALL configure yt-dlp to extract audio in `opus` format with no post-processing transcode

---

### Requirement: Audio format — mp3 mode with bitrate capping
When `options.mode` is `audio` and `options.format` is `mp3`, the engine SHALL transcode to MP3. The output bitrate SHALL be capped at the source audio bitrate, with a maximum of 320kbps. No upsampling SHALL occur.

#### Scenario: MP3 audio download
- **WHEN** `options.mode` is `audio` and `options.format` is `mp3`
- **THEN** the engine SHALL configure yt-dlp with `--extract-audio --audio-format mp3 --audio-quality 0` (which uses VBR targeting best quality without upsampling)

---

### Requirement: Invalid option rejection
The engine SHALL validate the options object at call time and raise a clear error for any unsupported `quality`, `video_format`, or `audio_format` value.

#### Scenario: Unsupported quality passed
- **WHEN** `options.quality` is a value not in the supported set
- **THEN** the engine SHALL raise a `ValueError` with a descriptive message before any download starts

#### Scenario: Unsupported video_format passed
- **WHEN** `options.video_format` is not `mp4`, `mkv`, or `webm`
- **THEN** the engine SHALL raise a `ValueError` with a descriptive message before any download starts

#### Scenario: Unsupported audio format passed
- **WHEN** `options.audio_format` is not `mp3` or `opus`
- **THEN** the engine SHALL raise a `ValueError` with a descriptive message before any download starts
