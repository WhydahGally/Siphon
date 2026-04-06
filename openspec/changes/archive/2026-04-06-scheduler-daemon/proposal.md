## Why

Siphon can watch playlists and download new items, but syncing only happens when
the user manually runs `siphon sync`. To fulfil its core purpose as a 24x7
container service, syncing must trigger automatically on a configurable schedule
without any human intervention.

A pure CLI approach cannot support this elegantly: a long-running scheduler
daemon and short-lived config commands are separate OS processes with no shared
memory, making config propagation require filesystem-based IPC (PID files,
sockets) or a polling tick — both undesirable. The clean solution is to
restructure Siphon so that `siphon watch` is a long-running FastAPI daemon that
owns all state, and every other command becomes a thin HTTP client talking to it.
This also lays the foundation for a future web UI.

## What Changes

- **NEW**: `siphon watch` starts a long-running FastAPI daemon on port 8000
  (internal, fixed) that owns the DB connection, the scheduler, and exposes a
  REST API for all operations
- **NEW**: A `PlaylistScheduler` class (own section in `watcher.py`) manages one
  `threading.Timer` per watched playlist using a fire-sync-rearm model; no
  periodic ticks; dormant between syncs
- **NEW**: `siphon add` and all other subcommands become thin HTTP clients that
  POST/PATCH/GET/DELETE against the running daemon; the daemon is a prerequisite
  for all commands
- **NEW**: `siphon add` gains `--no-watch` flag (opt out of automatic scheduling)
  and `--interval <seconds>` flag (per-playlist schedule override)
- **MODIFIED**: `playlist-registry` — `playlists` table gains `watched` (INTEGER,
  default 1) and `check_interval_secs` (INTEGER, nullable) columns; `settings`
  table gains `check-interval` key (global default interval, default 86400)
- **MODIFIED**: `playlist-watcher-cli` — adds `watch` subcommand; updates `add`
  and `config` subcommands with new flags and daemon-client behaviour;
  `siphon sync` and `siphon sync-failed` become manual trigger endpoints on the
  daemon (still callable from CLI as thin clients)
- **BREAKING**: Running any `siphon` subcommand other than `watch` requires the
  daemon to be running; commands will exit with an error if the daemon is not
  reachable

## Capabilities

### New Capabilities

- `siphon-daemon`: FastAPI application served by uvicorn, bound to
  `0.0.0.0:8000` (internal container port, mapped externally via Docker `-p`).
  Exposes REST endpoints for all playlist and settings operations. Owns the DB
  connection and the scheduler instance. Handles graceful shutdown on SIGTERM
  (waits for any in-progress sync to complete before exiting).

- `playlist-scheduler`: `PlaylistScheduler` class that reads all watched
  playlists from the DB on startup, arms one `threading.Timer` per playlist, and
  uses a fire-sync-rearm model (timer fires → sync runs → new timer armed with
  interval re-read from DB). No periodic ticks. Per-playlist interval
  (`check_interval_secs`) takes precedence over global `check-interval` setting;
  falls back to global; falls back to 86400s. Scheduler is instantiated once at
  daemon startup; adding or modifying playlists via the API updates the scheduler
  in-process with no restart required.

### Modified Capabilities

- `playlist-registry`: Schema change — add `watched` and `check_interval_secs`
  columns to `playlists` table; add `check-interval` as a valid settings key.

- `playlist-watcher-cli`: New `watch` subcommand; `siphon add` gains `--no-watch`
  and `--interval` flags; all subcommands refactored to HTTP clients; daemon
  required as prerequisite for non-`watch` commands.

## Impact

- **New dependencies**: `fastapi`, `uvicorn[standard]`, `pydantic` (pulled in by
  FastAPI) added to `requirements.txt` and `pyproject.toml`
- **`src/siphon/watcher.py`**: Major refactor — CLI `cmd_*` functions become HTTP
  client wrappers; `PlaylistScheduler` added in its own section; `cmd_watch`
  replaced by daemon startup logic
- **`src/siphon/registry.py`**: Schema migration for new columns; new query
  functions (`get_watched_playlists`, `set_playlist_watched`,
  `set_playlist_interval`)
- **Docker**: Container `CMD` changes to `siphon watch`; port 8000 exposed in
  `Dockerfile`; Unraid template maps host port (user-configurable) → container
  8000
- **No auth**: Consistent with *arr ecosystem precedent for home-server
  containers; README documents reverse-proxy guidance for external exposure
