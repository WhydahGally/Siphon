## ADDED Requirements

### Requirement: `siphon sync-failed` subcommand
`siphon sync-failed [<name>]` SHALL retry all persisted failures from the `failed_downloads` table. Without an argument it retries failures for all registered playlists. With a playlist name argument it retries failures for that playlist only.

#### Scenario: Add sync-failed to CLI entry point
- **WHEN** the package is installed
- **THEN** `siphon sync-failed --help` SHALL print usage without error

#### Scenario: Retry failures for a named playlist
- **WHEN** `siphon sync-failed <name>` is called and failures exist for that playlist
- **THEN** the CLI SHALL dispatch the failed entries through the parallel engine, report results, and exit 0

#### Scenario: Retry failures for all playlists
- **WHEN** `siphon sync-failed` is called with no argument
- **THEN** the CLI SHALL iterate all playlists with failures and retry them sequentially (playlist-level is sequential; within each playlist is parallel)

#### Scenario: No failures for named playlist
- **WHEN** `siphon sync-failed <name>` is called and no failures exist for that playlist
- **THEN** the CLI SHALL print `"No failures recorded for '<name>'."` and exit 0

#### Scenario: No failures at all
- **WHEN** `siphon sync-failed` is called with no argument and no failures exist in the DB
- **THEN** the CLI SHALL print `"No failures recorded."` and exit 0

#### Scenario: Unknown playlist name
- **WHEN** `siphon sync-failed <name>` is called and no playlist with that name is in the registry
- **THEN** the CLI SHALL print an error and exit with a non-zero code

---

### Requirement: `max-concurrent-downloads` config key
`siphon config max-concurrent-downloads [<value>]` SHALL read or write the maximum number of simultaneous downloads used by the parallel engine. The value SHALL be an integer between 1 and 10 inclusive. The default effective value when unset SHALL be 5.

#### Scenario: Set max-concurrent-downloads
- **WHEN** `siphon config max-concurrent-downloads 3` is run
- **THEN** the CLI SHALL persist `3` in the settings table and print `Set max-concurrent-downloads.`

#### Scenario: Invalid value — out of range
- **WHEN** `siphon config max-concurrent-downloads 0` or `siphon config max-concurrent-downloads 11` is run
- **THEN** the CLI SHALL print an error (`"max-concurrent-downloads must be between 1 and 10"`) and exit with a non-zero code without modifying the DB

#### Scenario: Invalid value — non-integer
- **WHEN** `siphon config max-concurrent-downloads abc` is run
- **THEN** the CLI SHALL print an error and exit with a non-zero code

#### Scenario: Read max-concurrent-downloads when set
- **WHEN** `siphon config max-concurrent-downloads` is run and a value has been stored
- **THEN** the CLI SHALL print `max-concurrent-downloads: <value>`

#### Scenario: Read max-concurrent-downloads when unset
- **WHEN** `siphon config max-concurrent-downloads` is run on a fresh install
- **THEN** the CLI SHALL print `max-concurrent-downloads: (not set)`

---

### Requirement: Sync overall progress line
During `sync` and `sync-failed`, the CLI SHALL print an overall progress summary that updates as items complete: `Syncing '<name>': X / N downloaded`.

#### Scenario: Progress during sync
- **WHEN** a sync is in progress with N total items to download
- **THEN** the CLI SHALL update the overall progress line as each item completes, showing the current completed count out of total

#### Scenario: Progress at completion
- **WHEN** all items have completed
- **THEN** the CLI SHALL print a final summary: `"<name>: N new item(s) added. (M total)"` or `"<name>: Already up to date. (M total)"`

## MODIFIED Requirements

### Requirement: `siphon sync` subcommand
`siphon sync` SHALL fetch new items for all registered playlists and download only those not already recorded in the `items` DB table. `siphon sync <name>` SHALL sync only the named playlist. Deduplication is performed via DB lookup before dispatch — no yt-dlp archive file is used.

#### Scenario: Sync all playlists — new items exist
- **WHEN** `siphon sync` is called and one or more playlists have new items on YouTube
- **THEN** the CLI SHALL enumerate entries via `extract_flat`, filter against `items` / `ignored_items` / `failed_downloads` (attempt >= 3), dispatch remaining entries to the parallel engine, persist each success via `registry.insert_item`, and update `last_synced_at` for each synced playlist

#### Scenario: Sync all playlists — already up to date
- **WHEN** `siphon sync` is called and no new items exist in any playlist after filtering
- **THEN** the CLI SHALL print `"Already up to date."` per playlist and update `last_synced_at`

