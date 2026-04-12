## Context

Siphon's daemon (`siphon watch`) is a long-running FastAPI process that manages playlist syncs, downloads, and renames. Logging currently goes to stderr only, configured once at startup in `main()`. The `log_level` setting exists in the DB and is read at boot, but changing it requires a restart. Several modules (`registry.py`) have no logging at all. The SSE broadcast pattern (async queues + `call_soon_threadsafe`) is already proven in sync-events and job-stream endpoints.

## Goals / Non-Goals

**Goals:**
- Persist logs to a size-capped rolling file in `.data/`
- Stream logs to the browser console via SSE for live debugging
- Make log level changes take effect immediately (no daemon restart)
- Add comprehensive log coverage across all Python modules
- Provide a `browser-logs` toggle via Settings UI and CLI

**Non-Goals:**
- No log viewer UI — browser DevTools is the viewer
- No remote/centralized log aggregation
- No per-module log level control — single global level
- No log search or filtering API

## Decisions

### 1. RotatingFileHandler from stdlib

**Choice:** `logging.handlers.RotatingFileHandler` with `maxBytes=5*1024*1024`, `backupCount=1`.

**Alternatives considered:**
- *TimedRotatingFileHandler* — rotates by time, not size. Less predictable disk usage for a daemon that may be idle for hours then burst during syncs.
- *Single file with line truncation* — fragile, non-standard, requires custom code to seek/truncate.
- *Third-party (loguru, structlog)* — unnecessary dependency for what stdlib handles natively.

**Rationale:** Size-based rotation is predictable (10 MB max), battle-tested, zero dependencies. The file lives at `.data/siphon.log` alongside the DB.

### 2. SSELogHandler for browser streaming

**Choice:** A custom `logging.Handler` subclass that pushes formatted log records into a list of `asyncio.Queue` instances (one per SSE subscriber), using the existing `call_soon_threadsafe` pattern.

**Design:**
- Module-level `_log_queues: List[asyncio.Queue]` and `_log_loop: Optional[asyncio.AbstractEventLoop]` (mirrors `_sync_event_queues` / `_sync_loop`).
- `SSELogHandler.emit()` serializes the record to JSON (`{level, name, msg, timestamp}`) and pushes to all queues.
- If `browser_logs` setting is `"false"` or no subscribers exist, `emit()` short-circuits immediately — zero overhead.
- `GET /logs/stream` endpoint follows the sync-events pattern: create a queue, append to `_log_queues`, yield from it, remove on disconnect.

**Alternatives considered:**
- *WebSocket* — more complex (bidirectional not needed), SSE is already the established pattern.
- *Piggyback on sync-events stream* — mixes concerns, harder to toggle independently.

### 3. Live log-level propagation via settings handler

**Choice:** Extend `api_put_setting()` with a post-save hook. When `log_level` is written, call `logging.getLogger("siphon").setLevel()` inline. When `browser_logs` is written, no handler change needed — `SSELogHandler.emit()` reads the setting dynamically.

**Rationale:** No broadcast infrastructure needed. The logger is a process-global singleton. One line of code in the PUT handler.

### 4. Frontend auto-connect for log stream

**Choice:** `App.vue` watches the `browser-logs` setting reactively. When enabled, it opens an `EventSource` to `/logs/stream`. When disabled (or on unmount), it closes the connection. Log events are dispatched to `console[level.toLowerCase()]()`.

**Level mapping:**
| Python level | Browser method |
|---|---|
| DEBUG | `console.debug()` |
| INFO | `console.info()` |
| WARNING | `console.warn()` |
| ERROR, CRITICAL | `console.error()` |

### 5. Log format consistency

**Choice:** All handlers (stderr, file, SSE) use the same base information: timestamp, level, logger name, message. The file/stderr handlers use the existing text format. The SSE handler emits JSON for structured parsing in the browser.

## Risks / Trade-offs

- **[High-volume logging fills SSE buffer]** → `SSELogHandler.emit()` uses `put_nowait()` and catches `QueueFull`. If the browser can't keep up, old log events are dropped rather than blocking the logger. Queue maxsize should be bounded (e.g., 500 events).
- **[Log file I/O on hot path]** → `RotatingFileHandler` writes are synchronous but fast for line-sized writes. Not a concern at siphon's throughput. If it ever becomes one, `QueueHandler` + `QueueListener` is the stdlib escape hatch.
- **[Settings read in emit() hot path]** → `SSELogHandler.emit()` checks `browser_logs` setting per record. To avoid a DB read per log line, cache the value in a module-level variable and update it in the PUT handler alongside the logger level change.
- **[Rolling file loses old logs]** → By design. 10 MB total is the budget. Users who need more can adjust in a future change.
