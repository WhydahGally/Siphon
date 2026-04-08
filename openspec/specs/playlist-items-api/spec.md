## ADDED Requirements

### Requirement: GET /playlists/{playlist_id}/items endpoint
The daemon SHALL expose `GET /playlists/{playlist_id}/items` which returns a JSON array of all downloaded items for the given playlist, ordered by `downloaded_at` ascending. Each item SHALL include: `video_id`, `yt_title`, `renamed_to` (nullable), `rename_tier` (nullable), `uploader` (nullable), `duration_secs` (nullable), `downloaded_at`.

#### Scenario: Playlist exists with items
- **WHEN** `GET /playlists/{playlist_id}/items` is called for a playlist with downloaded items
- **THEN** the response SHALL be a JSON array of item objects ordered by `downloaded_at` ascending

#### Scenario: Playlist exists with no items
- **WHEN** `GET /playlists/{playlist_id}/items` is called for a playlist with no downloaded items
- **THEN** the response SHALL be an empty JSON array `[]`

#### Scenario: Playlist does not exist
- **WHEN** `GET /playlists/{playlist_id}/items` is called for a `playlist_id` not in the registry
- **THEN** the response SHALL be HTTP 404 with a detail message

---

### Requirement: list_items_for_playlist registry function
The `registry` module SHALL expose `list_items_for_playlist(playlist_id: str) -> list` that returns all item rows for the given playlist from the `items` table, ordered by `downloaded_at` ascending.

#### Scenario: Items returned in order
- **WHEN** `list_items_for_playlist(playlist_id)` is called for a playlist with items
- **THEN** the result SHALL be a list of dicts ordered by `downloaded_at` ascending

#### Scenario: No items returns empty list
- **WHEN** `list_items_for_playlist(playlist_id)` is called for a playlist with no items
- **THEN** the result SHALL be an empty list
