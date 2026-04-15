## ADDED Requirements

### Requirement: registry.py logging — DB initialization
`registry.py` SHALL import and use `logger = logging.getLogger(__name__)`. On `init()`, it SHALL log at INFO: `"Database initialized at {path}"`. Each migration step SHALL be logged at DEBUG: `"Running migration: {description}"`. Migration `ALTER TABLE` no-ops (column already exists) SHALL be logged at DEBUG: `"Migration already applied: {column}"`.

#### Scenario: DB init logged
- **WHEN** `registry.init()` is called
- **THEN** an INFO log `"Database initialized at {path}"` SHALL be emitted

#### Scenario: Migration logged
- **WHEN** a migration runs during init
- **THEN** a DEBUG log SHALL be emitted for each migration step

### Requirement: registry.py logging — playlist and settings operations
`add_playlist()` SHALL log at INFO: `"Playlist registered: {name} ({id})"`. `remove_playlist()` SHALL log at INFO: `"Playlist removed: {id}"`. `set_setting()` SHALL log at DEBUG: `"Setting updated: {key}={value}"`. New thread DB connections SHALL be logged at DEBUG: `"New DB connection for thread {thread_id}"`.

#### Scenario: Playlist registration logged
- **WHEN** `add_playlist()` succeeds
- **THEN** an INFO log with the playlist name and ID SHALL be emitted

#### Scenario: Setting update logged
- **WHEN** `set_setting()` is called
- **THEN** a DEBUG log with the key and value SHALL be emitted

### Requirement: downloader.py logging — download lifecycle
`download()` SHALL log at INFO on entry: `"Starting download: {url} (mode={mode})"` and on exit: `"Download complete: {url}"`. Format selector construction SHALL be logged at DEBUG. Postprocessor chain SHALL be logged at DEBUG. When yt-dlp silently skips a video via `ignoreerrors=True`, the `_YtdlpLogger.error()` handler SHALL log at WARNING: `"Video skipped by yt-dlp: {message}"`.

#### Scenario: Download entry logged
- **WHEN** `download()` is called
- **THEN** an INFO log with the URL and mode SHALL be emitted

#### Scenario: Download exit logged
- **WHEN** `download()` completes
- **THEN** an INFO log SHALL be emitted

### Requirement: renamer.py logging — MusicBrainz and noise patterns
MusicBrainz HTTP requests SHALL be logged at DEBUG with the query, HTTP status code, and response latency in milliseconds. Rate-limit waits SHALL be logged at DEBUG with the wait duration. Noise pattern stripping SHALL be logged at DEBUG with before and after values when text is actually modified.

#### Scenario: MB request logged
- **WHEN** a MusicBrainz HTTP request is made
- **THEN** a DEBUG log with query, status code, and latency SHALL be emitted

#### Scenario: Noise stripping logged
- **WHEN** a noise pattern modifies the title text
- **THEN** a DEBUG log with before and after values SHALL be emitted

### Requirement: watcher.py logging — API, SSE, and scheduler
All API route handlers SHALL log at DEBUG: `"{method} {path}"`. SSE client connections and disconnections SHALL be logged at DEBUG with the endpoint name. `PlaylistScheduler` thread start and stop SHALL be logged at INFO. Settings changes via the API SHALL be logged at INFO: `"Setting changed: {key} → {value}"`. Per-item sync start SHALL be logged at DEBUG: `"Syncing item: {video_id} ({title})"`.

#### Scenario: API request logged
- **WHEN** any API endpoint is called
- **THEN** a DEBUG log with the HTTP method and path SHALL be emitted

#### Scenario: SSE connection logged
- **WHEN** an SSE client connects to any stream endpoint
- **THEN** a DEBUG log SHALL be emitted

#### Scenario: Setting change logged
- **WHEN** a setting is changed via `PUT /settings/{key}`
- **THEN** an INFO log with the key and new value SHALL be emitted
