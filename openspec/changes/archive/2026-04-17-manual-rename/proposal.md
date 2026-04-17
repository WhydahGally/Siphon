## Why

Users sometimes want to override the auto-renamer's output — a MusicBrainz mismatch, a preferred spelling, or simply a personal naming preference. Today, `renamed_to` is immutable after download: the only option is to rename the file manually on disk and accept that the DB is now out of sync. A manual rename tier lets users fix names through the same interfaces they already use (CLI and web UI), keeping the DB, filesystem, and display all consistent.

## What Changes

- New CLI command `siphon rename-item <playlist> <current-name> <new-name>` that renames a downloaded item's file on disk and updates the DB with `rename_tier='manual'`.
- New HTTP endpoint `PUT /playlists/{playlist_id}/items/{video_id}/rename` that performs the same operation for UI clients.
- For single-video downloads (no playlist, not in DB): rename is supported in the download queue only — updates daemon in-memory `JobItem` and renames the file on disk. No DB write.
- Inline rename editing in `PlaylistItemsPanel.vue` (Library page) and `QueueItem.vue` (Dashboard download queue, `done` state only). Pencil icon on hover, inline text input with Save button, click-outside-to-cancel — matching the Settings page interval edit pattern.
- For items where auto-rename was off (`renamed_to` is NULL), clicking the pencil inserts the arrow and text input inline, prefilled with `yt_title`.
- File extension is resolved by extracting known extensions (`VALID_AUDIO_FORMATS ∪ VALID_VIDEO_FORMATS`) from the tail of the current filename on disk.

## Capabilities

### New Capabilities

- `manual-rename-api`: HTTP endpoint and registry function for renaming a playlist item (DB + filesystem). Also covers the in-memory rename path for single-video jobs in the JobStore.
- `manual-rename-cli`: CLI command `siphon rename-item <playlist> <current-name> <new-name>` that calls the rename API endpoint.
- `manual-rename-ui`: Inline rename editing UI in PlaylistItemsPanel and QueueItem components — pencil icon, text input, save/cancel behavior.

### Modified Capabilities

- `auto-renamer`: Add `manual` as a recognised `rename_tier` value. No behavioral change to the existing three-tier chain.
- `job-store`: `JobItem` gains a mutable `renamed_to` field that can be updated after download completes (for single-video in-memory rename).

## Impact

- **Backend**: `registry.py` gets a new `update_item_rename()` function. `watcher.py` gets a new PUT endpoint and a new CLI subcommand + parser. `formats.py` constants are reused for extension extraction.
- **Frontend**: `PlaylistItemsPanel.vue` and `QueueItem.vue` gain inline edit mode. No new components needed — the pattern already exists in `Settings.vue`.
- **DB schema**: No schema migration. The `rename_tier` column already accepts free text; `'manual'` is a new value.
- **Filesystem**: `os.rename()` is called on the download directory to rename the actual file.
