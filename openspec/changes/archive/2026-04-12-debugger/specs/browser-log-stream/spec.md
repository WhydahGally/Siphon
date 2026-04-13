## ADDED Requirements

### Requirement: SSELogHandler broadcasts log records to subscribers
The daemon SHALL implement a custom `logging.Handler` subclass (`SSELogHandler`) attached to the `siphon` logger. When `browser_logs` is enabled and at least one SSE subscriber is connected, `emit()` SHALL serialize each log record to JSON with fields `level` (string), `name` (logger name), `msg` (formatted message), and `ts` (ISO 8601 timestamp), and push it to all subscriber queues via `call_soon_threadsafe`. When `browser_logs` is disabled or no subscribers exist, `emit()` SHALL return immediately with no work. Each subscriber queue SHALL have a `maxsize` of 500; if a queue is full, the event SHALL be dropped silently.

#### Scenario: Log record streamed to browser
- **WHEN** `browser_logs` is `"on"` and a browser is connected to `/logs/stream` and a log record is emitted
- **THEN** the subscriber SHALL receive a JSON event with `level`, `name`, `msg`, and `ts` fields

#### Scenario: No subscribers connected
- **WHEN** `browser_logs` is `"on"` but no SSE clients are connected
- **THEN** `emit()` SHALL return immediately without serializing the record

#### Scenario: Browser logs disabled
- **WHEN** `browser_logs` is `"off"`
- **THEN** `emit()` SHALL return immediately regardless of subscriber count

#### Scenario: Queue full drops event
- **WHEN** a subscriber queue has 500 pending events
- **THEN** the new event SHALL be dropped and no error SHALL be raised

### Requirement: GET /logs/stream SSE endpoint
The daemon SHALL expose a `GET /logs/stream` endpoint that returns a `text/event-stream` response. On connection, the endpoint SHALL create an `asyncio.Queue(maxsize=500)`, append it to the subscriber list, and yield `data:` frames as log events arrive. On client disconnect, the queue SHALL be removed from the subscriber list. The endpoint SHALL return `503` if the daemon is not fully initialized.

#### Scenario: Browser connects and receives logs
- **WHEN** a browser opens an EventSource to `/logs/stream` and `browser_logs` is `"on"`
- **THEN** log events SHALL be streamed as `data: {json}\n\n` frames

#### Scenario: Browser disconnects
- **WHEN** the SSE client disconnects
- **THEN** the subscriber queue SHALL be removed from the list and no further events SHALL be queued for it

#### Scenario: Daemon not initialized
- **WHEN** `/logs/stream` is called before the daemon is fully started
- **THEN** the response SHALL be `503 Service Unavailable`

### Requirement: Frontend auto-connects EventSource for log stream
When the `browser-logs` setting is `"on"`, `App.vue` SHALL open an `EventSource` to `/logs/stream`. Each received event SHALL be dispatched to the browser console: DEBUG → `console.debug()`, INFO → `console.info()`, WARNING → `console.warn()`, ERROR/CRITICAL → `console.error()`. The log message SHALL be formatted as `[{name}] {msg}`. When the setting changes to `"off"` or the component unmounts, the EventSource SHALL be closed. The connection SHALL be reactive — toggling the setting SHALL connect/disconnect without a page refresh.

#### Scenario: Setting enabled triggers connection
- **WHEN** `browser-logs` is changed from `"off"` to `"on"` in the Settings UI
- **THEN** an EventSource to `/logs/stream` SHALL be opened automatically

#### Scenario: Setting disabled closes connection
- **WHEN** `browser-logs` is changed from `"on"` to `"off"`
- **THEN** the EventSource SHALL be closed immediately

#### Scenario: DEBUG record maps to console.debug
- **WHEN** a log event with `level: "DEBUG"` is received
- **THEN** it SHALL be printed via `console.debug("[{name}] {msg}")`

#### Scenario: WARNING record maps to console.warn
- **WHEN** a log event with `level: "WARNING"` is received
- **THEN** it SHALL be printed via `console.warn("[{name}] {msg}")`

#### Scenario: ERROR record maps to console.error
- **WHEN** a log event with `level: "ERROR"` is received
- **THEN** it SHALL be printed via `console.error("[{name}] {msg}")`
