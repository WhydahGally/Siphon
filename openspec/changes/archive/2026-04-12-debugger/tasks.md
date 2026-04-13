## 1. Rolling Log File

- [x] 1.1 Add `RotatingFileHandler` to `main()` in `watcher.py` — `.data/siphon.log`, 5 MB max, 1 backup, same format as stderr handler
- [x] 1.2 Update `/info` endpoint to include `logs_dir` field (same value as `db_dir`)
- [x] 1.3 Update `App.vue` console message from "DB directory" to "DB & logs directory"

## 2. Browser Log Stream (Backend)

- [x] 2.1 Add module-level `_log_queues`, `_log_loop` variables in `watcher.py` (mirror sync-events pattern)
- [x] 2.2 Implement `SSELogHandler(logging.Handler)` — serialize record to JSON, push to subscriber queues via `call_soon_threadsafe`, short-circuit when disabled or no subscribers, respect `maxsize=500`
- [x] 2.3 Attach `SSELogHandler` to `siphon` logger in `main()`
- [x] 2.4 Add `GET /logs/stream` SSE endpoint — create queue, append to subscribers, yield frames, cleanup on disconnect

## 3. Browser Log Stream (Frontend)

- [x] 3.1 Add reactive EventSource in `App.vue` — watch `browser-logs` setting, auto-connect/disconnect, pipe events to `console[level]()`

## 4. Browser Logs Setting

- [x] 4.1 Add `browser-logs` to `_KNOWN_KEYS` and `_ALLOWED_VALUES` in `watcher.py` (on/off)
- [x] 4.2 Preload `browser-logs` in `useSettings.js`
- [x] 4.3 Add browser logs toggle to Settings page in a new Debugging section (between Appearance and About)

## 5. Live Settings Propagation

- [x] 5.1 In `api_put_setting()`, add post-save hook: when `log_level` changes, call `logging.getLogger("siphon").setLevel()` immediately
- [x] 5.2 In `api_put_setting()`, add post-save hook: when `browser_logs` changes, update the cached module-level flag immediately

## 6. Codebase Logging — registry.py

- [x] 6.1 Add `logger = logging.getLogger(__name__)` and log DB init (INFO), migrations (DEBUG), new connections (DEBUG), playlist add/remove (INFO), setting updates (DEBUG)

## 7. Codebase Logging — downloader.py

- [x] 7.1 Add INFO logs for `download()` entry/exit, DEBUG for format selector and postprocessor chain, WARNING for yt-dlp silent skips

## 8. Codebase Logging — renamer.py

- [x] 8.1 Add DEBUG logs for MusicBrainz HTTP request (query, status, latency), rate-limit waits, and noise pattern stripping (before/after)

## 9. Codebase Logging — watcher.py

- [x] 9.1 Add DEBUG logging for API request handling (method + path) via middleware or per-route
- [x] 9.2 Add DEBUG logging for SSE client connect/disconnect on all stream endpoints
- [x] 9.3 Add INFO logging for scheduler thread start/stop and INFO for settings changes via API
- [x] 9.4 Add DEBUG logging for per-item sync start
