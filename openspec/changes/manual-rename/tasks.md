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
