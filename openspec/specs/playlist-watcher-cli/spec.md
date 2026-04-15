## ADDED Requirements

### Requirement: CLI entry point
The system SHALL expose a `siphon` command installed via `pyproject.toml` `[project.scripts]`. The command SHALL support eight subcommands: `add`, `sync`, `sync-failed`, `list`, `delete`, `config`, `config-playlist`, and `watch`. Invoking `siphon` without a subcommand or with `--help` SHALL print usage information.

#### Scenario: Entry point is installed
- **WHEN** the package is installed with `pip install -e .`
- **THEN** `siphon --help` SHALL print usage without error

#### Scenario: Unknown subcommand
- **WHEN** an unrecognised subcommand is passed (e.g., `siphon foo`)
- **THEN** the CLI SHALL print an error and usage, and exit with a non-zero code

---

### Requirement: `siphon add` subcommand
`siphon add <url>` SHALL register a YouTube playlist in the registry. If `--download` is provided, it SHALL also immediately download all items in the playlist.

#### Scenario: Add a new playlist
- **WHEN** `siphon add <url>` is called with a valid YT playlist URL and the playlist is not already registered
- **THEN** the CLI SHALL fetch the playlist title from YouTube (without downloading content), register it in the DB, print confirmation with the fetched name and playlist ID, and exit 0

#### Scenario: Add with --download flag
- **WHEN** `siphon add <url> --download` is called
- **THEN** the CLI SHALL register the playlist and immediately begin downloading all items, persisting each item record via `on_item_complete`

#### Scenario: Add a playlist already registered
- **WHEN** `siphon add <url>` is called and the playlist ID is already in the registry
- **THEN** the CLI SHALL print an error ("Playlist already registered. Use 'siphon sync' to fetch new items.") and exit with a non-zero code

---

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

### Requirement: `siphon list` subcommand
`siphon list` SHALL display all registered playlists with their item counts and last synced timestamps.

#### Scenario: Playlists exist
- **WHEN** `siphon list` is called and at least one playlist is registered
- **THEN** the CLI SHALL print a table with columns: NAME, URL, ITEMS, LAST SYNCED. LAST SYNCED SHALL show "never" if `last_synced_at` is NULL.

#### Scenario: No playlists registered
- **WHEN** `siphon list` is called and no playlists are registered
- **THEN** the CLI SHALL print "No playlists registered." and exit 0

---

### Requirement: `siphon config` subcommand
`siphon config <key> [<value>]` SHALL read or write a global configuration setting stored in the DB `settings` table via the daemon API. The set of known keys is: `mb-user-agent`, `log-level`, `max-concurrent-downloads`, `interval`. Attempting to read or write an unknown key SHALL print an error listing valid keys and exit with a non-zero code.

#### Scenario: Read a setting that has been set
- **WHEN** `siphon config <key>` is called and the key has a stored value
- **THEN** the CLI SHALL print `"<key>: <value>"` and exit 0

#### Scenario: Read a setting that has not been set
- **WHEN** `siphon config <key>` is called and no value is stored
- **THEN** the CLI SHALL print `"<key>: (not set)"` and exit 0

#### Scenario: Write a setting
- **WHEN** `siphon config <key> <value>` is called with a valid key
- **THEN** the CLI SHALL call PUT /settings/{key} on the daemon, print `"Set <key>."`, and exit 0

#### Scenario: Unknown config key
- **WHEN** `siphon config <unknown-key>` is called
- **THEN** the CLI SHALL print an error listing the known keys and exit with a non-zero code

#### Scenario: Write interval — invalid value
- **WHEN** `siphon config interval abc` or a non-positive integer is passed
- **THEN** the CLI SHALL print an error and exit non-zero without writing to the daemon

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

### Requirement: Live download progress display
During `siphon add --download`, `siphon sync`, and `siphon sync-failed`, the CLI SHALL print a numbered list of all items planned for download before any download begins. As each item completes, the CLI SHALL emit a result log line for that item. Consecutive lines from the same item may interleave with output from another item in rare cases of near-simultaneous completion — this is acceptable and by design. After all items complete, the CLI SHALL print a summary line.

#### Scenario: Planned items list printed before download starts
- **WHEN** `_sync_parallel` (or the `add --download` path) has filtered entries and is about to dispatch
- **THEN** the CLI SHALL print a numbered list of all to-download titles, in playlist order, before any worker thread starts

