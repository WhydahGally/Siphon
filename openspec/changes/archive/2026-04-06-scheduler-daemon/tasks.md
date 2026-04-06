## 1. Dependencies & Project Setup

- [x] 1.1 Add `fastapi`, `uvicorn[standard]` to `requirements.txt` and `pyproject.toml`
- [x] 1.2 Add `Dockerfile` with `CMD ["siphon", "watch"]` and `EXPOSE 8000`

## 2. Registry — Schema & Helpers

- [x] 2.1 Add `watched INTEGER NOT NULL DEFAULT 1` and `check_interval_secs INTEGER NULL` columns to `_SCHEMA` in `registry.py`
- [x] 2.2 Add `ALTER TABLE` migration statements for both columns in `init_db()` (safe for existing DBs)
- [x] 2.3 Update `add_playlist()` signature to accept `watched` and `check_interval_secs` parameters
- [x] 2.4 Add `get_watched_playlists()` returning rows where `watched=1`
- [x] 2.5 Add `set_playlist_watched(playlist_id, watched: bool)`
- [x] 2.6 Add `set_playlist_interval(playlist_id, interval_secs: int | None)`
- [x] 2.7 Add `check-interval` as a recognised key in the settings validation list

## 3. PlaylistScheduler (watcher.py — dedicated section)

- [x] 3.1 Implement `PlaylistScheduler.__init__()` — reads watched playlists from DB, builds timer dict
- [x] 3.2 Implement `PlaylistScheduler.start()` — arms one `threading.Timer` per playlist
- [x] 3.3 Implement `PlaylistScheduler._resolve_interval(playlist_row)` — applies precedence chain (per-playlist → global → 86400)
- [x] 3.4 Implement `PlaylistScheduler._fire(playlist_id)` — calls `_sync_parallel`, then `_rearm`
- [x] 3.5 Implement `PlaylistScheduler._rearm(playlist_id)` — re-reads interval from DB, arms new timer
- [x] 3.6 Implement `PlaylistScheduler.add_playlist(playlist_id)` — arms new timer for newly registered playlist
- [x] 3.7 Implement `PlaylistScheduler.remove_playlist(playlist_id)` — cancels timer; no-op if not present
- [x] 3.8 Implement `PlaylistScheduler.reschedule_playlist(playlist_id)` — cancel + re-arm with fresh interval; cancel-only if `watched=0`
- [x] 3.9 Implement `PlaylistScheduler.stop()` — cancels all timers; joins any in-progress sync threads

## 4. FastAPI Daemon (watcher.py — dedicated section)

- [x] 4.1 Create FastAPI `app` instance with `lifespan` context manager: start scheduler on startup, call `scheduler.stop()` on shutdown
- [x] 4.2 Implement `POST /playlists` — validate URL, call `registry.add_playlist()`, call `scheduler.add_playlist()`, return 201
- [x] 4.3 Implement `GET /playlists` — return all playlists as JSON array
- [x] 4.4 Implement `GET /playlists/{playlist_id}` — return single playlist or 404
- [x] 4.5 Implement `DELETE /playlists/{playlist_id}` — delete from DB, call `scheduler.remove_playlist()`, return 204
- [x] 4.6 Implement `PATCH /playlists/{playlist_id}` — update DB (watched, interval), call `scheduler.reschedule_playlist()`, return 200
- [x] 4.7 Implement `POST /playlists/{playlist_id}/sync` — dispatch `_sync_parallel` in a background thread, return 202
- [x] 4.8 Implement `POST /playlists/{playlist_id}/sync-failed` — dispatch sync-failed in a background thread, return 202
- [x] 4.9 Implement `GET /settings` — return all settings key-value pairs
- [x] 4.10 Implement `GET /settings/{key}` — return single setting or null value
- [x] 4.11 Implement `PUT /settings/{key}` — validate key, upsert value, return 200; return 400 for unknown key
- [x] 4.12 Implement `GET /health` — return `{"status": "ok", "watched_playlists": <count>}`
- [x] 4.13 Implement `cmd_watch()` — initialise DB, create `PlaylistScheduler`, start uvicorn

## 5. CLI — Refactor Subcommands as HTTP Clients

- [x] 5.1 Create a shared `_daemon_client()` helper that makes HTTP requests to `http://localhost:8000` and handles connection errors (printing the "not running" message and exiting non-zero on `ConnectionRefusedError`)
- [x] 5.2 Refactor `cmd_add()` as HTTP client: POST /playlists; add `--no-watch` and `--interval` argument parsing
- [x] 5.3 Refactor `cmd_list()` as HTTP client: GET /playlists; render as table
- [x] 5.4 Refactor `cmd_sync()` as HTTP client: POST /playlists/{id}/sync (all or named)
- [x] 5.5 Refactor `cmd_sync_failed()` as HTTP client: POST /playlists/{id}/sync-failed
- [x] 5.6 Refactor `cmd_delete()` as HTTP client: DELETE /playlists/{id}
- [x] 5.7 Refactor `cmd_config()` as HTTP client: GET or PUT /settings/{key}; add `check-interval` to valid keys list and docstring
- [x] 5.8 Register `watch` subcommand in the argparse entry point; update module docstring with new CLI usage

## 6. Documentation & Validation

- [x] 6.1 Update `watcher.py` module docstring to reflect new CLI shape: `siphon watch`, updated `add` flags, `check-interval` config key, daemon prerequisite note
- [x] 6.2 Verify `GET /docs` (Swagger UI) renders correctly with all endpoints
- [x] 6.3 Verify migration is safe: run `siphon watch` against an existing `.data/siphon.db` and confirm playlists retain all data with `watched=1` defaults
