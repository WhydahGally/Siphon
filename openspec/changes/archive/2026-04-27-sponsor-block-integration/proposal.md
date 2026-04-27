## Why

YouTube music videos frequently contain non-music segments — talking-head intros, sponsor reads, end cards — that are jarring when listening through a music library. SponsorBlock is a community-sourced database of these segments. yt-dlp has native SponsorBlock support via `--sponsorblock-remove`, which lets ffmpeg cut the segments at download time. Adding this to Siphon gives music library users clean, segment-free files with no manual editing.

## What Changes

- `DownloadOptions` gains a `sponsorblock_categories` field (`list[str] | None`); `download()` adds `SponsorBlockPP` and `ModifyChaptersPP` post-processors via `ydl.add_post_processor()` when the field is non-empty.
- The `playlists` table gains a `sponsorblock_categories` column (`TEXT`, nullable). `NULL` = use global default at sync time; `""` (empty string) = explicitly disabled per-playlist.
- Two new global settings keys: `sb-enabled` (`true`/`false`, default `true`) and `sb-cats` (JSON array, default `["music_offtopic"]`).
- `PlaylistCreate` and `PlaylistPatch` models gain `sponsorblock_enabled` and `sponsorblock_categories` fields.
- CLI: `siphon config sb-enabled` / `siphon config sb-cats` for global settings; `siphon config-playlist <name> sponsorblock` / `siphon config-playlist <name> sb-cats` for per-playlist overrides; `--sponsorblock` opt-in flag on `siphon add`.
- UI: **Settings.vue** — new "SponsorBlock" section with enable toggle and collapsible chip-based category picker. **DownloadForm.vue** — "SponsorBlock" toggle seeded from global, positioned between Auto rename and Sync. **PlaylistRow.vue** — "SponsorBlock" toggle between Auto rename and Sync, immediate PATCH on click.
- README: SponsorBlock listed as a feature with a link to the project; `siphon config` and `siphon config-playlist` key tables updated.

## Capabilities

### New Capabilities

- `sponsorblock`: SponsorBlock segment removal — yt-dlp option wiring, per-playlist and global settings storage, and resolution at download time.

### Modified Capabilities

- `download-engine`: `DownloadOptions` gains `sponsorblock_categories`; `download()` updated to add SponsorBlock post-processors via `ydl.add_post_processor()`.
- `global-config-keys`: Two new global settings keys (`sb-enabled`, `sb-cats`).
- `settings-ui`: New "SponsorBlock" section added to Settings page.
- `web-ui`: DownloadForm and PlaylistRow gain a "Sponsor Block" toggle.

## Impact

- **`src/siphon/formats.py`** — `DownloadOptions` dataclass modified.
- **`src/siphon/downloader.py`** — `download()` modified to add SponsorBlock post-processors; `run_download_job()` and `sync_parallel()` accept and forward `sponsorblock_categories`.
- **`src/siphon/models.py`** — `PlaylistCreate`, `PlaylistPatch` models modified.
- **`src/siphon/registry.py`** — DB schema (`playlists` table), `upsert_playlist`, `patch_playlist`, `get_playlist`, settings read helpers modified.
- **`src/siphon/api.py`** — job creation and playlist PATCH endpoints modified.
- **`src/siphon/scheduler.py`** — scheduled sync reads sponsorblock settings to pass to downloader.
- **`src/siphon/cli.py`** — `_KNOWN_KEYS`, `_PLAYLIST_KNOWN_KEYS`, `cmd_config`, `cmd_config_playlist` modified.
- **`src/ui/src/components/Settings.vue`** — new section added.
- **`src/ui/src/components/DownloadForm.vue`** — new toggle added.
- **`src/ui/src/components/PlaylistRow.vue`** — new toggle added.
- **`README.md`** — features list and CLI tables updated.
- **Dependencies**: no new Python or JS packages required (yt-dlp and ffmpeg already present).
