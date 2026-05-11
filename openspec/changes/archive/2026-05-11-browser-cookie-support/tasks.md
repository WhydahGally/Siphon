## 1. Database & Registry

- [x] 1.1 Add `cookies_enabled INTEGER` column to `_SCHEMA` in `registry.py`; add additive `ALTER TABLE playlists ADD COLUMN cookies_enabled INTEGER` migration in `init_db()` (same pattern as `sponsorblock_categories`)
- [x] 1.2 Add `set_playlist_cookies_enabled(playlist_id: str, enabled: Optional[bool]) -> None` to `registry.py` (True→1, False→0, None→NULL)
- [x] 1.3 Add `get_cookie_file(playlist_row=None) -> Optional[str]` to `registry.py` implementing the 5-step resolution: file-exists check → per-playlist override → global `cookies_enabled` setting → return path or None
- [x] 1.4 Add `delete_cookie_file_safe(data_dir: str) -> bool` to `registry.py` enforcing all three safety invariants (path prefix, `re.fullmatch(r'cookies\.txt', basename)`, file-exists) before calling `os.remove()`; raise `RuntimeError` on invariant failure; return False if file absent
- [x] 1.5 Update playlist dict serialisation (list/get helpers) to include `cookies_enabled` field from the DB row

## 2. Models

- [x] 2.1 Add `cookies_enabled: Optional[bool] = None` to `PlaylistCreate` and `PlaylistPatch` Pydantic models in `models.py`

## 3. API — Cookie File Endpoints

- [x] 3.1 Add `POST /settings/cookie-file` endpoint: enforce 1 MB limit (413 if exceeded), validate Netscape cookie format (at least one 7-field tab-separated line with `TRUE`/`FALSE` in fields 2 & 4 and integer in field 5), save to `.data/cookies.txt` with `os.chmod(path, 0o600)`, return 204
- [x] 3.2 Add `GET /settings/cookie-file` endpoint: return `{"set": True}` if `.data/cookies.txt` exists and is a regular file, `{"set": False}` otherwise; never return path or contents
- [x] 3.3 Add `DELETE /settings/cookie-file` endpoint: call `registry.delete_cookie_file_safe(data_dir)`; return 204 on success, 404 if file not present

## 4. API — Existing Endpoint Updates

- [x] 4.1 Update `api_factory_reset()` to call `registry.delete_cookie_file_safe(data_dir)` after the DB wipe; silently ignore `False` return (file absent)
- [x] 4.2 Update playlist PATCH handler to call `registry.set_playlist_cookies_enabled()` when `cookies_enabled` is present in `PlaylistPatch` body
- [x] 4.3 Update playlist creation handler to pass `cookies_enabled` from `PlaylistCreate` to `registry.add_playlist()`
- [x] 4.4 Add `cookies-enabled` to the settings endpoint allow-list (`_KNOWN_KEYS` check in `api_put_setting`) with accepted values `"true"` / `"false"`
- [x] 4.5 Add `_get_cookie_file_path(playlist_row=None) -> Optional[str]` helper in `api.py` that delegates to `registry.get_cookie_file()`
- [x] 4.6 Thread `cookie_file=_get_cookie_file_path(row)` into all `sync_parallel()` call sites in `api.py` (scheduler callback `_scheduler_sync_fn`, manual sync endpoint, sync-failed endpoint)
- [x] 4.7 Thread `cookie_file=_get_cookie_file_path()` into the `run_download_job()` call site in `api.py`; also pass to the `enumerate_entries()` preflight in the job creation handler

## 5. Downloader

- [x] 5.1 Add `cookie_file: Optional[str] = None` to `enumerate_entries()`; set `ydl_opts["cookiefile"] = cookie_file` when non-None
- [x] 5.2 Add `cookie_file: Optional[str] = None` to `_build_ydl_opts()`; set `ydl_opts["cookiefile"] = cookie_file` when non-None
- [x] 5.3 Add `cookie_file: Optional[str] = None` to `download()`; pass to preflight `_preflight_opts` and to `_build_ydl_opts()`
- [x] 5.4 Add `cookie_file: Optional[str] = None` to `download_worker()` and thread through to `download()`
- [x] 5.5 Add `cookie_file: Optional[str] = None` to `download_parallel()` and thread through to `download_worker()`
- [x] 5.6 Add `cookie_file: Optional[str] = None` to `sync_parallel()` and thread through to `download_parallel()`
- [x] 5.7 Add `cookie_file: Optional[str] = None` to `run_download_job()` and thread through to `download_worker()`

