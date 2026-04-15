## Why

Siphon needs a core download engine that can fetch YouTube playlists and single videos in a chosen format and quality, serving as the foundational layer all future interfaces (CLI, web UI) will build on top of.

## What Changes

- Introduce a Python-based download core using the yt-dlp API (not subprocess)
- Support downloading full playlists and single videos
- Support two output modes: video (with resolution selection) and audio (mp3 or opus)
- MP3 mode caps bitrate at source quality up to 320kbps — no upsampling
- Opus mode remuxes the source Opus/WebM stream without transcoding
- Playlist output structure: `<root>/<playlist name>/<video title>`
- Single video output structure: `<root>/<video title>`
- Warn and continue on unavailable videos or missing requested resolution (falls back to best available)
- Progress is emitted via callback, not printed directly — callers decide how to render it
- File sanitization delegates to yt-dlp's built-in handling; renaming logic is stubbed as a separate hookable function for future use
- Proper debug logging and graceful error handling throughout
- A runnable script entry point for manual testing via CLI arguments

## Capabilities

### New Capabilities

- `download-engine`: Core download orchestration — accepts a URL (playlist or single video), format/quality options, output directory, and a progress callback; fetches metadata, builds output paths, and drives yt-dlp to download each item
- `format-options`: Defines the supported format/quality surface: video resolutions (best, 4K, 1080p, 720p, 480p, 360p), audio formats (mp3, opus) with bitrate capping logic
- `progress-events`: Defines the progress event shape emitted during downloads, decoupling the download engine from any specific UI rendering

### Modified Capabilities

## Impact

- New dependencies: `yt-dlp` (Python package), `ffmpeg` (system binary, required for MP3 transcoding)
- No existing code modified — this is a greenfield project
- All future interfaces (CLI runner, future web API) depend on `download-engine`
