## ADDED Requirements

### Requirement: CLI entry point
The system SHALL expose a `siphon` command installed via `pyproject.toml` `[project.scripts]`. The command SHALL support four subcommands: `add`, `sync`, `list`, and `delete`. Invoking `siphon` without a subcommand or with `--help` SHALL print usage information.

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

#### Scenario: URL is not a playlist
- **WHEN** `siphon add <url>` is called with a single-video URL (no `list=` param)
- **THEN** the CLI SHALL print an error ("Only playlist URLs are supported by siphon add.") and exit with a non-zero code

---

### Requirement: `siphon sync` subcommand
`siphon sync` SHALL fetch new items for all registered playlists and download only those not already in the local archive. `siphon sync <name>` SHALL sync only the named playlist.

#### Scenario: Sync all playlists — new items exist
- **WHEN** `siphon sync` is called and one or more playlists have new items on YouTube
- **THEN** the CLI SHALL download only new items for each playlist (using the yt-dlp archive file to skip known items), persist each via `on_item_complete`, and update `last_synced_at` for each synced playlist

#### Scenario: Sync all playlists — already up to date
- **WHEN** `siphon sync` is called and no new items exist in any playlist
- **THEN** the CLI SHALL print "Already up to date." (with item counts per playlist) and update `last_synced_at` for each playlist

#### Scenario: Sync named playlist — name exists
- **WHEN** `siphon sync <name>` is called and a playlist with that name is registered
- **THEN** the CLI SHALL sync only that playlist

#### Scenario: Sync named playlist — name does not exist
- **WHEN** `siphon sync <name>` is called and no playlist with that name is in the registry
- **THEN** the CLI SHALL print an error: `"No playlist named '<name>'. Run 'siphon list' to see registered playlists."` and exit with a non-zero code

#### Scenario: Sync — YT playlist is deleted or privated
- **WHEN** yt-dlp reports the playlist as unavailable during sync
- **THEN** the CLI SHALL log a warning, print a message to the user, update `last_synced_at`, and exit 0 (not crash)

#### Scenario: Sync — no playlists registered
- **WHEN** `siphon sync` is called and the registry has no playlists
- **THEN** the CLI SHALL print "No playlists registered. Use 'siphon add <url>' to add one." and exit 0

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
`siphon config <key> [<value>]` SHALL read or write a global configuration setting stored in the DB `settings` table. When called with only a key, it prints the current value. When called with a key and value, it persists the value.

#### Scenario: Read a setting that has been set
- **WHEN** `siphon config <key>` is called and the key has a stored value
- **THEN** the CLI SHALL print `"<key>: <value>"` and exit 0

#### Scenario: Read a setting that has not been set
- **WHEN** `siphon config <key>` is called and no value is stored
- **THEN** the CLI SHALL print `"<key>: (not set)"` and exit 0

#### Scenario: Write a setting
- **WHEN** `siphon config <key> <value>` is called
- **THEN** the CLI SHALL upsert the value in the settings table, print `"Set <key>."`, and exit 0

#### Scenario: Unknown config key
- **WHEN** `siphon config <key>` is called with an unrecognised key
- **THEN** the CLI SHALL print an error listing the known keys and exit with a non-zero code

---

### Requirement: `siphon delete` subcommand
`siphon delete <name>` SHALL remove a registered playlist from the registry and delete its yt-dlp archive file. Downloaded music files SHALL NOT be touched. The command SHALL always ask for interactive confirmation before proceeding.

#### Scenario: Delete an existing playlist — confirmed
- **WHEN** `siphon delete <name>` is called, the playlist exists, and the user confirms at the prompt
- **THEN** the CLI SHALL delete the playlist row and all its item rows from the DB, delete `.data/archives/<playlist_id>.txt` if it exists, print a confirmation message, and exit 0

#### Scenario: Delete an existing playlist — cancelled
- **WHEN** `siphon delete <name>` is called, the playlist exists, and the user declines at the prompt
- **THEN** the CLI SHALL print "Cancelled. No changes made." and exit 0

#### Scenario: Delete a playlist that does not exist
- **WHEN** `siphon delete <name>` is called and no playlist with that name is in the registry
- **THEN** the CLI SHALL print an error: `"No playlist named '<name>'. Run 'siphon list' to see registered playlists."` and exit with a non-zero code

#### Scenario: Archive file missing at delete time
- **WHEN** `siphon delete <name>` is confirmed but the archive file `.data/archives/<playlist_id>.txt` does not exist on disk
- **THEN** the CLI SHALL proceed with deleting the DB rows, skip the archive file deletion silently, and exit 0

---

### Requirement: Live download progress display
During `siphon add --download` and `siphon sync`, the CLI SHALL print a live per-file progress line to stdout that overwrites itself on each yt-dlp progress tick. When a file finishes downloading, the CLI SHALL replace the progress line with a checkmark and the filename.

#### Scenario: File is downloading
- **WHEN** yt-dlp emits a `downloading` progress event for a file
- **THEN** the CLI SHALL print a `\r`-overwriting line showing the filename, percentage complete, bytes downloaded / total, download speed, and ETA

#### Scenario: File download completes
- **WHEN** yt-dlp emits a `finished` progress event for a file
- **THEN** the CLI SHALL print a final line with a checkmark (✓) and the filename, ending with a newline

#### Scenario: Total size is unknown
- **WHEN** yt-dlp cannot determine the total file size
- **THEN** the CLI SHALL show bytes downloaded and speed only, omitting percentage and ETA

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