#### Scenario: Item completes successfully
- **WHEN** a worker thread completes an item without error
- **THEN** the CLI SHALL print: a `✓ <filename>  [<size> · <elapsed>s]` success line; if auto_rename is enabled and a rename occurred, a second line showing `  Renamed: "<original>" → "<final>"  [<tier>]`

#### Scenario: Item completes with failure
- **WHEN** a worker thread fails on an item
- **THEN** the CLI SHALL print a `✗ <title> — <error message>` failure line

#### Scenario: Concurrent items complete simultaneously
- **WHEN** two or more worker threads complete at nearly the same time
- **THEN** each individual log line is atomic; consecutive lines from the same item may interleave with lines from another item in rare cases of near-simultaneous completion — this is acceptable and by design

#### Scenario: Already up to date
- **WHEN** after filtering, no new items remain to download
- **THEN** the CLI SHALL print `"<playlist>: Already up to date. (<N> total)"` and exit without downloading anything

---

### Requirement: Configurable log level
`siphon config log-level [<value>]` SHALL read or set the logging verbosity for the `siphon` logger. Valid values are `DEBUG`, `INFO`, `WARNING`, and `ERROR` (case-insensitive at write time; stored upper-cased). When unset, the effective level SHALL be `INFO`.

#### Scenario: Set log level to DEBUG
- **WHEN** `siphon config log-level DEBUG` is run
- **THEN** the CLI SHALL persist `DEBUG` in the DB settings table and print `Set log-level.`

#### Scenario: Invalid log level value
- **WHEN** `siphon config log-level VERBOSE` (or any value not in the valid set) is run
- **THEN** the CLI SHALL print an error listing the valid values and exit with a non-zero code without modifying the DB

#### Scenario: Read log level when set
- **WHEN** `siphon config log-level` is run and a value has been previously set
- **THEN** the CLI SHALL print `log-level: <stored-value>`

#### Scenario: Read log level when unset
- **WHEN** `siphon config log-level` is run on a fresh install with no stored value
- **THEN** the CLI SHALL print `log-level: (not set)`

#### Scenario: Log level applied at startup — DB initialised
- **WHEN** the DB already exists and `log_level` is set to `DEBUG`
- **THEN** every subsequent `siphon` invocation SHALL apply `DEBUG` level to the `siphon` logger before any command runs

#### Scenario: Log level applied at startup — DB not yet initialised
- **WHEN** the DB has not been initialised (fresh install, first run)
- **THEN** the CLI SHALL silently fall back to `INFO` and proceed normally without error

---

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

---

### Requirement: `siphon watch` subcommand
`siphon watch` SHALL start the FastAPI daemon and `PlaylistScheduler`. It SHALL
be the container's primary `CMD` and the prerequisite for all other subcommands.
It SHALL NOT return until the process receives SIGTERM.

#### Scenario: watch starts daemon
- **WHEN** `siphon watch` is run
- **THEN** the daemon SHALL start, bind to `0.0.0.0:8000`, initialise the DB,
  start the scheduler, and log a startup message

#### Scenario: watch is the container CMD
- **WHEN** the Docker container starts with the default CMD
- **THEN** `siphon watch` SHALL be invoked automatically

---

### Requirement: Daemon prerequisite for all subcommands
All `siphon` subcommands other than `watch` SHALL require the daemon to be
running at `http://localhost:8000`. If the daemon is not reachable, the command
SHALL print a clear error and exit non-zero.

#### Scenario: Daemon not running
- **WHEN** any subcommand other than `watch` is invoked and the daemon is not
  reachable on port 8000
- **THEN** the CLI SHALL print `"siphon watch is not running. Start it with 'siphon watch'."` and exit with a non-zero code

#### Scenario: Daemon running
- **WHEN** a subcommand is invoked and the daemon responds on port 8000
- **THEN** the subcommand SHALL proceed normally

---

### Requirement: `siphon add` — --no-watch flag
`siphon add` SHALL accept a `--no-watch` flag. When set, the registered playlist
SHALL have `watched=0` and SHALL NOT be added to the `PlaylistScheduler`. The
playlist can still be synced manually via `siphon sync <name>`.

#### Scenario: Add with --no-watch
- **WHEN** `siphon add <url> --no-watch` is called
- **THEN** the playlist SHALL be registered with `watched=0`, the daemon SHALL
  NOT arm a timer for it, and the confirmation message SHALL note that automatic
  syncing is disabled

