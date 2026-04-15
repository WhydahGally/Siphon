## ADDED Requirements

### Requirement: Failure recording on download error
When a download worker encounters an error for a specific item, the engine SHALL record the failure in the `failed_downloads` table. If a record already exists for that `(video_id, playlist_id)`, the `attempt_count` SHALL be incremented and `last_attempted_at` updated. The `error_message` SHALL be replaced with the most recent error.

#### Scenario: First failure for an item
- **WHEN** a video download fails for the first time
- **THEN** a row SHALL be inserted into `failed_downloads` with `attempt_count = 1`, `error_message` set to the error text, and `last_attempted_at` set to the current UTC timestamp

#### Scenario: Repeated failure for an item
- **WHEN** a video download fails and a `failed_downloads` row already exists for that `(video_id, playlist_id)`
- **THEN** `attempt_count` SHALL be incremented by 1, `error_message` SHALL be updated, and `last_attempted_at` SHALL be updated

---

### Requirement: Failure cleared on successful retry
When a previously-failed item downloads successfully, its `failed_downloads` record SHALL be deleted and a normal `items` record SHALL be inserted.

#### Scenario: Retry succeeds
- **WHEN** an item with an existing `failed_downloads` row is dispatched (via `siphon sync-failed`) and completes successfully
- **THEN** the `failed_downloads` row SHALL be deleted for that `(video_id, playlist_id)`
- **THEN** a row SHALL be inserted into `items` as normal

---

### Requirement: Failure report at end of sync
At the end of every sync run, if any failures occurred, the CLI SHALL print a failure summary listing each failed item's title and error message.

#### Scenario: One or more failures in a sync run
- **WHEN** a sync or sync-failed run completes and one or more items failed
- **THEN** the CLI SHALL print a summary section showing: total failed count, and for each failure: title and error message

#### Scenario: No failures in a sync run
- **WHEN** a sync run completes with zero failures
- **THEN** no failure summary SHALL be printed

---

### Requirement: `siphon sync-failed` command (per playlist)
`siphon sync-failed <name>` SHALL query `failed_downloads` for the named playlist and re-dispatch those entries through the same parallel engine.

#### Scenario: Named playlist has failures
- **WHEN** `siphon sync-failed <name>` is called and failures exist for that playlist
- **THEN** the engine SHALL dispatch only the failed entries for that playlist
- **THEN** on success each entry is cleared from `failed_downloads` and inserted into `items`
- **THEN** on failure `attempt_count` is incremented

#### Scenario: Named playlist has no failures
- **WHEN** `siphon sync-failed <name>` is called and no failures exist for that playlist
- **THEN** the CLI SHALL print `"No failures recorded for '<name>'."` and exit 0

#### Scenario: Playlist name does not exist
- **WHEN** `siphon sync-failed <name>` is called and no playlist with that name is registered
- **THEN** the CLI SHALL print an error and exit with a non-zero code

---

### Requirement: `siphon sync-failed` command (all playlists)
`siphon sync-failed` with no argument SHALL retry failures for all registered playlists that have at least one failure record.

#### Scenario: Multiple playlists have failures
- **WHEN** `siphon sync-failed` is called with no argument and 2 playlists have failures
- **THEN** the engine SHALL retry failures for each playlist sequentially (playlists are sequential; items within each playlist are parallel)

#### Scenario: No failures across any playlist
- **WHEN** `siphon sync-failed` is called and no failures exist in the DB
- **THEN** the CLI SHALL print `"No failures recorded."` and exit 0
