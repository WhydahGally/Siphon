## ADDED Requirements

### Requirement: list_items_for_playlist function
The `registry` module SHALL expose `list_items_for_playlist(playlist_id: str) -> list` that returns all rows from the `items` table for the given `playlist_id`, ordered by `downloaded_at` ascending. Each row SHALL be returned as a plain dict containing: `video_id`, `playlist_id`, `yt_title`, `renamed_to`, `rename_tier`, `uploader`, `channel_url`, `duration_secs`, `downloaded_at`.

#### Scenario: Items returned in order
- **WHEN** `list_items_for_playlist(playlist_id)` is called for a playlist that has downloaded items
- **THEN** the result SHALL be a list of dicts ordered by `downloaded_at` ascending

#### Scenario: No items returns empty list
- **WHEN** `list_items_for_playlist(playlist_id)` is called for a playlist with no items in the `items` table
- **THEN** the result SHALL be an empty list `[]`

## MODIFIED Requirements

### Requirement: Playlist CRUD
The registry SHALL support registering, retrieving, listing, and deleting playlists. Playlist list responses consumed by the API layer SHALL include an `item_count` field (count of rows in `items` for that playlist) and an `is_syncing` field (a boolean derived from the daemon's in-memory `_syncing_playlists` set, not stored in the DB).

#### Scenario: Register a new playlist
- **WHEN** `registry.add_playlist(id, name, url, fmt, output_dir)` is called and no playlist with that `id` exists
- **THEN** a row SHALL be inserted into `playlists` with `added_at` set to the current UTC ISO 8601 timestamp, `last_synced_at` set to NULL, and `format` and `output_dir` stored for use by future syncs

#### Scenario: Register a duplicate playlist
- **WHEN** `registry.add_playlist(id, name, url, fmt, output_dir)` is called and a playlist with that `id` already exists
- **THEN** the registry SHALL raise a `ValueError` indicating the playlist is already registered

#### Scenario: List all playlists
- **WHEN** `registry.list_playlists()` is called
- **THEN** the registry SHALL return all rows from `playlists` ordered by `added_at` ascending

#### Scenario: Update last synced time
- **WHEN** `registry.update_last_synced(playlist_id)` is called
- **THEN** `playlists.last_synced_at` SHALL be set to the current UTC ISO 8601 timestamp for that playlist

#### Scenario: Find playlist by name
- **WHEN** `registry.get_playlist_by_name(name)` is called
- **THEN** the registry SHALL return the matching playlist row, or `None` if no match exists

#### Scenario: Delete a playlist
- **WHEN** `registry.delete_playlist(playlist_id)` is called
- **THEN** all rows in `items` with that `playlist_id` SHALL be deleted, then the row in `playlists` SHALL be deleted, within a single transaction

#### Scenario: API playlist response includes is_syncing
- **WHEN** `GET /playlists` or `GET /playlists/{id}` is called
- **THEN** each playlist object in the response SHALL include `"is_syncing": true` if the playlist is currently being synced, and `"is_syncing": false` otherwise
