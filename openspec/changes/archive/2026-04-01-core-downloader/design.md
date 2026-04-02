## Context

Siphon is a greenfield Python project. There is no existing codebase to integrate with. The goal is a download engine that is simple, correct, and easy to build a web UI on top of later. It wraps yt-dlp — a mature, actively maintained download library — so the design is primarily about *what to expose* and *how to structure the boundary* between the engine and its callers.

## Goals / Non-Goals

**Goals:**
- A clean Python module (`downloader.py`) callable by any interface with no UI coupling
- Support playlist and single-video downloads with consistent item lifecycle
- Two output modes: video (selectable resolution) and audio (mp3 or opus)
- Progress events emitted via callback — callers render them, the engine does not
- Graceful handling of unavailable videos, missing resolutions, and network errors
- Debug-level logging throughout using Python's `logging` module
- A `__main__` entry point for direct invocation during development/testing

**Non-Goals:**
- No terminal UI, progress bars, or rich output in the engine itself
- No database or persistent download history (planned separately)
- No configuration file — options passed explicitly by the caller
- No file renaming logic beyond yt-dlp's built-in sanitization
- No playlist/channel discovery — the caller provides the URL

## Decisions

### 1. Use yt-dlp Python API, not subprocess

**Decision:** Call `yt_dlp.YoutubeDL` directly rather than `subprocess.run(["yt-dlp", ...])`.

**Rationale:** The Python API gives structured access to metadata, per-video progress hooks, and error types. subprocess gives only exit codes and stdout/stderr, making it much harder to emit structured progress events or distinguish error types (network vs. unavailable vs. private video).

**Alternative considered:** subprocess — simpler to reason about but loses all structured data.

---

### 2. Progress emitted via callback, not printed

**Decision:** The engine accepts an optional `progress_callback` parameter. It is called with a structured dict on each yt-dlp progress event. The engine itself never calls `print()`.

**Rationale:** This is the architectural seam that allows any future interface (web API, TUI, desktop GUI) to consume progress without modifying the engine. The `__main__` runner provides a simple callback that prints to stdout.

**Alternative considered:** Engine prints directly — simpler now, breaks the interface contract later.

---

### 3. Single function entry point with a shared item lifecycle

**Decision:** One public function: `download(url, output_dir, options, progress_callback=None)`. Internally, both playlist and single-video downloads go through the same per-item download path.

**Rationale:** Keeps the public surface minimal. The shared lifecycle ensures the planned file renamer hook (and any future per-item processing) applies identically to both cases. yt-dlp already handles detecting whether a URL is a playlist or a single video.

**Alternative considered:** Separate `download_playlist` and `download_video` functions — more explicit, but creates two lifecycle paths to maintain.

---

### 4. File renamer as a stubbed hook

**Decision:** A `rename_file(filepath)` function exists in `renamer.py` but is a no-op passthrough by default. The downloader calls it after each item. The stub makes the hook easy to locate and replace.

**Rationale:** yt-dlp handles filename sanitization natively. The stub preserves the future integration point without adding complexity now.

---

### 5. Audio format strategy

**Decision:** Two audio modes:
- `opus` — remux the source Opus/WebM stream directly, no transcode
- `mp3` — transcode to MP3; yt-dlp's `--audio-quality 0` caps the output bitrate at the source bitrate, max 320kbps (no upsampling)

**Rationale:** Opus preserves the highest quality with no transcode loss. MP3 is the compatibility choice. FLAC is excluded — transcoding lossy source to a lossless container is misleading and wasteful.

---

### 6. Resolution fallback

**Decision:** When requested resolution is unavailable, yt-dlp falls back to the next best available resolution. A warning is logged. The download continues.

**Rationale:** Aborting an entire playlist because one video lacks 4K is a poor user experience. Silent fallback is acceptable for a personal tool; a log warning is sufficient visibility.

---

### 7. Output path structure

**Decision:**
- Playlist: `<output_dir>/<playlist_title>/<video_title>.<ext>`
- Single video: `<output_dir>/<video_title>.<ext>`

**Rationale:** Matches user expectation. Single videos go to root to avoid an artificial grouping folder. yt-dlp output templates are used to implement this (`%(playlist_title)s/%(title)s.%(ext)s` vs `%(title)s.%(ext)s`), with yt-dlp's built-in sanitization handling illegal filename characters.

## Risks / Trade-offs

- **yt-dlp API stability** → yt-dlp is a community project; the Python API is not formally versioned. Pin the dependency version. Mitigation: the engine is a thin wrapper, so changes are localised.
- **ffmpeg dependency for MP3** → MP3 transcoding requires ffmpeg to be installed on the system. No ffmpeg = audio-only downloads silently fail or error. Mitigation: check for ffmpeg at startup and emit a clear error if missing when MP3 mode is requested.
- **Progress callback errors** → An exception in the caller's progress callback will propagate into the yt-dlp download loop. Mitigation: wrap the callback invocation in a try/except, log the error, continue.
- **Large playlists** → No concurrency; downloads are sequential. For personal use this is acceptable. Mitigation: noted as a future improvement, no action now.

## Open Questions

- None. All decisions are resolved for this phase.
