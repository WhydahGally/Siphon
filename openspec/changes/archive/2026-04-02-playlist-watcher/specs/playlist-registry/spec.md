## ADDED Requirements

### Requirement: Persistent playlist registry
The system SHALL maintain a SQLite database at `.data/siphon.db` that stores all registered playlists and their downloaded items. The database SHALL be created automatically on first use if it does not exist. The `.data/` folder SHALL be git-ignored via an entry in the root `.gitignore`.

#### Scenario: First startup — no DB exists
- **WHEN** any `siphon` subcommand is invoked and `.data/siphon.db` does not exist
- **THEN** the registry SHALL create `.data/` (and `.data/archives/`) and initialise the database with all three tables (`playlists`, `items`, `settings`)

#### Scenario: Subsequent startup — DB exists
- **WHEN** any `siphon` subcommand is invoked and `.data/siphon.db` already exists
- **THEN** the registry SHALL open the existing database without altering its schema or data

---

### Requirement: Playlist CRUD
The registry SHALL support registering, retrieving, and listing playlists.

#### Scenario: Register a new playlist
- **WHEN** `registry.add_playlist(id, name, url, fmt, quality, output_dir)` is called and no playlist with that `id` exists
- **THEN** a row SHALL be inserted into `playlists` with `added_at` set to the current UTC ISO 8601 timestamp, `last_synced_at` set to NULL, and `format`, `quality`, and `output_dir` stored for use by future syncs

#### Scenario: Register a duplicate playlist
- **WHEN** `registry.add_playlist(id, name, url, fmt, quality, output_dir)` is called and a playlist with that `id` already exists
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

---

### Requirement: Item persistence
The registry SHALL record each successfully downloaded item with its full metadata.

#### Scenario: Insert a new item
- **WHEN** `registry.insert_item(item_record)` is called with a populated `ItemRecord`
- **THEN** a row SHALL be inserted into `items` with all provided fields. `downloaded_at` SHALL be set to the current UTC ISO 8601 timestamp if not supplied.

#### Scenario: Duplicate item in same playlist
- **WHEN** `registry.insert_item(item_record)` is called and a row with the same `(video_id, playlist_id)` already exists
- **THEN** the insert SHALL be silently ignored (INSERT OR IGNORE semantics)

---

### Requirement: Duplicate video detection
The registry SHALL provide a way to identify videos that appear in more than one registered playlist.

#### Scenario: Query for duplicates
- **WHEN** `registry.find_duplicates()` is called
- **THEN** the registry SHALL return all `video_id` values that appear in more than one distinct `playlist_id`, along with the list of playlist names they appear in

---

### Requirement: Settings storage
The registry SHALL provide a key-value settings table for future use.

#### Scenario: Write a setting
- **WHEN** `registry.set_setting(key, value)` is called
- **THEN** the value SHALL be upserted into the `settings` table for that key

#### Scenario: Read a setting
- **WHEN** `registry.get_setting(key)` is called
- **THEN** the registry SHALL return the stored value string, or `None` if the key does not exist
