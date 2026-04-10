## Context

Siphon uses yt-dlp to download YouTube playlists and videos. For audio downloads, `build_audio_postprocessors()` in `formats.py` returns a single-element list containing only `FFmpegExtractAudio`. The yt-dlp opts dict has no `writethumbnail` key. As a result, all embedding postprocessors are never reached, and downloaded audio files have no ID3 tags and no cover art.

The fix is entirely local to `formats.py`. No other file needs to change.

## Goals / Non-Goals

**Goals:**
- Embed title, artist, track, uploader, and other available YouTube metadata into mp3 and opus audio files.
- Embed the video thumbnail as cover art in mp3 (ID3 `APIC`) and opus (`METADATA_BLOCK_PICTURE`).
- Ensure no stray thumbnail files are left on disk.

**Non-Goals:**
- Metadata embedding for video downloads (mp4/mkv/webm). Out of scope.
- Custom metadata editing or overriding (e.g. letting the user supply their own cover art).
- Integration with the auto-renamer's MusicBrainz lookups for tag enrichment. That is a separate concern.

## Decisions

### 1. Postprocessor order: FFmpegExtractAudio → FFmpegMetadata → EmbedThumbnail

yt-dlp runs postprocessors in list order. The correct sequence is:

```
1. FFmpegExtractAudio   — transcode/remux source to mp3 or opus
2. FFmpegMetadata       — write YouTube metadata fields as ID3/Vorbis tags
3. EmbedThumbnail       — embed the thumbnail as cover art
```

`FFmpegMetadata` must run after `FFmpegExtractAudio` because there is a file to tag only once transcoding is done. `EmbedThumbnail` must run last because it re-encodes the container to insert the APIC frame — doing this before FFmpegMetadata would risk overwriting tags.

### 2. `writethumbnail: True` is added to yt-dlp opts for audio mode only

`EmbedThumbnail` is a no-op if no thumbnail file is on disk. yt-dlp downloads thumbnails only when `writethumbnail: True`. This flag is added inside `_build_ydl_opts()` conditionally on `options.mode == "audio"`, keeping video downloads unaffected.

**Alternative considered:** passing `writethumbnail` unconditionally. Rejected — video containers (mp4/mkv) don't benefit from the same simple pipeline and this change explicitly scopes to audio.

### 3. Thumbnail cleanup is delegated to yt-dlp

`EmbedThumbnailPP` calls `_delete_downloaded_files()` on the thumbnail path before returning when `already_have_thumbnail=False` (the default). This is confirmed in the yt-dlp source and verified by a live test (only the `.mp3` was present after download). No custom cleanup code is needed.

### 4. Same postprocessors for both mp3 and opus

Both formats support embedded cover art. yt-dlp's `EmbedThumbnailPP` branches on `info['ext']` internally and handles the correct embedding method per format. No conditional logic is required in Siphon.

## Risks / Trade-offs

- **ffmpeg must support the image codec** — yt-dlp converts WebP thumbnails to PNG before embedding when needed (via `FFmpegThumbnailsConvertorPP`). This is handled internally by yt-dlp; no risk if ffmpeg is present (already a hard requirement for mp3).

- **Extra network round-trip for thumbnail** — downloading the thumbnail adds a small request per video. This is negligible and consistent with what every other tool (meTube, spotdl, yt-dlp CLI defaults) does.

- **Metadata quality is YouTube-dependent** — fields like `artist` and `track` are only populated for videos in the YouTube Music catalog. For regular videos, yt-dlp falls back to `title` and `uploader`. This is expected and correct behavior; no mitigation needed.

## Migration Plan

No migration is needed. The change affects only newly downloaded files. Existing files on disk are not modified. The change is entirely backward-compatible.
