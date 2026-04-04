## ADDED Requirements

### Requirement: Persistent playlist registry
The system SHALL maintain a SQLite database at `.data/siphon.db` that stores all registered playlists and their downloaded items. The database SHALL be created automatically on first use if it does not exist. The `.data/` folder SHALL be git-ignored via an entry in the root `.gitignore`. The `.data/archives/` subdirectory SHALL NOT be created; archive file management is removed from the registry.

#### Scenario: First startup — no DB exists
- **WHEN** any `siphon` subcommand is invoked and `.data/siphon.db` does not exist
- **THEN** the registry SHALL create `.data/` and initialise the database with all tables: `playlists`, `items`, `settings`, `failed_downloads`, `ignored_items`
- **THEN** WAL mode SHALL be enabled

#### Scenario: Subsequent startup — DB exists
- **WHEN** any `siphon` subcommand is invoked and `.data/siphon.db` already exists
- **THEN** the registry SHALL open the existing database, apply WAL mode, and run schema migrations for any new tables without altering existing data

---

### Requirement: Playlist CRUD
The registry SHALL support registering, retrieving, and listing playlists.

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

---

### Requirement: WAL mode enabled at init
The registry SHALL enable SQLite WAL mode at `init_db()` time by executing `PRAGMA journal_mode=WAL`. This allows multiple reader connections and serialises writers internally without a Python-level lock.

#### Scenario: WAL mode enabled on first init
- **WHEN** `init_db()` is called on a new database
- **THEN** `PRAGMA journal_mode=WAL` SHALL be executed before any other operations

#### Scenario: WAL mode enabled on existing database
- **WHEN** `init_db()` is called on an existing database that was created without WAL mode
- **THEN** `PRAGMA journal_mode=WAL` SHALL be applied, converting the database to WAL mode

---

### Requirement: Per-thread short-lived connections
All write operations performed from worker threads SHALL open a new `sqlite3.connect()` connection with `PRAGMA busy_timeout = 3000`. The connection SHALL be closed after the write completes.

#### Scenario: Worker thread inserts an item record
- **WHEN** a worker thread calls `registry.insert_item(record, playlist_id)` from a thread other than the main thread
- **THEN** the function SHALL open its own connection, execute the INSERT, and close the connection without error

#### Scenario: Write contention between threads
- **WHEN** two worker threads attempt to write to the DB at the same moment
- **THEN** one SHALL succeed immediately; the other SHALL wait up to 3000ms before retrying internally via SQLite WAL
- **THEN** both writes SHALL ultimately succeed without a Python-level exception (assuming contention resolves within the timeout)

---

### Requirement: failed_downloads table
The registry SHALL maintain a `failed_downloads` table with the following schema:

- `video_id` (TEXT NOT NULL)
- `playlist_id` (TEXT NOT NULL)
- `yt_title` (TEXT NOT NULL)
- `url` (TEXT NOT NULL)
- `error_message` (TEXT)
- `attempt_count` (INTEGER NOT NULL DEFAULT 1)
- `last_attempted_at` (TEXT NOT NULL — UTC ISO 8601)
- PRIMARY KEY: `(video_id, playlist_id)`

#### Scenario: Table created on init
- **WHEN** `init_db()` is called
- **THEN** the `failed_downloads` table SHALL exist with the schema above

---

### Requirement: failed_downloads write helpers
The registry SHALL provide functions to insert, update, query, and delete failure records.

#### Scenario: Insert first failure
- **WHEN** `registry.insert_failed(video_id, playlist_id, yt_title, url, error_message)` is called and no row exists for that primary key
- **THEN** a row SHALL be inserted with `attempt_count = 1` and `last_attempted_at` set to the current UTC timestamp

#### Scenario: Upsert on repeated failure
- **WHEN** `registry.insert_failed(...)` is called and a row already exists for that `(video_id, playlist_id)`
- **THEN** `attempt_count` SHALL be incremented by 1, `error_message` updated, and `last_attempted_at` updated

#### Scenario: Query failures for playlist
- **WHEN** `registry.get_failed(playlist_id)` is called
- **THEN** the registry SHALL return all `failed_downloads` rows for that playlist ordered by `last_attempted_at` ascending

#### Scenario: Delete on successful retry
- **WHEN** `registry.clear_failed(video_id, playlist_id)` is called
- **THEN** the row for that `(video_id, playlist_id)` SHALL be deleted

---

### Requirement: ignored_items table
The registry SHALL maintain an `ignored_items` table. See `openspec/specs/ignored-items/spec.md` for the full schema and behaviour requirements.

#### Scenario: Table created on init
- **WHEN** `init_db()` is called
- **THEN** the `ignored_items` table SHALL exist

## REMOVED Requirements

### Requirement: Archive path management
**Reason**: The yt-dlp `download_archive` mechanism is superseded by the `items` DB table as the sole deduplication source. The registry no longer needs to compute, create, or return archive file paths.
**Migration**: `registry.archive_path(playlist_id)` is removed. Any callers that used it to pass `download_archive` to yt-dlp SHALL be updated to use the DB-based pre-dispatch filter instead. Existing `.data/archives/` directories and files become inert.

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
