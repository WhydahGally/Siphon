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

#### Scenario: Add with --format and --quality
- **WHEN** `siphon add <url> --format mp4 --quality 1080` is called
- **THEN** the CLI SHALL register the playlist with `format=mp4` and `quality=1080`; both SHALL be persisted in the registry and reused on every subsequent `siphon sync`
- **WHEN** `--quality` is omitted
- **THEN** `quality` SHALL default to `"best"`
- **WHEN** `--quality` is provided with a non-video format (e.g. `mp3`)
- **THEN** the `quality` value SHALL be stored but ignored by the download engine (audio mode does not use quality)

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
