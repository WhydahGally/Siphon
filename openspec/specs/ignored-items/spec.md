## ADDED Requirements

### Requirement: Ignore list DB schema
The registry SHALL maintain an `ignored_items` table. Each row records a video that SHALL be permanently skipped during sync.

Schema:
- `video_id` (TEXT NOT NULL)
- `playlist_id` (TEXT NOT NULL DEFAULT '' — empty string means globally ignored across all playlists; a non-empty value scopes the ignore to that specific playlist)
- `reason` (TEXT, nullable — user-provided label, e.g. "region locked")
- `ignored_at` (TEXT NOT NULL — UTC ISO 8601 timestamp)
- PRIMARY KEY: `(video_id, playlist_id)`

> **Note**: SQLite does not support expressions in PRIMARY KEY constraints, so `NULL` cannot be used as a sentinel for "global ignore". An empty string `''` is used instead.

#### Scenario: Ignore table created on init
- **WHEN** `registry.init_db()` is called on a new or existing database
- **THEN** the `ignored_items` table SHALL exist with the schema above

---

### Requirement: Ignore list write
The registry SHALL provide a function to add a video to the ignore list.

#### Scenario: Add a playlist-scoped ignore
- **WHEN** `registry.insert_ignored(video_id, playlist_id=<id>, reason=<str>)` is called
- **THEN** a row SHALL be inserted with the given `playlist_id` and `reason`, and `ignored_at` set to the current UTC timestamp

#### Scenario: Add a global ignore
- **WHEN** `registry.insert_ignored(video_id, playlist_id=None, reason=<str>)` is called
- **THEN** a row SHALL be inserted with `playlist_id = ''` (empty string)

#### Scenario: Duplicate ignore insert
- **WHEN** `insert_ignored` is called for a `(video_id, playlist_id)` combination that already exists
- **THEN** the insert SHALL be silently ignored (INSERT OR IGNORE semantics)

---

### Requirement: Ignore list read (sync filter)
The registry SHALL provide a function to check whether a video should be skipped for a given playlist.

#### Scenario: Video is globally ignored
- **WHEN** `registry.is_ignored(video_id, playlist_id)` is called and a row exists with `playlist_id = ''` (empty string) and that `video_id`
- **THEN** the function SHALL return `True`

#### Scenario: Video is ignored for this specific playlist
- **WHEN** `registry.is_ignored(video_id, playlist_id)` is called and a row exists with that `(video_id, playlist_id)` pair
- **THEN** the function SHALL return `True`

#### Scenario: Video is not ignored
- **WHEN** `registry.is_ignored(video_id, playlist_id)` is called and no matching row exists
- **THEN** the function SHALL return `False`

---

### Requirement: Ignore list is for future UI write path
The `ignored_items` table and registry helpers SHALL be created in this change to support future read filtering. No CLI command for adding to the ignore list is introduced in this change. The table starts empty; filtering is applied but no items will be skipped until a write path is added (in a future change).

#### Scenario: Table exists and is empty on first sync with new schema
- **WHEN** the schema migration runs for the first time and `siphon sync` is executed
- **THEN** no items SHALL be filtered by the ignore list (no rows exist)
- **THEN** the ignore list filter code path SHALL be exercised without error
