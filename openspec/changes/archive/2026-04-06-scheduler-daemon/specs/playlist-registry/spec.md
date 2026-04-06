## ADDED Requirements

### Requirement: watched and check_interval_secs columns on playlists table
The `playlists` table SHALL gain two new columns:

- `watched` (INTEGER NOT NULL DEFAULT 1) — whether the playlist is included in
  automatic scheduler syncs. `1` = watched, `0` = manual sync only.
- `check_interval_secs` (INTEGER NULL DEFAULT NULL) — per-playlist override for
  the check interval in seconds. NULL means inherit the global `interval`
  setting.

Both columns SHALL be added via `ALTER TABLE` migration in `init_db()`, safe to
run against existing databases.

#### Scenario: Migration on existing DB
- **WHEN** `init_db()` is called against a DB created before this change
- **THEN** both columns SHALL be added to `playlists` with their default values;
  all existing playlists SHALL have `watched=1` and `check_interval_secs=NULL`

#### Scenario: New DB creation
- **WHEN** `init_db()` is called and no DB exists
- **THEN** the `playlists` table SHALL be created with both new columns included
  in the schema

---

### Requirement: interval settings key
The `settings` table SHALL recognise `interval` as a valid key representing
the global default sync interval in seconds (integer, stored as TEXT). The daemon
SHALL validate that the value is a positive integer when written.

> **Note**: Originally named `check-interval`; renamed to `interval` during
> implementation for consistency with the `--interval` flag used on `add` and
> `config-playlist`.

#### Scenario: Write interval
- **WHEN** `registry.set_setting("check_interval", "3600")` is called
- **THEN** the value SHALL be upserted into the `settings` table

#### Scenario: Read interval — not set
- **WHEN** `registry.get_setting("check_interval")` is called and the key has
  never been set
- **THEN** `None` SHALL be returned

---

### Requirement: Registry helpers for scheduler columns
The registry SHALL provide functions to read and write the new scheduler-related
columns.

#### Scenario: get_watched_playlists returns only watched playlists
- **WHEN** `registry.get_watched_playlists()` is called
- **THEN** the registry SHALL return all rows from `playlists` where `watched=1`,
  ordered by `added_at` ascending

#### Scenario: set_playlist_watched updates the watched flag
- **WHEN** `registry.set_playlist_watched(playlist_id, watched: bool)` is called
- **THEN** `playlists.watched` SHALL be set to `1` (if True) or `0` (if False)
  for that playlist

#### Scenario: set_playlist_interval updates per-playlist interval
- **WHEN** `registry.set_playlist_interval(playlist_id, interval_secs: int | None)` is called
- **THEN** `playlists.check_interval_secs` SHALL be updated to the given value
  (or NULL if None) for that playlist

#### Scenario: add_playlist stores watched and interval
- **WHEN** `registry.add_playlist(...)` is called with `watched` and
  `check_interval_secs` arguments
- **THEN** the new row SHALL be inserted with those values; `watched` SHALL
  default to `1` if not provided; `check_interval_secs` SHALL default to `NULL`
  if not provided
