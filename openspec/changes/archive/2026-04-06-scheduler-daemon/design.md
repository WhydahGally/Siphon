## Context

Siphon currently operates as a pure CLI tool: every `siphon` subcommand spawns a
short-lived OS process, performs work, and exits. This design is simple but
creates a fundamental obstacle for automatic scheduling: a long-running scheduler
daemon and short-lived CLI processes are separate OS processes with no shared
memory. Any config change written to the DB by `siphon config` is invisible to
the daemon without an IPC bridge (PID files, Unix sockets, OS signals, or a
polling tick). All of these add complexity, fragility, or violate the requirement
for a dormant scheduler.

The resolution is to invert the architecture: `siphon watch` becomes the
long-lived daemon that owns all mutable state (DB connection, scheduler). All
other subcommands become thin HTTP clients that call the daemon's REST API. There
is no IPC problem because there is only one process that mutates state.

This also directly enables a future web UI: the UI is just another HTTP client
of the same API, with no special integration work needed.

## Goals / Non-Goals

**Goals:**
- `siphon watch` starts a FastAPI daemon that exposes REST endpoints for all
  playlist and settings operations
- A `PlaylistScheduler` class manages per-playlist `threading.Timer` instances
  with fire-sync-rearm lifecycle; no polling ticks; dormant between syncs
- All `siphon` subcommands (other than `watch`) work as thin HTTP clients against
  the running daemon
- Per-playlist configurable check intervals, with a global fallback default
- `siphon add` gains `--no-watch` and `--interval` flags
- Graceful SIGTERM shutdown: wait for any in-progress sync to complete
- Lay the groundwork for a future web UI (API contract, OpenAPI spec)

**Non-Goals:**
- Building the web UI (separate future change)
- API authentication (documented as out of scope; reverse-proxy guidance in README)
- Exposing the scheduler over a separate control port or management API
- Container auto-restart on config change — the daemon handles in-process updates
- Supporting `siphon` commands when the daemon is not running (error and exit)

## Decisions

### Decision: FastAPI + uvicorn as the API framework

**Chosen**: FastAPI with uvicorn[standard]

**Alternatives considered**:
- `http.server` (stdlib): No routing, no request parsing, no response models.
  Would require significant boilerplate for a correct implementation.
- Flask: Mature, minimal, synchronous. Viable but no auto-generated OpenAPI spec.
  The future UI story is weaker without a machine-readable contract.
- FastAPI: Auto-generates OpenAPI spec at `/docs`. Async-native (works well with
  background threads for downloads). Pydantic request/response models. De-facto
  standard for this class of Python service.

FastAPI's dependency cost (pydantic, starlette, uvicorn) is justified by the
OpenAPI spec alone — when the UI is built, the contract already exists.

---

### Decision: threading.Timer with fire-sync-rearm (not APScheduler)

**Chosen**: stdlib `threading.Timer`, one per watched playlist, rearmed after
each sync completes.

**Alternatives considered**:
- APScheduler: Feature-rich (cron syntax, missed job policies, persistence).
  Adds a dependency and complexity for a use case that is fully covered by a
  one-shot timer rearmed in a loop.
- `asyncio` event loop with `loop.call_later`: Requires the entire scheduler to
  run in an async context. yt-dlp and the existing sync logic are synchronous.
  Mixing async/sync correctly requires `run_in_executor` throughout — over-
  engineering for one timer per playlist.
- Periodic tick (`while True: sleep(30); check_overdue()`): Violates the
  requirement for a dormant scheduler. Wakes the CPU every 30 seconds for no
  functional reason.

`threading.Timer` fires exactly once at the right time, then the rearm logic
schedules the next fire after the sync completes. No ticks. No wasted wakeups.
Under the hood `threading.Timer` is a `threading.Thread` that sleeps for the
given interval — exactly the dormancy model required.

The fire-sync-rearm model means: if a sync takes longer than the configured
interval, the next timer is armed *after* the sync finishes, not at a fixed wall-
clock cadence. This prevents concurrent syncs for the same playlist.

---

### Decision: CLI as thin HTTP clients (daemon required as prerequisite)

**Chosen**: All subcommands other than `watch` make HTTP requests to
`http://localhost:8000`; exit with an error if the daemon is not reachable.

