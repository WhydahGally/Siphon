## ADDED Requirements

### Requirement: PUT /playlists/{playlist_id}/items/{video_id}/rename endpoint
The daemon SHALL expose `PUT /playlists/{playlist_id}/items/{video_id}/rename` which accepts a JSON body `{ "new_name": "<string>" }`. The endpoint SHALL: validate that the playlist and item exist, sanitize `new_name` using the existing `sanitize()` function from the renamer module, resolve the current file path on disk, rename the file, and update the DB record with `renamed_to=<sanitized_name>` and `rename_tier='manual'`. The response SHALL be 200 with the updated item record. The file extension SHALL be preserved from the original file.

#### Scenario: Successful rename of auto-renamed item
- **WHEN** `PUT /playlists/{pid}/items/{vid}/rename` is called with `{ "new_name": "My Custom Name" }` for an item with `renamed_to='Artist - Track'` and file `Artist - Track.opus` on disk
- **THEN** the file SHALL be renamed to `My Custom Name.opus`, the DB SHALL be updated with `renamed_to='My Custom Name'` and `rename_tier='manual'`, and the response SHALL be 200 with the updated item

#### Scenario: Successful rename of non-renamed item (auto-rename was off)
- **WHEN** `PUT /playlists/{pid}/items/{vid}/rename` is called for an item with `renamed_to=NULL` and file `Some YouTube Title.mp3` on disk
- **THEN** the file SHALL be renamed to `<sanitized_new_name>.mp3`, the DB SHALL be updated with `renamed_to=<sanitized_new_name>` and `rename_tier='manual'`, and the response SHALL be 200

#### Scenario: Item not found
- **WHEN** `PUT /playlists/{pid}/items/{vid}/rename` is called for a `video_id` not in the given playlist
- **THEN** the response SHALL be 404 with a descriptive error

#### Scenario: Playlist not found
- **WHEN** `PUT /playlists/{pid}/items/{vid}/rename` is called for a `playlist_id` not in the registry
- **THEN** the response SHALL be 404 with a descriptive error

#### Scenario: File not found on disk
- **WHEN** the item exists in the DB but the corresponding file cannot be found in the download directory
- **THEN** the response SHALL be 404 with an error indicating the file was not found on disk. The DB SHALL NOT be updated.

#### Scenario: Name collision on disk
- **WHEN** a file with the target name `<new_name>.<ext>` already exists in the download directory
- **THEN** the response SHALL be 409 with an error indicating a file with that name already exists. Neither the file nor the DB SHALL be modified.

#### Scenario: new_name is empty or whitespace-only
- **WHEN** `PUT /playlists/{pid}/items/{vid}/rename` is called with `{ "new_name": "  " }` or `{ "new_name": "" }`
- **THEN** the response SHALL be 422 with a validation error

---

### Requirement: PUT /jobs/{job_id}/items/{video_id}/rename endpoint for single-video downloads
The daemon SHALL expose `PUT /jobs/{job_id}/items/{video_id}/rename` which accepts a JSON body `{ "new_name": "<string>" }`. This endpoint handles single-video downloads that are not tracked in the DB. The endpoint SHALL: validate that the job and item exist in the JobStore and that the item is in `done` state, sanitize `new_name`, resolve the current file path on disk, rename the file, and update `JobItem.renamed_to` and `JobItem.rename_tier` in memory. No DB write SHALL occur. The response SHALL be 200 with the updated item.

#### Scenario: Successful rename of single-video item
- **WHEN** `PUT /jobs/{jid}/items/{vid}/rename` is called for a single-video job item in `done` state
- **THEN** the file SHALL be renamed on disk, `JobItem.renamed_to` and `JobItem.rename_tier='manual'` SHALL be updated in the JobStore, and the response SHALL be 200

#### Scenario: Item not in done state
- **WHEN** `PUT /jobs/{jid}/items/{vid}/rename` is called for an item in `downloading` or `pending` state
- **THEN** the response SHALL be 409 with an error indicating the item must be in done state

#### Scenario: Job not found
- **WHEN** `PUT /jobs/{jid}/items/{vid}/rename` is called for a `job_id` not in the JobStore
- **THEN** the response SHALL be 404

---

### Requirement: update_item_rename registry function
The `registry` module SHALL expose `update_item_rename(video_id: str, playlist_id: str, new_name: str) -> None` that updates the `renamed_to` and `rename_tier` columns for the given item. `rename_tier` SHALL be set to `'manual'`.

#### Scenario: Item updated successfully
- **WHEN** `update_item_rename(video_id, playlist_id, 'New Name')` is called for an existing item
- **THEN** the item's `renamed_to` SHALL be `'New Name'` and `rename_tier` SHALL be `'manual'`

#### Scenario: Item does not exist
- **WHEN** `update_item_rename(video_id, playlist_id, 'New Name')` is called for a non-existent item
- **THEN** the function SHALL raise a `ValueError`

---

### Requirement: File extension extraction from known formats
The rename operation SHALL determine the file extension by matching the tail of the current filename against the known set of supported extensions (`VALID_AUDIO_FORMATS ∪ VALID_VIDEO_FORMATS` from `formats.py`). If no known extension matches, `os.path.splitext()` SHALL be used as a fallback.

#### Scenario: Known audio extension
- **WHEN** the current file is `Artist - Track.opus`
- **THEN** the extracted extension SHALL be `.opus`

#### Scenario: Known video extension
- **WHEN** the current file is `My Video.mkv`
- **THEN** the extracted extension SHALL be `.mkv`

#### Scenario: Unknown extension fallback
- **WHEN** the current file is `Something.flac`
- **THEN** `os.path.splitext()` SHALL be used, extracting `.flac`

---

### Requirement: Resolve current file path for rename
The rename operation SHALL resolve the current file on disk by: determining the filename stem as `renamed_to` if set, otherwise `yt_title`; scanning the playlist's download directory for a file matching `<stem>.<known_ext>`; and returning the full path. For single-video downloads, the output directory is the root downloads folder (no playlist subfolder).

#### Scenario: Auto-renamed file found
- **WHEN** an item has `renamed_to='Artist - Track'` and `downloads/MyPlaylist/Artist - Track.opus` exists
- **THEN** the resolved path SHALL be `downloads/MyPlaylist/Artist - Track.opus`

#### Scenario: Non-renamed file found
- **WHEN** an item has `renamed_to=NULL`, `yt_title='Cool Song'`, and `downloads/MyPlaylist/Cool Song.mp3` exists
- **THEN** the resolved path SHALL be `downloads/MyPlaylist/Cool Song.mp3`

#### Scenario: Single-video file found
- **WHEN** a single-video job item has `yt_title='My Video'` and `downloads/My Video.mp4` exists
- **THEN** the resolved path SHALL be `downloads/My Video.mp4`
