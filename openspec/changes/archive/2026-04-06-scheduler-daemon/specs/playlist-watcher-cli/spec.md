## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: `siphon config` subcommand
`siphon config <key> [<value>]` SHALL read or write a global configuration
setting stored in the DB `settings` table via the daemon API. The set of known
keys is: `mb-user-agent`, `log-level`, `max-concurrent-downloads`, `interval`.
Attempting to read or write an unknown key SHALL print an error listing valid
keys and exit with a non-zero code.

#### Scenario: Read a setting that has been set
- **WHEN** `siphon config <key>` is called and the key has a stored value
- **THEN** the CLI SHALL print `"<key>: <value>"` and exit 0

#### Scenario: Read a setting that has not been set
- **WHEN** `siphon config <key>` is called and no value is stored
- **THEN** the CLI SHALL print `"<key>: (not set)"` and exit 0

#### Scenario: Write a setting
- **WHEN** `siphon config <key> <value>` is called with a valid key
- **THEN** the CLI SHALL call PUT /settings/{key} on the daemon, print
  `"Set <key>."`, and exit 0

#### Scenario: Unknown config key
- **WHEN** `siphon config <unknown-key>` is called
- **THEN** the CLI SHALL print an error listing the known keys and exit with a
  non-zero code

#### Scenario: Write interval — invalid value
- **WHEN** `siphon config interval abc` or a non-positive integer is passed
- **THEN** the CLI SHALL print an error and exit non-zero without writing to the
  daemon

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

---

### Requirement: CLI entry point
The system SHALL expose a `siphon` command installed via `pyproject.toml`
`[project.scripts]`. The command SHALL support eight subcommands: `add`, `sync`,
`sync-failed`, `list`, `delete`, `config`, `config-playlist`, and `watch`.
Invoking `siphon` without a subcommand or with `--help` SHALL print usage
information.

#### Scenario: Entry point is installed
- **WHEN** the package is installed with `pip install -e .`
- **THEN** `siphon --help` SHALL print usage without error

#### Scenario: Unknown subcommand
- **WHEN** an unrecognised subcommand is passed (e.g., `siphon foo`)
- **THEN** the CLI SHALL print an error and usage, and exit with a non-zero code
