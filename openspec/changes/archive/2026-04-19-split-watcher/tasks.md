## 1. Extract pure data types

- [x] 1.1 Create `models.py` with `FailureRecord`, `JobItem`, `DownloadJob` dataclasses and Pydantic request models (`PlaylistCreate`, `PlaylistPatch`, `SettingWrite`, `JobCreate`, `RenameRequest`)
- [x] 1.2 Update `watcher.py` imports to use `models.py`
- [x] 1.3 Verify daemon starts and CLI works

## 2. Extract JobStore

- [x] 2.1 Create `job_store.py` with the `JobStore` class (imports from `models`)
- [x] 2.2 Update `watcher.py` imports to use `job_store.py`
- [x] 2.3 Verify daemon starts and job creation/SSE streaming works

## 3. Move utilities to their natural homes

- [x] 3.1 Move `_build_options` into `formats.py` as `build_options`
- [x] 3.2 Move `_get_noise_patterns` into `registry.py` as `get_noise_patterns`
- [x] 3.3 Update all call sites in `watcher.py`
- [x] 3.4 Verify daemon starts

## 4. Expand downloader.py with orchestration

- [x] 4.1 Move `enumerate_entries`, `_filter_entries`, `_fmt_size`, `_download_worker`, `download_parallel`, `_run_download_job`, `_sync_parallel`, `_run_sync_failed_for_playlist` into `downloader.py`
- [x] 4.2 Add sync-event callbacks parameter to `_sync_parallel` (replace direct global access with callbacks passed by caller)
- [x] 4.3 Update all call sites in `watcher.py`
- [x] 4.4 Verify daemon starts, sync works, and job downloads work

## 5. Extract CLI

- [x] 5.1 Create `cli.py` with all `cmd_*` functions (except `cmd_watch`), `_daemon_get/post/delete/patch/put`, `_daemon_handle_error`, `_parse_bool`, `_print_table`, argparse config constants (`_KNOWN_KEYS`, `_VALID_LOG_LEVELS`, `_ALLOWED_VALUES`, `_PLAYLIST_KNOWN_KEYS`)
- [x] 5.2 Update `watcher.py` to import CLI commands from `cli.py`
- [x] 5.3 Verify all CLI commands work (`siphon list`, `siphon sync`, `siphon config`, etc.)

## 6. Extract scheduler

- [x] 6.1 Create `scheduler.py` with `PlaylistScheduler` class (imports from `registry`, `downloader`, `formats`)
- [x] 6.2 Update `watcher.py` imports
- [x] 6.3 Verify scheduler fires and rearms correctly

## 7. Extract API routes and migrate to app.state

- [x] 7.1 Create `api.py` with FastAPI `app`, lifespan, middleware, all `api_*` route functions, `_SSELogHandler`, `_broadcast_sync_event`, `_playlist_to_dict`, `_job_to_dict`, `_normalise_youtube_url`, static file mount
- [x] 7.2 Replace 8 module-level globals with `app.state` attributes set in lifespan
- [x] 7.3 Update all route functions to read from `app.state` instead of globals
- [x] 7.4 Verify all API routes work (add playlist, sync, jobs, SSE streams, settings)

## 8. Create entry point and finalize

- [x] 8.1 Create `app.py` with `main()`, logging setup, argparse dispatch, path constants (`DATA_DIR`, `DEFAULT_OUTPUT_DIR`)
- [x] 8.2 Rename `cmd_watch` to `cmd_start` in `app.py`; update argparse subcommand from `watch` to `start`
- [x] 8.3 Create `__main__.py` (`from siphon.app import main; main()`)
- [x] 8.4 Update `pyproject.toml` entry point to `siphon = "siphon.app:main"`
- [x] 8.5 Delete `watcher.py`
- [x] 8.6 Update Dockerfile `CMD` from `["siphon", "watch"]` to `["siphon", "start"]`
- [x] 8.7 Update README references from `siphon watch` to `siphon start`
- [x] 8.8 Verify full flow: `siphon start` launches daemon, CLI commands work, UI serves correctly
