## Context

yt-dlp defaults to Deno as its only JS runtime for YouTube challenge solving. Deno is not a standard system package on Linux and is uncommon on developer machines. As a result, every download session emitted four warnings about missing runtimes and solver scripts, signature solving failures, and n-parameter throttling failures — all of which can degrade format availability and download speed.

Separately, when the playlist-watcher CLI was built it passed `None` as the progress callback in `_download_with_archive`, so no download progress was ever printed. The root logging level was also set to `WARNING` everywhere with no way to raise it for debugging.

## Goals / Non-Goals

**Goals:**
- Silence the yt-dlp JS challenge warnings by explicitly configuring Node.js (available via `apt`/`brew`/nvm) as the primary runtime and fetching the EJS solver script from GitHub on first run.
- Restore visible download progress in the CLI without introducing a dependency on a third-party progress library.
- Allow persistent, per-install control of log verbosity via `siphon config log-level`.

**Non-Goals:**
- Bundling or vendoring the EJS solver script inside the repo (would require update maintenance).
- Supporting Bun or QuickJS runtimes (they are valid yt-dlp values but unnecessary complexity here).
- Per-command log-level overrides via CLI flags.

## Decisions

### 1. Node.js over Deno as primary runtime
yt-dlp supports `deno`, `node`, `bun`, and `quickjs`. Node.js ships in every major Linux container base image (`apt-get install nodejs`) and is managed via nvm on most dev machines. Deno requires a separate install. The `js_runtimes` dict is ordered — `node` is tried first, `deno` is kept as a fallback for environments that happen to have it.

### 2. `remote_components: ["ejs:github"]` over `ejs:npm`
yt-dlp's own documentation recommends `ejs:github` as the preferred distribution. The script is fetched once and cached locally by yt-dlp; subsequent runs use the cache. `ejs:npm` was not added because it pulls from the npm registry (an additional outbound dependency) and `ejs:github` is sufficient.

### 3. Inline progress callback over a library
A lightweight `_make_cli_progress_callback()` factory in `watcher.py` uses `\r` overwriting and a checkmark on completion. This avoids adding `tqdm`, `rich`, or similar as a dependency. The callback is only attached in the CLI layer — the `downloader.py` API stays generic (caller-supplied callback).

### 4. DB-backed log level with try/except fallback
The log level is read from the DB before dispatch using `registry.get_setting()` directly. If the DB has not been initialised yet (`_get_conn()` raises `RuntimeError`), the fallback is `INFO`. This avoids calling `init_db()` redundantly in `main()` just for the logger, since every `cmd_*` function already calls `init_db()` itself.

### 5. Validation at config write time
`log-level` values are upper-cased and validated against `_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR"}` at write time in `cmd_config`. This prevents invalid values from ever reaching `getattr(logging, level)` at startup.

## Risks / Trade-offs

- **EJS script requires internet on first run**: On first use after install, yt-dlp will fetch the solver script from GitHub. If the machine is offline or GitHub is unreachable, the fetch fails silently and warnings will still appear for that session.
  → *Mitigation*: For containers, pre-warm the cache during the Docker build step. No code change needed — just run a dummy extraction during `docker build`.

- **Node.js is a system dependency, not a Python one**: It is not expressible in `requirements.txt` or `pyproject.toml`.
  → *Mitigation*: Document in `README.md` and in a future `Dockerfile`.

## Migration Plan

No schema changes, no breaking API changes. The changes are confined to `_build_ydl_opts` and `watcher.py`. Existing installs pick up the new behaviour automatically on the next `pip install -e .` (or equivalent). No rollback needed — the `js_runtimes` and `remote_components` keys are ignored gracefully by older yt-dlp versions.
