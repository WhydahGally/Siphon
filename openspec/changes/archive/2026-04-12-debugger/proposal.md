## Why

Siphon currently logs only to stderr with no persistence. When something goes wrong in the daemon (a silent yt-dlp skip, a MusicBrainz timeout cascade, a failed migration), the only evidence is whatever scrolled past in the terminal. Several modules (`registry.py`) have zero logging. There is no way to stream logs to the browser for live debugging, and changing the log level requires a daemon restart. This change adds a proper logging pipeline: rolling file persistence, comprehensive log coverage across all modules, browser console streaming via SSE, and live log-level control.

## What Changes

- Add a `RotatingFileHandler` to the daemon's logging setup — 5 MB max, 1 backup copy, written to the `.data/` directory alongside the DB.
- Add a `browser-logs` setting (on/off toggle in Settings UI + `siphon config browser-logs on/off` CLI command) that controls whether logs are streamed to the browser.
- Add a `GET /logs/stream` SSE endpoint that streams log records to connected browsers. A custom `SSELogHandler` pushes log records into subscriber queues using the existing `call_soon_threadsafe` pattern.
- The frontend auto-connects/disconnects the EventSource based on the `browser-logs` setting and pipes events to `console.debug()` / `console.info()` / `console.warn()` / `console.error()`.
- Make `PUT /settings/log-level` apply the new level to the running daemon immediately (no restart required). Same for `browser-logs` toggle.
- Add INFO/DEBUG/WARN logging throughout the codebase where currently missing — covering `registry.py` (DB init, migrations, connections), `downloader.py` (entry/exit, format selection, silent skips), `renamer.py` (MB HTTP requests, rate-limit waits, noise stripping), and `watcher.py` (API requests, SSE connections, scheduler lifecycle, settings changes).
- Update the `/info` endpoint to include a `logs_dir` field (same as `db_dir`) and update the browser console message to say "DB & logs directory".

## Capabilities

### New Capabilities
- `rolling-log-file`: RotatingFileHandler setup — 5 MB max, 1 backup, `.data/siphon.log`
- `browser-log-stream`: SSE endpoint (`GET /logs/stream`), custom SSELogHandler, frontend EventSource subscription with auto-connect, `browser-logs` setting + CLI command
- `codebase-logging`: Add missing log statements across all siphon modules at appropriate levels

### Modified Capabilities
- `global-config-keys`: Add `browser-logs` key (on/off) to `_KNOWN_KEYS` and `_ALLOWED_VALUES`
- `settings-ui`: Add browser logs toggle to the Settings page
- `siphon-daemon`: Live log-level and browser-logs propagation in `api_put_setting()`; `/info` response includes `logs_dir`

## Impact

- **Backend**: `watcher.py` (logging setup in `main()`, new SSE endpoint, settings handler side-effects), `registry.py` (add logger), `downloader.py` (add log statements), `renamer.py` (add log statements)
- **Frontend**: `App.vue` (EventSource for log stream, updated console message), `Settings.vue` (browser-logs toggle), `useSettings.js` (preload new key)
- **CLI**: `siphon config browser-logs on/off` — follows existing config pattern
- **Disk**: Up to 10 MB additional in `.data/` (active log + 1 backup)
- **Dependencies**: None — uses Python stdlib `logging.handlers.RotatingFileHandler`
