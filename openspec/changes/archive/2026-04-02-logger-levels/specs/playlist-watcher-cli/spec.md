## ADDED Requirements

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
