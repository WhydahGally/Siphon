## ADDED Requirements

### Requirement: cookies_enabled per-playlist column
The `playlists` table SHALL have a `cookies_enabled INTEGER` column (NULL = follow global, 0 = force-off, 1 = force-on). It SHALL be added as an additive migration in `init_db()` using the same `ALTER TABLE … ADD COLUMN` pattern as `sponsorblock_categories`. The column SHALL default to `NULL` for all existing rows.

#### Scenario: Migration runs on existing database
- **WHEN** `init_db()` is called on a database that does not have `cookies_enabled`
- **THEN** the column SHALL be added silently and all existing playlist rows SHALL have `cookies_enabled = NULL`

#### Scenario: New playlist stores cookies_enabled
- **WHEN** `registry.add_playlist(...)` is called with a `cookies_enabled` value
- **THEN** that value SHALL be stored in the new column

---

### Requirement: set_playlist_cookies_enabled() function
The registry SHALL expose `set_playlist_cookies_enabled(playlist_id: str, enabled: Optional[bool]) -> None`. Passing `True` SHALL write `1`, `False` SHALL write `0`, and `None` SHALL write `NULL` (reverting to global default).

#### Scenario: Force-disable cookies for playlist
- **WHEN** `set_playlist_cookies_enabled(playlist_id, False)` is called
- **THEN** `playlists.cookies_enabled` SHALL be `0` for that playlist

#### Scenario: Revert to global default
- **WHEN** `set_playlist_cookies_enabled(playlist_id, None)` is called
- **THEN** `playlists.cookies_enabled` SHALL be `NULL` for that playlist

---

### Requirement: Playlist dict serialisation includes cookies_enabled
The playlist dicts returned by `list_playlists()` and `get_playlist_by_id()` SHALL include the `cookies_enabled` field as returned from the DB (NULL, 0, or 1). The API layer SHALL pass this field through in list and detail responses.

#### Scenario: Playlist list response includes cookies_enabled
- **WHEN** `GET /playlists` is called
- **THEN** each playlist object SHALL include `"cookies_enabled": null | 0 | 1`

---

### Requirement: PlaylistPatch model includes cookies_enabled
The `PlaylistPatch` Pydantic model SHALL include `cookies_enabled: Optional[bool] = None`. The `PATCH /playlists/{id}` handler SHALL call `registry.set_playlist_cookies_enabled()` when this field is present in the request body.

#### Scenario: PATCH enables cookies for playlist
- **WHEN** `PATCH /playlists/{id}` is called with `{"cookies_enabled": true}`
- **THEN** `playlists.cookies_enabled` SHALL be set to `1` for that playlist