#### Scenario: Sync named playlist — name exists
- **WHEN** `siphon sync <name>` is called and a playlist with that name is registered
- **THEN** the CLI SHALL sync only that playlist using the parallel engine

#### Scenario: Sync named playlist — name does not exist
- **WHEN** `siphon sync <name>` is called and no playlist with that name is in the registry
- **THEN** the CLI SHALL print an error: `"No playlist named '<name>'. Run 'siphon list' to see registered playlists."` and exit with a non-zero code

#### Scenario: Sync — YT playlist is deleted or privated
- **WHEN** yt-dlp reports the playlist as unavailable during `extract_flat`
- **THEN** the CLI SHALL log a warning, print a message to the user, update `last_synced_at`, and exit 0

#### Scenario: Sync — no playlists registered
- **WHEN** `siphon sync` is called and the registry has no playlists
- **THEN** the CLI SHALL print `"No playlists registered. Use 'siphon add <url>' to add one."` and exit 0

---

### Requirement: `siphon delete` subcommand
`siphon delete <name>` SHALL remove a registered playlist from the registry. Downloaded music files SHALL NOT be touched. The command SHALL ask for interactive confirmation. Archive file deletion is removed — there is no longer an archive file to delete.

#### Scenario: Delete an existing playlist — confirmed
- **WHEN** `siphon delete <name>` is called, the playlist exists, and the user confirms at the prompt
- **THEN** the CLI SHALL delete the playlist row, all its `items` rows, all its `failed_downloads` rows, all its `ignored_items` rows (where `playlist_id` matches) from the DB, print a confirmation message, and exit 0

#### Scenario: Delete an existing playlist — cancelled
- **WHEN** `siphon delete <name>` is called, the playlist exists, and the user declines at the prompt
- **THEN** the CLI SHALL print `"Cancelled. No changes made."` and exit 0

#### Scenario: Delete a playlist that does not exist
- **WHEN** `siphon delete <name>` is called and no playlist with that name is in the registry
- **THEN** the CLI SHALL print an error and exit with a non-zero code

---

### Requirement: `siphon config` subcommand
`siphon config <key> [<value>]` SHALL read or write a global configuration setting. The set of known keys is: `mb-user-agent`, `log-level`, `max-concurrent-downloads`. Attempting to read or write an unknown key SHALL print an error listing valid keys and exit with a non-zero code.

#### Scenario: Read a setting that has been set
- **WHEN** `siphon config <key>` is called and the key has a stored value
- **THEN** the CLI SHALL print `"<key>: <value>"` and exit 0

#### Scenario: Read a setting that has not been set
- **WHEN** `siphon config <key>` is called and no value is stored
- **THEN** the CLI SHALL print `"<key>: (not set)"` and exit 0

#### Scenario: Write a setting
- **WHEN** `siphon config <key> <value>` is called with a valid key
- **THEN** the CLI SHALL upsert the value, print `"Set <key>."`, and exit 0

#### Scenario: Unknown config key
- **WHEN** `siphon config <unknown-key>` is called
- **THEN** the CLI SHALL print an error listing the known keys and exit with a non-zero code

## MODIFIED Requirements

### Requirement: Live download progress display
During `siphon add --download`, `siphon sync`, and `siphon sync-failed`, the CLI SHALL display a fixed multi-slot progress area — one line per active download — updated in place using ANSI cursor movement. Above the slot area, completed items are printed with a checkmark or failure indicator as they finish. The overall `X / N` count SHALL be shown on a dedicated summary line.

#### Scenario: Multiple files downloading simultaneously
- **WHEN** W worker threads are each downloading a different file
- **THEN** the CLI SHALL display W active progress lines, each showing filename, percentage, bytes, speed, and ETA for its respective download
- **THEN** the lines SHALL refresh in place at approximately 10 Hz without interleaving output from different threads

#### Scenario: Item completes (success)
- **WHEN** a worker thread completes an item successfully
- **THEN** the CLI SHALL print a `✓ <filename>` line above the slot area and clear the slot

#### Scenario: Item completes (failure)
- **WHEN** a worker thread fails on an item
- **THEN** the CLI SHALL print a `✗ <title> — <error>` line above the slot area and clear the slot

#### Scenario: Total size is unknown
- **WHEN** yt-dlp cannot determine the total file size for an active download
- **THEN** that slot SHALL show bytes downloaded and speed only, omitting percentage and ETA

#### Scenario: Fewer active downloads than max workers
- **WHEN** fewer items remain than the configured worker count
- **THEN** empty slots SHALL be blank; the display SHALL not show phantom rows
