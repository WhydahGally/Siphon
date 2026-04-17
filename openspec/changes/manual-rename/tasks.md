## 1. Backend — Registry and Helpers

- [x] 1.1 Add `update_item_rename(video_id, playlist_id, new_name)` to `registry.py` — UPDATE `renamed_to` and `rename_tier='manual'` for the given item PK
- [x] 1.2 Add `get_item(video_id, playlist_id)` to `registry.py` — fetch a single item row (needed to resolve current filename)
- [x] 1.3 Add file extension extraction helper using `VALID_AUDIO_FORMATS ∪ VALID_VIDEO_FORMATS` from `formats.py`, with `os.path.splitext()` fallback
- [x] 1.4 Add file path resolution helper — given item record and playlist download dir, find the current file on disk by stem + known extension scan

## 2. Backend — API Endpoints

- [x] 2.1 Add `PUT /playlists/{playlist_id}/items/{video_id}/rename` endpoint in `watcher.py` — validate input, resolve file, rename on disk, update DB, return updated item
- [x] 2.2 Add `PUT /jobs/{job_id}/items/{video_id}/rename` endpoint in `watcher.py` — validate job/item in JobStore, rename on disk, update `JobItem.renamed_to` and `rename_tier` in memory, return updated item
- [x] 2.3 Add `rename_tier` field to `JobItem` dataclass (already present)

## 3. CLI — rename-item Command

- [x] 3.1 Add `rename-item` subparser to the CLI argument parser with positional args `playlist`, `current-name`, `new-name`
- [x] 3.2 Implement `cmd_rename_item` — resolve playlist by name, find item by current name match, call PUT endpoint, print result
- [x] 3.3 Document the command in `README.md`

## 4. UI — Inline Rename in PlaylistItemsPanel

- [x] 4.1 Add edit state tracking (per-item `editingVideoId` ref) and pencil icon on hover over the renamed portion of each item row
- [x] 4.2 Implement inline text input with Save button — prefill with `renamed_to` or `yt_title`, show arrow for non-renamed items entering edit mode
- [x] 4.3 Implement save handler — call `PUT /playlists/{playlist_id}/items/{video_id}/rename`, update local item cache on success, exit edit mode
- [x] 4.4 Implement cancel behavior — click-outside and Escape key dismiss edit mode without saving

## 5. UI — Inline Rename in QueueItem

- [x] 5.1 Add pencil icon on hover for items in `done` state only
- [x] 5.2 Implement inline text input with same UX as PlaylistItemsPanel
- [x] 5.3 Implement save handler — route to playlist rename endpoint if `playlist_id` is set, otherwise to job rename endpoint
- [x] 5.4 Implement cancel behavior (click-outside, Escape)

## 6. Backend — Always-rename and visual-equivalent character map

- [x] 6.1 Add `_VISUAL_EQUIVALENT_MAP` dict to `renamer.py` — maps each unsafe ASCII char (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) to its Unicode visual lookalike
- [x] 6.2 Add `safe_replace(name: str) -> str` function to `renamer.py` — applies the visual-equivalent map to a string, replacing each unsafe char with its safe counterpart
- [x] 6.3 Add `passthrough_rename(info_dict: dict) -> Optional[RenameResult]` function to `renamer.py` — applies `safe_replace` to the raw YT title (no noise stripping, no MB, no metadata), renames the file on disk, returns `RenameResult` with `tier="yt_title_passthrough"`
- [x] 6.4 Update tier 3 in `rename_file()` — when a known separator is found in the title, split into artist/track and format as `Artist - Track` instead of using `sanitize()`
- [x] 6.5 Update tier 3 in `rename_file()` — when NO separator is found, use `safe_replace()` instead of `sanitize()` to preserve title appearance

## 7. Integration — Always register rename post-processor

- [x] 7.1 Update `downloader.py` — always register `_RenamePostProcessor`, passing a new flag to indicate whether full auto-rename or passthrough mode should be used
- [x] 7.2 Update `_RenamePostProcessor.run()` — call `passthrough_rename()` when auto-rename is OFF, call `rename_file()` when auto-rename is ON
- [x] 7.3 Update `_download_worker` in `watcher.py` — `renamed_to` and `rename_tier` are now always populated (no more `None` for auto-rename OFF)

## 8. Embed original YT title in file metadata

- [x] 8.1 Add `embed_original_title(filepath, original_title)` to `renamer.py` — write the original YT title into the file's metadata using mutagen (ID3 `TXXX:original_title` for MP3, `ORIGINAL_TITLE` Vorbis comment for Opus)
- [x] 8.2 Call `embed_original_title` from `_RenamePostProcessor.run()` after rename completes — pass the final filepath and the original YT title