#### Scenario: Add without --no-watch (default)
- **WHEN** `siphon add <url>` is called without `--no-watch`
- **THEN** the playlist SHALL be registered with `watched=1` and the daemon SHALL
  arm a timer for it via `PlaylistScheduler.add_playlist()`

---

### Requirement: `siphon add` — --interval flag
`siphon add` SHALL accept `--interval <seconds>` (positive integer). When set,
the playlist SHALL be stored with `check_interval_secs = <seconds>`.

#### Scenario: Add with --interval
- **WHEN** `siphon add <url> --interval 3600` is called
- **THEN** the playlist SHALL be registered with `check_interval_secs=3600` and
  the scheduler SHALL use this interval for its timer

#### Scenario: Add with --interval and --no-watch
- **WHEN** `siphon add <url> --no-watch --interval 3600` is called
- **THEN** `check_interval_secs=3600` SHALL be stored in the DB; no timer SHALL
  be armed (--no-watch takes precedence)

#### Scenario: --interval value is not a positive integer
- **WHEN** `siphon add <url> --interval 0` or `--interval -1` is called
- **THEN** the CLI SHALL print an error and exit non-zero without registering the
  playlist

---

### Requirement: All subcommands refactored as HTTP clients
Every `siphon` subcommand other than `watch` SHALL make HTTP requests to the
daemon API rather than directly accessing the DB or calling business logic
functions. The CLI layer becomes a thin presentation wrapper.

#### Scenario: siphon add calls POST /playlists
- **WHEN** `siphon add <url>` is called
- **THEN** the CLI SHALL POST to `http://localhost:8000/playlists` and print the
  result; it SHALL NOT call `registry.*` functions directly

#### Scenario: siphon list calls GET /playlists
- **WHEN** `siphon list` is called
- **THEN** the CLI SHALL GET `http://localhost:8000/playlists` and render the response as a table

#### Scenario: siphon sync calls POST /playlists/{id}/sync
- **WHEN** `siphon sync [<name>]` is called
- **THEN** the CLI SHALL POST to the appropriate sync endpoint and print status

#### Scenario: siphon config <key> <value> calls PUT /settings/{key}
- **WHEN** `siphon config interval 3600` is called
- **THEN** the CLI SHALL PUT to `http://localhost:8000/settings/interval`

---

### Requirement: `siphon config-playlist` subcommand
`siphon config-playlist <name> [<key> [<value>]]` SHALL read or write a
per-playlist setting for a playlist already registered in the DB. The set of
known per-playlist keys is: `interval`, `watched`, `auto-rename`. Omitting both
`<key>` and `<value>` SHALL print all current settings for the named playlist.
Omitting only `<value>` SHALL print the current value of the given key.

#### Scenario: Show all settings for a playlist
- **WHEN** `siphon config-playlist "Listen Later"` is called (no key)
- **THEN** the CLI SHALL print `name`, `watched`, `interval`, and `auto-rename`
  for that playlist and exit 0; if no per-playlist interval is set, `interval`
  SHALL display as `<N> (global default)` where N is the resolved fallback value

#### Scenario: Read one key
- **WHEN** `siphon config-playlist "Listen Later" interval` is called
- **THEN** the CLI SHALL print the current per-playlist interval, or `<N> (global default)`
  showing the resolved fallback value if no per-playlist interval is set

#### Scenario: Set interval
- **WHEN** `siphon config-playlist "Listen Later" interval 3600` is called
- **THEN** the CLI SHALL PATCH `/playlists/{id}` with `{"check_interval_secs": 3600}`,
  the scheduler SHALL reschedule the playlist with the new interval, and the CLI
  SHALL print `"Set interval for 'Listen Later'."` and exit 0

#### Scenario: Set watched
- **WHEN** `siphon config-playlist "Listen Later" watched false` is called
- **THEN** the CLI SHALL PATCH `/playlists/{id}` with `{"watched": false}` and
  the scheduler SHALL cancel the playlist's timer

#### Scenario: Set auto-rename
- **WHEN** `siphon config-playlist "Listen Later" auto-rename true` is called
- **THEN** the CLI SHALL PATCH `/playlists/{id}` with `{"auto_rename": true}`

#### Scenario: Unknown playlist name
- **WHEN** `siphon config-playlist "No Such Playlist" interval 3600` is called
- **THEN** the CLI SHALL print an error and exit non-zero

#### Scenario: Unknown per-playlist key
- **WHEN** `siphon config-playlist "Listen Later" unknown-key value` is called
- **THEN** the CLI SHALL print an error listing the known per-playlist keys and exit non-zero
