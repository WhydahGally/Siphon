## Why

Audio files downloaded by Siphon contain no embedded metadata — no title, artist, track, or album art. This is because the download pipeline only runs FFmpegExtractAudio; the postprocessors responsible for writing tags and embedding thumbnails are never registered. Tools like meTube produce complete files because they additionally run FFmpegMetadata and EmbedThumbnail.

## What Changes

- Add `FFmpegMetadata` postprocessor to the audio download pipeline for both mp3 and opus outputs, writing all available YouTube metadata (title, artist, track, uploader, etc.) as embedded tags.
- Add `EmbedThumbnail` postprocessor to the audio download pipeline for both mp3 and opus, embedding the video thumbnail as cover art (ID3 `APIC` frame for mp3, Vorbis `METADATA_BLOCK_PICTURE` for opus).
- Set `writethumbnail: True` in the yt-dlp opts so the thumbnail is fetched alongside the audio stream. yt-dlp automatically deletes the thumbnail file after `EmbedThumbnail` runs — no custom cleanup needed.

## Capabilities

### New Capabilities

- `audio-metadata-embedding`: Embed title, artist, track, uploader and thumbnail cover art into downloaded audio files (mp3 and opus) using yt-dlp's FFmpegMetadata and EmbedThumbnail postprocessors.

### Modified Capabilities

<!-- None — this is a new behaviour not previously specified. -->

## Impact

- `src/siphon/formats.py` — `build_audio_postprocessors()` returns an extended postprocessors list; `_build_ydl_opts()` gains `writethumbnail: True` for audio mode.
- No changes to video download path, renamer, watcher, or CLI.
- No new Python dependencies. ffmpeg is already a stated requirement for mp3 transcoding; it also handles thumbnail embedding.
