## Why

Siphon is built on yt-dlp, which supports 1000+ sites beyond YouTube. There is no technical reason to limit users to YouTube — the core engine is already platform-agnostic. This change removes the arbitrary YouTube-only framing and makes Siphon's multi-platform capability explicit and reliable.

## What Changes

- Replace URL-heuristic playlist detection (`"list=" in url`) with a yt-dlp `_type` pre-flight check — works correctly for any platform
- **BREAKING**: Rename `yt_title` column to `title` in `items` and `failed_downloads` tables (DB will be dropped and recreated)
- **BREAKING**: Rename internal rename tier values: `yt_metadata` → `metadata`, `yt_title` → `title`
- Add `platform` column to `playlists` table, populated from sanitized `extractor_key` at add time (e.g. `Youtube`, `Soundcloud`, `Bandcamp`)
- Expose `platform` on playlist API responses and library UI meta area
- Introduce a lightweight extractor-key sanitizer to strip yt-dlp suffixes (`Tab`, `Playlist`, `Channel`, `Album`, etc.)
- Add a rename-tier display label map in the UI (`metadata` → "Metadata", `title` → "Title", `musicbrainz` → "MusicBrainz", `manual` → "Manual")
- Remove all YouTube-specific strings from log messages, error messages, docstrings, and comments
- Rename `_normalise_youtube_url` → `_normalise_url` in `api.py`
- Rename `yt_title` field in Python models (`ItemRecord`, `JobItem`) to `title`

## Capabilities

### New Capabilities

- `platform-field`: Store and display the source platform (e.g. `Youtube`, `Soundcloud`) per playlist, derived from yt-dlp's extractor key at registration time
- `playlist-type-detection`: Platform-agnostic playlist vs. single-video detection via yt-dlp `_type` field instead of URL pattern matching

### Modified Capabilities

- `download-engine`: Playlist detection logic changes from URL heuristic to yt-dlp info-dict inspection
- `audio-metadata-embedding`: Tier 1 rename is no longer "YouTube metadata" — it is generic embedded metadata (`artist` + `track` fields from any platform)

## Impact

- **`src/siphon/downloader.py`**: `download()` — replace `is_playlist` heuristic with `extract_info` pre-flight; update `renamer.py` tier constants
- **`src/siphon/renamer.py`**: Rename tier string constants (`yt_metadata` → `metadata`, `yt_title` → `title`); update comments
- **`src/siphon/models.py`**: Rename `yt_title` field to `title` on `ItemRecord`, `JobItem`, `FailureRecord`
- **`src/siphon/registry.py`**: Drop and recreate schema with `title` column and new `platform` column; update all queries
- **`src/siphon/api.py`**: Rename `_normalise_youtube_url`; update all JSON response keys (`yt_title` → `title`); update error messages; populate `platform` from info dict at playlist registration
- **`src/ui/src/components/PlaylistItemsPanel.vue`**, **`QueueItem.vue`**: Update field references (`yt_title` → `title`); add tier label display map; show `platform` in library meta area
- **Database**: Destructive migration — DB will be dropped and recreated from scratch
