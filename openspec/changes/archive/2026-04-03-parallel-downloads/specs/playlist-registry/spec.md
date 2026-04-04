## ADDED Requirements

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
The registry SHALL maintain an `ignored_items` table. See `specs/ignored-items/spec.md` for the full schema and behaviour requirements.

#### Scenario: Table created on init
- **WHEN** `init_db()` is called
- **THEN** the `ignored_items` table SHALL exist

## MODIFIED Requirements

### Requirement: Persistent playlist registry
The system SHALL maintain a SQLite database at `.data/siphon.db` that stores all registered playlists and their downloaded items. The database SHALL be created automatically on first use if it does not exist. The `.data/` folder SHALL be git-ignored via an entry in the root `.gitignore`. The `.data/archives/` subdirectory SHALL NOT be created; archive file management is removed from the registry.

#### Scenario: First startup — no DB exists
- **WHEN** any `siphon` subcommand is invoked and `.data/siphon.db` does not exist
- **THEN** the registry SHALL create `.data/` and initialise the database with all tables: `playlists`, `items`, `settings`, `failed_downloads`, `ignored_items`
- **THEN** WAL mode SHALL be enabled

#### Scenario: Subsequent startup — DB exists
- **WHEN** any `siphon` subcommand is invoked and `.data/siphon.db` already exists
- **THEN** the registry SHALL open the existing database, apply WAL mode, and run schema migrations for any new tables without altering existing data

## REMOVED Requirements

### Requirement: Archive path management
**Reason**: The yt-dlp `download_archive` mechanism is superseded by the `items` DB table as the sole deduplication source. The registry no longer needs to compute, create, or return archive file paths.
**Migration**: `registry.archive_path(playlist_id)` is removed. Any callers that used it to pass `download_archive` to yt-dlp SHALL be updated to use the DB-based pre-dispatch filter instead. Existing `.data/archives/` directories and files become inert.
