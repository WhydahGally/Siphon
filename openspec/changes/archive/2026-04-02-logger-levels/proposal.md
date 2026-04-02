## Why

After the playlist-watcher CLI was built, three operational gaps were discovered:
YouTube's JS challenge warnings appeared on every download because yt-dlp defaulted to Deno (not installed); download progress was invisible in the terminal; and there was no way to control how much logging detail the CLI produced.

## What Changes

- Bake `node` as the primary JS runtime and `ejs:github` as the challenge solver script into the yt-dlp options so YouTube signature and n-parameter challenge solving works out of the box with Node.js (already present on most dev machines and in standard Linux container images).
- Add a live per-file download progress line to the CLI that overwrites itself and prints a checkmark on completion.
- Add a `log-level` config key (`DEBUG` / `INFO` / `WARNING` / `ERROR`) that is stored in the DB and applied at startup on every invocation. Default when unset: `INFO`.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `download-engine`: JS runtime and remote component solver are now explicitly configured rather than left to yt-dlp defaults.
- `playlist-watcher-cli`: CLI now shows live download progress per file, and the `siphon config` subcommand gains a `log-level` key that controls logging verbosity persistently.

## Impact

- `src/siphon/downloader.py` — `_build_ydl_opts` gains `js_runtimes` and `remote_components` keys.
- `src/siphon/watcher.py` — adds `_make_cli_progress_callback()`, wires it into `_download_with_archive`, adds `log-level` to `_KNOWN_KEYS`, and reads the setting from the DB in `main()`.
- No new dependencies; Node.js is a system-level requirement (not a Python package).
