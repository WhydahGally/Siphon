## 1. Project Setup

- [x] 1.1 Create project directory structure: `siphon/` package with `__init__.py`, `downloader.py`, `formats.py`, `renamer.py`
- [x] 1.2 Create `requirements.txt` with `yt-dlp` pinned to a specific version
- [x] 1.3 Verify `ffmpeg` detection works by checking PATH at import/runtime

## 2. Format Options Module

- [x] 2.1 Implement `DownloadOptions` dataclass in `formats.py` with fields: `mode` (video/audio), `quality` (video height: best/2160/1080/720/480/360), `video_format` (container: mp4/mkv/webm), `audio_format` (mp3/opus), and validation on construction
- [x] 2.2 Implement video format selector function: maps `quality` value to yt-dlp format string (e.g., `1080` → `bestvideo[height<=1080]+bestaudio/best[height<=1080]`)
- [x] 2.3 Implement audio format selector function: returns yt-dlp postprocessor config for `opus` (remux) and `mp3` (transcode with `--audio-quality 0`)
- [x] 2.4 Add `ValueError` for invalid quality, video_format, or audio_format values
- [x] 2.5 Implement video container selection: pass `video_format` to yt-dlp `merge_output_format`; add ffmpeg guard for `mp4`/`mkv` remuxing

## 3. Progress Events Module

- [x] 3.1 Define the progress event dict shape (as a typed dict or dataclass) in `progress.py`
- [x] 3.2 Implement `make_progress_event(d)` that maps a raw yt-dlp progress hook dict to the normalised event shape

## 4. Renamer Hook

- [x] 4.1 Create `renamer.py` with a `rename_file(filepath: str) -> str` function that is a no-op passthrough (returns `filepath` unchanged)

## 5. Download Engine

- [x] 5.1 Implement `download(url, output_dir, options, progress_callback=None)` in `downloader.py`
- [x] 5.2 Detect whether the URL is a playlist or single video and set the appropriate yt-dlp output template (`%(playlist_title)s/%(title)s.%(ext)s` vs `%(title)s.%(ext)s`)
- [x] 5.3 Wire `make_progress_event` and the caller's `progress_callback` into yt-dlp's `progress_hooks`
- [x] 5.4 Wrap the callback invocation in try/except — log WARNING and continue on callback errors
- [x] 5.5 Configure yt-dlp `ignoreerrors=True` so unavailable playlist items are skipped; log a WARNING per skipped item
- [x] 5.6 Check for ffmpeg on PATH when `options.format == "mp3"` before starting downloads; raise a clear error if missing
- [x] 5.7 Call `renamer.rename_file()` on each completed item's output path

## 6. Entry Point for Testing

- [x] 6.1 Add `if __name__ == "__main__":` block to `downloader.py` with `argparse` for `url`, `--output-dir`, `--format`, `--quality`
- [x] 6.2 Define a simple stdout progress callback in the `__main__` block that prints `[status] filename — X%`
- [x] 6.3 Wire basic logging setup (`logging.basicConfig(level=logging.DEBUG)`) in the `__main__` block

## 7. Manual Testing

- [x] 7.1 Test playlist download in video mode at a specific resolution (e.g., 1080p) with a short public playlist
- [x] 7.2 Test playlist download in audio mp3 mode; verify bitrate is not upsampled vs source
- [x] 7.3 Test playlist download in audio opus mode; verify no transcode occurs
- [x] 7.4 Test single video download; verify file lands in root output dir (not a subdirectory)
- [x] 7.5 Test with a playlist containing an unavailable video; verify download continues and warning is logged
- [x] 7.6 Test with a requested resolution higher than any available stream; verify fallback and warning
