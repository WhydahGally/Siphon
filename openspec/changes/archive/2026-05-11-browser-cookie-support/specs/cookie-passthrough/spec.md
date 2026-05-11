## ADDED Requirements

### Requirement: get_cookie_file() resolution function
The registry module SHALL expose `get_cookie_file(playlist_row=None) -> Optional[str]` that resolves the effective cookie file path for a given download context.

Resolution order:
1. If `.data/cookies.txt` does not exist → return `None` (cookies unavailable regardless of any toggle)
2. If `playlist_row` is provided and `playlist_row["cookies_enabled"]` is `0` → return `None` (force-disabled)
3. If `playlist_row` is provided and `playlist_row["cookies_enabled"]` is `1` → return the path (force-enabled)
4. If global setting `cookies_enabled` is `"false"` → return `None`
5. Otherwise → return the path

#### Scenario: Cookie file absent — always None
- **WHEN** `get_cookie_file()` is called and `.data/cookies.txt` does not exist
- **THEN** the function SHALL return `None` regardless of any toggle state

#### Scenario: Per-playlist force-disabled
- **WHEN** `get_cookie_file(playlist_row)` is called and `playlist_row["cookies_enabled"]` is `0`
- **THEN** the function SHALL return `None` even if the file exists and the global toggle is enabled

#### Scenario: Per-playlist force-enabled
- **WHEN** `get_cookie_file(playlist_row)` is called and `playlist_row["cookies_enabled"]` is `1`
- **THEN** the function SHALL return the cookie file path even if the global toggle is disabled

#### Scenario: Global disabled
- **WHEN** `get_cookie_file()` is called with no playlist row, the file exists, and global `cookies_enabled` is `"false"`
- **THEN** the function SHALL return `None`

#### Scenario: Default — file present, all defaults
- **WHEN** `get_cookie_file()` is called with no playlist row, the file exists, and `cookies_enabled` has never been set
- **THEN** the function SHALL return the path to `.data/cookies.txt`

---

### Requirement: cookie_file parameter in enumerate_entries
`enumerate_entries(url, cookie_file=None)` SHALL accept an optional `cookie_file` parameter. When non-None, it SHALL set `ydl_opts["cookiefile"] = cookie_file` before the `extract_flat` call. This ensures private playlists can be enumerated before any item download begins.

#### Scenario: Private playlist enumerated with cookie file
- **WHEN** `enumerate_entries(url, cookie_file="/path/to/cookies.txt")` is called with a private playlist URL
- **THEN** yt-dlp SHALL receive `cookiefile` in its options and the playlist entries SHALL be returned

#### Scenario: Public URL — no cookie file needed
- **WHEN** `enumerate_entries(url)` is called without a `cookie_file`
- **THEN** no `cookiefile` key SHALL appear in yt-dlp options

---

### Requirement: cookie_file parameter in the full download chain
`cookie_file: Optional[str]` SHALL be added to all of the following functions: `download()`, `_build_ydl_opts()`, `download_worker()`, `download_parallel()`, `sync_parallel()`, and `run_download_job()`. When non-None, `_build_ydl_opts()` SHALL set `ydl_opts["cookiefile"] = cookie_file`. The parameter SHALL default to `None` on all signatures (backward-compatible).

#### Scenario: cookie_file flows from sync_parallel to yt-dlp
- **WHEN** `sync_parallel(..., cookie_file="/path/to/cookies.txt")` is called
- **THEN** every `download_worker()` invocation within that sync SHALL receive the cookie file path, which SHALL be passed to `_build_ydl_opts()` and set as `ydl_opts["cookiefile"]`

#### Scenario: No cookie_file — no yt-dlp option set
- **WHEN** any function in the chain is called without `cookie_file` (or with `None`)
- **THEN** `cookiefile` SHALL NOT appear in `ydl_opts`

---

### Requirement: API call sites read cookie file at dispatch time
All API call sites that dispatch `sync_parallel()` or `run_download_job()` (the scheduler callback, the manual sync endpoint, the sync-failed endpoint, and the job creation endpoint) SHALL call `registry.get_cookie_file(playlist_row)` at dispatch time and pass the result as `cookie_file=`. The same applies to the preflight `enumerate_entries()` call in job creation.

#### Scenario: Scheduled sync respects per-playlist cookies setting
- **WHEN** the scheduler fires a sync for a playlist with `cookies_enabled = 0`
- **THEN** `sync_parallel()` SHALL be called with `cookie_file=None` even if `.data/cookies.txt` exists

#### Scenario: Job dispatch with cookie configured
- **WHEN** a job is created via `POST /jobs` and `.data/cookies.txt` exists and `cookies_enabled` is unset
- **THEN** both `enumerate_entries()` and `run_download_job()` SHALL be called with the cookie file path

---

### Requirement: cookies-enabled global config key
`cookies-enabled` SHALL be added to `_KNOWN_KEYS` with db key `cookies_enabled`. Accepted values via `PUT /settings/cookies-enabled` SHALL be `"true"` and `"false"`. The CLI `siphon config cookies-enabled [true|false]` SHALL read and write this key. If unset, the effective default SHALL be `"true"` (cookies used when file is present).

#### Scenario: Read unset cookies-enabled
- **WHEN** `GET /settings/cookies-enabled` is called and the key has never been set
- **THEN** the response value SHALL be `null` (resolved as enabled by `get_cookie_file()`)

#### Scenario: Disable cookies globally
- **WHEN** `PUT /settings/cookies-enabled` is called with `"false"`
- **THEN** `get_cookie_file()` SHALL return `None` for all playlists without a per-playlist override

#### Scenario: Invalid value rejected
- **WHEN** `PUT /settings/cookies-enabled` is called with a value other than `"true"` or `"false"`
- **THEN** the response SHALL be `400 Bad Request`

---

### Requirement: per-playlist cookies CLI command
The CLI SHALL expose `cookies` as a key in `_PLAYLIST_KNOWN_KEYS`. `siphon config-playlist <name> cookies [true|false]` SHALL read or write the `cookies_enabled` column for the named playlist. Writing `true` SHALL set the column to `1`; writing `false` SHALL set the column to `0`. Reading SHALL display the current per-playlist value (or `null` / "following global" if the column is `NULL`).

#### Scenario: Disable cookies for a specific playlist
- **WHEN** `siphon config-playlist MyPlaylist cookies false` is run
- **THEN** the PATCH endpoint SHALL be called with `cookies_enabled: false` and a confirmation SHALL be printed

#### Scenario: Read per-playlist cookies setting
- **WHEN** `siphon config-playlist MyPlaylist cookies` is run (no value)
- **THEN** the current `cookies_enabled` value for that playlist SHALL be printed
