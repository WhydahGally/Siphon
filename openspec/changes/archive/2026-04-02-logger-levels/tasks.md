## 1. yt-dlp JS runtime configuration

- [x] 1.1 Add `js_runtimes: {"node": {}, "deno": {}}` to `_build_ydl_opts` in `downloader.py`
- [x] 1.2 Add `remote_components: ["ejs:github"]` to `_build_ydl_opts` in `downloader.py`
- [x] 1.3 Verify the correct runtime key is `"node"` (not `"nodejs"`) against yt-dlp supported runtimes
- [x] 1.4 Mirror the same `js_runtimes` and `remote_components` keys in `_download_with_archive` in `watcher.py`

## 2. CLI progress display

- [x] 2.1 Implement `_make_cli_progress_callback()` factory in `watcher.py`
- [x] 2.2 Handle `downloading` status: print `\r`-overwriting line with filename, %, bytes, speed, ETA
- [x] 2.3 Handle `finished` status: print checkmark line with newline
- [x] 2.4 Handle unknown total size: omit percentage and ETA gracefully
- [x] 2.5 Wire `_make_cli_progress_callback()` into `_download_with_archive` via `_make_hook`

## 3. Configurable log level

- [x] 3.1 Add `"log-level"` entry to `_KNOWN_KEYS` in `watcher.py` with `db_key = "log_level"`
- [x] 3.2 Add `_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}`
- [x] 3.3 Validate value in `cmd_config` at write time; reject invalid values with error message and non-zero exit
- [x] 3.4 Upper-case the value before persisting so DB always stores canonical form
- [x] 3.5 In `main()`, read `log_level` from DB and apply to `logging.getLogger("siphon")` before dispatch
- [x] 3.6 Wrap the DB read in `try/except RuntimeError` so fresh installs fall back to `INFO` without error
