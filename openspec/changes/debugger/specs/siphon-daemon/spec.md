## MODIFIED Requirements

### Requirement: `GET /version` endpoint
The daemon SHALL expose a `GET /version` endpoint that returns a JSON object with the fields `siphon` (the installed package version read via `importlib.metadata`) and `yt_dlp` (the yt-dlp library version).

#### Scenario: Version response
- **WHEN** `GET /version` is called
- **THEN** the response SHALL be `200 OK` with body `{ "siphon": "<semver>", "yt_dlp": "<date-ver>" }`

## ADDED Requirements

### Requirement: Live log-level propagation
When `PUT /settings/log-level` is called with a valid level, the daemon SHALL immediately call `logging.getLogger("siphon").setLevel()` with the new level after persisting to the DB. The change SHALL take effect for all handlers (stderr, file, SSE) without a daemon restart.

#### Scenario: Log level changed via API
- **WHEN** `PUT /settings/log-level` is called with value `"DEBUG"`
- **THEN** the `siphon` logger level SHALL be set to DEBUG immediately and subsequent log records SHALL reflect the new level

#### Scenario: Log level changed via CLI
- **WHEN** `siphon config log-level WARNING` is run
- **THEN** the CLI SHALL call `PUT /settings/log-level` and the daemon SHALL apply the level immediately

### Requirement: Live browser-logs propagation
When `PUT /settings/browser-logs` is called, the daemon SHALL update the cached `browser_logs` flag immediately. The `SSELogHandler` SHALL respect the new value on the next `emit()` call without restart.

#### Scenario: Browser logs enabled via API
- **WHEN** `PUT /settings/browser-logs` is called with value `"on"`
- **THEN** the SSELogHandler SHALL begin broadcasting to subscribers immediately

#### Scenario: Browser logs disabled via API
- **WHEN** `PUT /settings/browser-logs` is called with value `"off"`
- **THEN** the SSELogHandler SHALL stop broadcasting immediately

### Requirement: `/info` response includes logs directory
The `/info` endpoint response SHALL include a `logs_dir` field containing the absolute path to the directory where `siphon.log` is written (same as `db_dir`).

#### Scenario: Info response with logs_dir
- **WHEN** `GET /info` is called
- **THEN** the response SHALL include `logs_dir` with the same value as `db_dir`
