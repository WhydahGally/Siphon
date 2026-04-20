## Why

`watcher.py` is 2,577 lines containing five unrelated concerns: data models, job store, scheduler, ~40 FastAPI API routes, and ~15 CLI commands. Every change touches this file, debugging requires scrolling through thousands of lines, and nothing can be imported or tested in isolation. It's the single biggest maintenance bottleneck in the project.

## What Changes

- Split `watcher.py` into focused modules: `models.py`, `job_store.py`, `scheduler.py`, `api.py`, `cli.py`, `app.py`
- Merge download orchestration functions (`enumerate_entries`, `_filter_entries`, `download_parallel`, `_run_download_job`, `_download_worker`) into the existing `downloader.py`
- Move `_build_options` into `formats.py` and `_get_noise_patterns` into `registry.py` — utilities placed next to the types they operate on
- Replace 8 module-level mutable globals (`_scheduler`, `_job_store`, `_syncing_playlists`, etc.) with `app.state` attributes set in the FastAPI lifespan
- Resolve path constants (`DATA_DIR`, `DEFAULT_OUTPUT_DIR`) once at module level in `app.py` instead of calling helper functions from 15 call sites
- **BREAKING**: Rename entry point from `siphon.watcher:main` to `siphon.app:main`
- **BREAKING**: Rename `siphon watch` CLI command to `siphon start`
- Add `__main__.py` so `python -m siphon` works
- Delete `watcher.py` after extraction is complete

## Capabilities

### New Capabilities

_None — this is a refactor, not new functionality._

### Modified Capabilities

- `siphon-daemon`: Entry point changes from `siphon watch` to `siphon start`; module path changes from `siphon.watcher:main` to `siphon.app:main`

## Impact

- **Code**: Every import of `siphon.watcher` across the project changes. The UI references `siphon watch` in docs/tooltips if any.
- **Deployment**: `pyproject.toml` entry point changes. Docker `entrypoint.sh` may reference `siphon watch`. Unraid template may reference it.
- **Dependencies**: No new dependencies added or removed.
- **Behavior**: Zero functional changes — same CLI commands, same API routes, same daemon behavior. Only the `watch` → `start` rename is user-visible.
