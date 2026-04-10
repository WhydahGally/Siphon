## 1. Core Implementation

- [x] 1.1 In `build_audio_postprocessors()` (formats.py), append `{"key": "FFmpegMetadata", "add_metadata": True}` after FFmpegExtractAudio for both mp3 and opus
- [x] 1.2 In `build_audio_postprocessors()`, append `{"key": "EmbedThumbnail"}` as the final postprocessor for both mp3 and opus
- [x] 1.3 In `_build_ydl_opts()` (formats.py), add `"writethumbnail": True` to the ydl_opts dict when `options.mode == "audio"`

## 2. Verification

- [x] 2.1 Download a single YouTube video as mp3 and confirm the output file has title, artist/uploader tags and an embedded cover image (inspect with `ffprobe` or a tag editor)
- [x] 2.2 Download a single YouTube video as opus and confirm the same for the opus container
- [x] 2.3 Confirm no `.webp`, `.jpg`, or `.png` files remain in the output directory after either download
- [x] 2.4 Download a playlist in audio mode and confirm all files carry metadata and cover art
- [x] 2.5 Run an existing video-mode download and confirm its output is unchanged
