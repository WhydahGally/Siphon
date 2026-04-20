## Context

`watcher.py` is a 2,577-line monolith containing data models, a job store, a playlist scheduler, ~40 FastAPI routes, ~15 CLI commands, SSE broadcasting, download orchestration, and the application entry point. All share 8 mutable module-level globals connected via the `global` keyword. Every feature change touches this file, and nothing can be imported or tested independently.

The entry point is currently `siphon.watcher:main` with the daemon started via `siphon watch`. The Dockerfile uses `CMD ["siphon", "watch"]`.

## Goals / Non-Goals

**Goals:**
- Split `watcher.py` into focused modules with clear single responsibilities
- Eliminate module-level mutable globals in favor of `app.state`
- Make each module independently importable and testable
- Rename entry point to `siphon.app:main` and daemon command to `siphon start`
- Zero functional changes — same behavior, same API surface, same CLI commands (except the rename)

**Non-Goals:**
- Adding tests (that's the next change, this unblocks it)
- Changing any API route paths or response shapes
- Refactoring the internals of any function being moved (move as-is, don't improve)
- Changing the scheduler, job store, or download logic

## Decisions

### 1. Module structure

Split into 6 new files + 2 existing file updates. No `helpers.py` — each utility goes where its type or sole caller lives.

| New module | Contents | Lines (approx) |
|---|---|---|
| `models.py` | `FailureRecord`, `JobItem`, `DownloadJob`, Pydantic request models | ~100 |
| `job_store.py` | `JobStore` class | ~250 |
| `scheduler.py` | `PlaylistScheduler` | ~200 |
| `api.py` | FastAPI `app`, lifespan, all routes, SSE handlers | ~700 |
| `cli.py` | All `cmd_*` functions, `_daemon_*` HTTP helpers, argparse config constants, `_parse_bool`, `_print_table` | ~650 |
| `app.py` | `main()`, logging setup, argparse dispatch, path constants, `__main__.py` one-liner | ~120 |

| Updated module | What moves in |
|---|---|
| `downloader.py` | `enumerate_entries`, `_filter_entries`, `download_parallel`, `_download_worker`, `_run_download_job`, `_fmt_size` |
| `formats.py` | `_build_options` (renamed to `build_options`) |
| `registry.py` | `_get_noise_patterns` (renamed to `get_noise_patterns`) |

**Why not a `helpers.py`?** Every utility has exactly one natural home. `_build_options` constructs a `DownloadOptions` — it belongs in `formats.py`. `_get_noise_patterns` reads from the registry — it belongs in `registry.py`. `_parse_bool` and `_print_table` are CLI-only. No orphans remain.

### 2. Daemon state via `app.state`

Replace the 8 module-level globals with attributes on FastAPI's built-in `app.state`, set in the lifespan:

```
Before (watcher.py):              After (api.py):
  _scheduler = None                 app.state.scheduler
  _job_store = None                 app.state.job_store
  _syncing_playlists = set()        app.state.syncing
  _sync_info = {}                   app.state.sync_info
  _sync_event_queues = []           app.state.sync_event_queues
  _sync_loop = None                 app.state.sync_loop
  _log_queues = []                  app.state.log_queues
  _browser_logs_enabled = False     app.state.browser_logs_enabled
```

Routes access state via `app.state.X` since `app` is module-level in `api.py`. No wrapper class, no dependency injection framework.

**Why not a separate `daemon_state.py` module?** `app.state` is idiomatic FastAPI and already exists. A separate module would be reinventing the same pattern with extra imports.

### 3. Entry point rename

- `pyproject.toml`: `siphon = "siphon.app:main"`
- CLI: `siphon start` replaces `siphon watch`
- Dockerfile `CMD`: `["siphon", "start"]`
- Add `src/siphon/__main__.py`: `from siphon.app import main; main()`

### 4. Download orchestration merges into `downloader.py`

Functions moving from `watcher.py` into `downloader.py`:
- `enumerate_entries()` — playlist enumeration via yt-dlp
- `_filter_entries()` — skip downloaded/ignored/max-failed items
- `_download_worker()` — single-item download + rename + record
- `download_parallel()` — thread pool orchestration (used by scheduler)
- `_run_download_job()` — thread pool orchestration with job store state updates (used by API)
- `_fmt_size()` — file size formatting (used only by `_download_worker`)

The combined `downloader.py` will be ~500 lines. One module owns everything download-related, from single-item to parallel orchestration.

**Why not keep them separate?** `engine.py` / `download.py` next to `downloader.py` creates naming confusion. The orchestration layer is just "call `download()` in a thread pool" — same concern, different level.

### 5. Sync event broadcasting

`_broadcast_sync_event` and `_sync_parallel` currently reach for globals (`_sync_event_queues`, `_syncing_playlists`, `_sync_info`). After the split:

- `_broadcast_sync_event` stays in `api.py` (it writes to `app.state.sync_event_queues`)
- `_sync_parallel` moves to `downloader.py` but takes a **callbacks dict** for sync events instead of reaching for globals:

```python
# downloader.py
def sync_parallel(..., on_sync_start=None, on_sync_end=None, on_new_item=None):

# api.py — passes callbacks that update app.state
def _make_sync_callbacks():
    return {
        "on_sync_start": lambda pid: ...,   # updates app.state.syncing
        "on_sync_end": lambda pid: ...,     # broadcasts SSE
    }
```

This keeps `downloader.py` free of FastAPI/asyncio dependencies.

### 6. Extraction order

Each step is independently deployable — the app works after every step:

```
Step 1: models.py            ← pure data, zero risk
Step 2: job_store.py          ← self-contained class
Step 3: formats.py + registry.py updates  ← move build_options, get_noise_patterns
Step 4: downloader.py expansion  ← merge orchestration in
Step 5: cli.py                ← independent HTTP clients
Step 6: scheduler.py          ← threading, depends on downloader + registry
Step 7: api.py                ← routes + lifespan + app.state migration
Step 8: app.py + __main__.py  ← entry point, glue
Step 9: delete watcher.py + update Dockerfile/pyproject.toml
```

## Risks / Trade-offs

**[Large diff]** → This is a move-only refactor. Each step can be reviewed independently. No logic changes reduce the risk of behavioral regressions.

**[Import cycles]** → The dependency graph is strictly layered (models → job_store → downloader → scheduler → api → app). No cycles by construction. `downloader.py` importing from `registry` is the only cross-cutting edge, and it already exists today.

**[`siphon watch` → `siphon start` breaking change]** → Users with existing scripts or muscle memory will need to update. Mitigated by: updating Dockerfile CMD, README, and Unraid template in the same change.

**[Static file mount side-effect]** → Currently `app.mount("/", StaticFiles(...))` runs at module import time (line 1873). After the split, this moves into `api.py` module level. Same behavior, just in a different file. No risk.