**Alternatives considered**:
- Soft fallback (write directly to DB if daemon not running): Splits the business
  logic between two code paths. Newly added playlists written directly to DB are
  never picked up by the scheduler without a restart or a notification mechanism —
  reintroducing the IPC problem.
- Keep CLI self-sufficient, add polling tick on daemon: Violates the no-tick
  requirement and adds the IPC mechanism we designed to avoid.

The daemon-as-prerequisite model (Flavor 1) is consistent with the *arr ecosystem
and the intended deployment: `siphon watch` is the container's `CMD`. The CLI
subcommands are debugging/management tools, not standalone programs.

---

### Decision: Port 8000 hardcoded internally; host port mapped via Docker -p

**Chosen**: Daemon always binds `0.0.0.0:8000` inside the container. Unraid and
other Docker hosts map the host port at deploy time via `-p <host>:8000`.

**Alternatives considered**:
- `SIPHON_PORT` env var: Only needed if the *internal* port must be configurable,
  which it doesn't — Docker port mapping makes the host port irrelevant to the
  container internals. Adding an env var adds a configuration surface with no
  practical benefit for the intended deployment environments.

This matches the pattern of every Linuxserver.io container app: fixed internal
port, user-configurable host port in the Unraid template.

---

### Decision: PlaylistScheduler in its own section of watcher.py

**Chosen**: Add a clearly delimited `# --- PlaylistScheduler ---` section to
`watcher.py` rather than a new `scheduler.py` module.

**Alternatives considered**:
- Separate `scheduler.py` module: Clean seam, but `PlaylistScheduler` only calls
  `_sync_parallel` from `watcher.py`. A separate module would either import from
  `watcher` (circular risk) or require moving `_sync_parallel` out.
- Keep everything flat in `watcher.py`: The file is already 772 lines. A clearly
  labelled section adds ~150 lines but preserves co-location of all watch logic.

The section approach keeps related code together and avoids a cross-module import
between two files that are tightly coupled by design.

## Risks / Trade-offs

**[Risk] uvicorn blocks main thread, scheduler runs in background threads**
→ Mitigation: Start `PlaylistScheduler` before `uvicorn.run()`. uvicorn's SIGTERM
handler shuts down the HTTP server; add a FastAPI `lifespan` context manager to
call `scheduler.stop()` on shutdown. The scheduler's `stop()` method cancels
pending timers and waits for any in-progress sync thread to complete.

**[Risk] Sync blocks a timer thread for a long time; thread pool exhaustion**
→ Mitigation: Each `threading.Timer` spawns one thread per playlist. For typical
use (daily interval, <10 playlists) the thread count is trivially small. This is
not a concern at the intended scale.

**[Risk] SQLite write contention between API requests and scheduler sync threads**
→ Mitigation: Already handled. WAL mode + `busy_timeout = 3000` on per-thread
connections is the existing pattern in `registry.py`. No new risk introduced.

**[Risk] Daemon not running when user types `siphon add`**
→ Mitigation: CLI prints a clear error: "siphon watch is not running. Start it
with 'siphon watch' or 'docker start <container>'." and exits non-zero.

**[Risk] Stale scheduler state if DB is modified externally (e.g. direct SQLite edit)**
→ Accepted trade-off. The system is not designed for external DB modification.
A container restart clears any inconsistency.

## Migration Plan

1. **Schema migration**: `registry.init_db()` adds the new columns via `ALTER
   TABLE ... ADD COLUMN IF NOT EXISTS` migrations (same pattern as existing
   migration block). Safe to run against existing DBs — new columns default to
   watched=1, check_interval_secs=NULL.

2. **Existing playlists**: Existing registered playlists automatically gain
   `watched=1` (all watched by default). Users who want to opt a playlist out of
   auto-sync can run `siphon config <name> no-watch` after migrating.

3. **Dockerfile update**: `CMD` changes from `siphon sync` (or manual invocation)
   to `siphon watch`. Port 8000 added to `EXPOSE`.

4. **Rollback**: The schema migration is additive (new columns only). Rolling back
   to a pre-daemon version of the code leaves the new columns inert — the old CLI
   code ignores them. No data loss.

## Open Questions

- Should `GET /status` (daemon health + scheduler state) be part of this change,
  or deferred to the UI change? Useful for debugging and for Unraid's container
  health check. Recommend including a minimal `/health` endpoint in this change.
