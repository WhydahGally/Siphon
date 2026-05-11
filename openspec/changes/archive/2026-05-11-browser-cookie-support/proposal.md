## Why

Siphon cannot currently download private playlists, age-restricted videos, or members-only content because it has no way to pass authentication credentials to yt-dlp. Browser cookie passthrough is yt-dlp's supported mechanism for this — adding it unlocks a significant class of content that users legitimately own but cannot access today.

## What Changes

- New API endpoints to upload, query, and delete a cookie file (`POST/GET/DELETE /settings/cookie-file`).
- Cookie file is stored at a fixed path inside `.data/` (`cookies.txt`); auto-renamed on upload regardless of source filename.
- Cookie file upload validates content against the Netscape HTTP Cookie File format; max upload size 1 MB.
- `delete_cookie_file_safe()` shared utility enforces path and filename safety invariants before any disk deletion; used by both the dedicated delete endpoint and factory reset.
- New global config key `cookies-enabled` (default `true`) controlling whether the cookie file is used by default.
- New per-playlist `cookies_enabled` column (NULL = follow global, 0 = force-off, 1 = force-on); follows the same resolution pattern as SponsorBlock.
- Cookie file existence gates all cookie-related toggles: if no file is present, the settings toggle is disabled and per-playlist / dashboard toggles are hidden.
- `cookie_file` threaded through the full download chain: `enumerate_entries`, `download`, `_build_ydl_opts`, `download_worker`, `download_parallel`, `sync_parallel`, `run_download_job`.
- New CLI commands: `siphon config cookies-enabled <true|false>` (global) and `siphon config-playlist <name> cookies <true|false>` (per-playlist), following existing `sb-enabled` / `sponsorblock` CLI patterns.
- Settings UI gains a new **Cookies** row in the Downloads section with: upload button (native OS file dialog), replace (re-upload) button, ConfirmButton delete, configured indicator badge, disabled toggle with tooltip when no file present, and security guidance linking to the yt-dlp cookie export guide.
- Dashboard (DownloadForm) and Library (PlaylistRow) each gain a **Cookies** toggle rendered only when a cookie file is configured.
- Factory reset updated to delete the cookie file via `delete_cookie_file_safe()` and UI description updated to mention cookies.

## Capabilities

### New Capabilities

- `cookie-file-management`: Upload, validation (Netscape format, 1 MB limit, content + extension checks), safe deletion, storage at `.data/cookies.txt`, factory reset integration, and the three dedicated API endpoints (`POST/GET/DELETE /settings/cookie-file`).
- `cookie-passthrough`: Threading `cookie_file` through the full yt-dlp download chain and resolving the effective value (file presence + global toggle + per-playlist override) at each call site in `api.py`.

### Modified Capabilities

- `global-config-keys`: New `cookies-enabled` key added to `_KNOWN_KEYS` and `_ALLOWED_VALUES`.
- `settings-ui`: New Cookies row in the Downloads section; disabled-state tooltip for the toggle; updated Factory Reset description.
- `playlist-registry`: New `cookies_enabled` INTEGER column on the `playlists` table; new `set_playlist_cookies_enabled()` function; `get_cookie_file()` resolution function; `PlaylistPatch` model extended.
- `download-engine`: `cookie_file: Optional[str]` parameter added to `enumerate_entries`, `download`, `_build_ydl_opts`, `download_worker`, `download_parallel`, `sync_parallel`, and `run_download_job`.

## Impact

- **Backend**: `registry.py`, `downloader.py`, `api.py`, `models.py`, `cli.py`, `app.py`
- **Frontend**: `Settings.vue`, `DownloadForm.vue`, `PlaylistRow.vue`, `useSettings.js`
- **DB**: Additive migration — one new column (`playlists.cookies_enabled`); no breaking schema changes
- **yt-dlp**: No version bump required; `cookiefile` option has been stable for years
- **Security**: File upload limited to 1 MB; destination path hardcoded server-side (no traversal possible); cookie file contents never returned by any API endpoint; `GET /settings/cookie-file` returns `{"set": true|false}` only
