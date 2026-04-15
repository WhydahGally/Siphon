## Why

The Settings page in the web UI is a stub ("coming soon"). All configuration today requires CLI commands (`siphon config`), which is impractical for users who interact with Siphon primarily through the web UI. Building out the Settings page completes the web UI as a fully self-service interface.

## What Changes

- Implement the Settings page (`Settings.vue`) replacing the current stub
- Add `GET /version` API endpoint returning Siphon and yt-dlp versions
- Add `DELETE /playlists` endpoint + `siphon delete-all-playlists` CLI command to remove all playlists (data reset, keeps settings)
- Add `POST /factory-reset` endpoint + `siphon factory-reset` CLI command to wipe all DB tables (full reset)
- Add three new global config keys: `auto-rename` (global default), `theme` (dark/light), and `auto-rename` participates in the existing `_KNOWN_KEYS` dispatch
- `DownloadForm.vue`: load `auto-rename` global default on mount instead of hardcoding `true`
- `style.css`: add a `[data-theme="light"]` block; dark theme remains the default `:root` block
- `main.js`: read `theme` setting on app startup and set `data-theme` attribute before mount to avoid flash

## Capabilities

### New Capabilities
- `settings-ui`: The Settings page UI — all sections, controls, and their API interactions
- `global-config-keys`: The three new entries in `_KNOWN_KEYS` (`auto-rename`, `theme`) plus the two new API endpoints (`/version`, `/factory-reset`, `DELETE /playlists`) and their corresponding CLI subcommands (`siphon delete-all-playlists`, `siphon factory-reset`)

### Modified Capabilities
- `web-ui`: Settings page requirement added; auto-rename default seeded from global config
- `siphon-daemon`: Three new HTTP endpoints; `auto-rename` global config key; factory-reset and delete-all-playlists operations

## Impact

- **Backend**: `watcher.py` (new endpoints, new `_KNOWN_KEYS` entries), `registry.py` (new `factory_reset()` and `delete_all_playlists()` functions)
- **Frontend**: `Settings.vue` (full implementation), `style.css` (light mode vars), `main.js` (theme init on load), `DownloadForm.vue` (auto-rename default from config)
- **No new dependencies** — uses existing FastAPI, SQLite, Vue 3 stack
- **No breaking changes** — all new endpoints and CLI subcommands; existing CLI config keys and behaviour unchanged