## 6. CLI

- [x] 6.1 Add `cookies-enabled` to `_KNOWN_KEYS` in `cli.py` with db key `cookies_enabled` and accepted values `"true"` / `"false"`; add to `_ALLOWED_VALUES`
- [x] 6.2 Add special-case handling for `cookie-file` in `cmd_config`: read the file at the given path and POST its raw contents to `POST /settings/cookie-file`; print success or error; exit non-zero on failure
- [x] 6.3 Add `cookies` to `_PLAYLIST_KNOWN_KEYS`; implement read (print current `cookies_enabled` value) and write (PATCH with `cookies_enabled: true/false`) in `cmd_config_playlist`
- [x] 6.4 Update `app.py` to include `cookie-file` and `cookies-enabled` in the `config` subcommand argument choices

## 7. UI — useSettings.js

- [x] 7.1 Add `cookieFileSet` ref; populate from `GET /settings/cookie-file` → `data.set` on module load (parallel to existing settings fetch)
- [x] 7.2 Add `cookiesEnabled` ref; populate from `s.cookies_enabled !== 'false'` in the existing settings fetch
- [x] 7.3 Export `cookieFileSet` and `cookiesEnabled` from `useSettings()`

## 8. UI — Settings.vue

- [x] 8.1 Import `cookieFileSet` and `cookiesEnabled` from `useSettings()`; add hidden `<input ref="cookieFileInput" type="file" accept=".txt" style="display:none">` to the template
- [x] 8.2 Add `handleCookieFileSelected(event)` function: read selected file, POST to `/settings/cookie-file`, update `cookieFileSet` on 204, show success toast; show warning toast with server message on 400 or 413
- [x] 8.3 Add `handleCookieFileDelete()` function: call `DELETE /settings/cookie-file`, update `cookieFileSet = false` on 204, show success toast
- [x] 8.4 Add `onCookiesEnabledToggle()` function: flip `cookiesEnabled`, call `PUT /settings/cookies-enabled` silently (no toast)
- [x] 8.5 Add the **Cookies** setting row to the Downloads section (after Auto rename row) with: label "Cookies", description with YouTube ban warning and "Follow this guide ↗" hyperlink to `https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies`, upload button (when `!cookieFileSet`), replace button + configured badge + ConfirmButton delete (when `cookieFileSet`)
- [x] 8.6 Add `cookies-enabled` toggle to the Cookies row: disabled/greyed with tooltip "Upload a cookie file to enable this setting." when `!cookieFileSet`; active when `cookieFileSet`; wired to `onCookiesEnabledToggle()`
- [x] 8.7 Update the Factory Reset danger zone description to "Wipes everything — playlists, history, cookies and all settings."

## 9. UI — DownloadForm.vue

- [x] 9.1 Import `cookieFileSet` and `cookiesEnabled` from `useSettings()`; add `useCookies` local ref seeded from `cookiesEnabled.value`; watch `settingsLoaded` to update once (same pattern as `sponsorBlock`)
- [x] 9.2 Add "Cookies" toggle in the `.toggles-row`, rendered with `v-if="cookieFileSet"`, bound to `useCookies`
- [x] 9.3 Include `use_cookies: useCookies.value` in the job POST body

## 10. UI — PlaylistRow.vue

- [x] 10.1 Import `cookieFileSet` from `useSettings()`
- [x] 10.2 Add `useCookies` local ref initialised from `props.playlist.cookies_enabled ?? cookiesEnabledDefault`
- [x] 10.3 Add `toggleUseCookies()` function: optimistic flip + PATCH `/playlists/{id}` with `{cookies_enabled: next}`, revert on error (same pattern as `toggleSponsorBlock`)
- [x] 10.4 Add "Cookies" toggle in both desktop and mobile layouts inside the toggles row, rendered with `v-if="cookieFileSet"`

## 11. README

- [x] 11.1 Update `siphon config` key list to include `cookies-enabled` and `cookie-file`
- [x] 11.2 Update `siphon config-playlist` key list to include `cookies`
- [x] 11.3 Add a note to the features list mentioning browser cookie support for private/age-restricted content
