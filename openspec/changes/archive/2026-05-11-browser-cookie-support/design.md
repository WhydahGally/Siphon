## Context

yt-dlp has stable built-in support for a `cookiefile` option (Netscape HTTP Cookie File format). Siphon wraps yt-dlp but never threads this option through its download chain, making private playlists, age-restricted videos, and members-only content inaccessible. Additionally, yt-dlp's preflight `extract_flat` enumeration call (used for playlist discovery) must also receive the cookie file or it will fail to enumerate private playlists before a download even starts.

The feature must support Docker/Unraid users who have no shell access to the container, hence the UI upload path is primary. Local (direct-run) users should also be able to drop a file into `.data/` directly or use a CLI command.

## Goals / Non-Goals

**Goals:**
- Allow users to upload a cookie file via the web UI or CLI and have it used automatically for all yt-dlp calls
- Support per-playlist enable/disable of cookie use (same resolution pattern as SponsorBlock)
- Global default toggle for cookie use in Settings
- Safe cookie file deletion — shared utility used by both the dedicated delete endpoint and factory reset
- Never expose cookie file contents or filesystem path through any API endpoint

**Non-Goals:**
- Per-playlist separate cookie files — one global cookie file, one Siphon instance
- Cookie refresh / rotation detection — if cookies expire, downloads fail with yt-dlp errors (existing failure path)
- Browser-based cookie extraction — users must export manually per the yt-dlp guide
- Authentication beyond cookies (OAuth, API keys)

## Decisions

### 1. Fixed path: `.data/cookies.txt` — not DB-stored

File existence at a hardcoded path replaces a DB setting. If `.data/cookies.txt` exists, cookies are available; if absent, they are not. This eliminates path injection risk (no user-supplied path ever reaches `open()` or yt-dlp's `cookiefile` option as a server-side path). Docker users already mount `.data/` as a volume, so the file is naturally accessible. The `GET /settings/cookie-file` endpoint returns `{"set": true|false}` — the path is never returned.

_Alternative considered_: Store path in the `settings` DB table. Rejected because it introduced user-controlled path values on the server, required path validation logic, and offered no UX benefit (the UI always uploads to a fixed location anyway).

### 2. Auto-rename uploaded file to `cookies.txt`

Regardless of the uploaded filename, the file is always saved as `.data/cookies.txt`. The source filename is irrelevant after validation. This is the standard approach for tools that accept config file uploads (e.g., Bitwarden CSV import, FreshRSS OPML).

_Alternative considered_: Require users to name their file `cookies.txt` and reject others. Rejected because it adds friction with zero security benefit.

### 3. Dedicated endpoints, not `PUT /settings`

Cookie file management uses three dedicated endpoints (`POST/GET/DELETE /settings/cookie-file`) rather than the generic `PUT /settings/{key}` machinery. The cookie file is a binary/text blob resource, not a JSON string value. Encoding file contents in a `SettingWrite` body would require base64 and break the clean settings contract.

The `cookies-enabled` toggle (a boolean) _does_ go through the normal `PUT /settings/cookies-enabled` path — it is just a string setting.

### 4. Content validation — Netscape format, not strict

Uploaded files are validated by checking that at least one non-comment line matches the 7-tab-field Netscape cookie structure: `domain \t bool \t path \t bool \t expiry \t name \t value`. Fields 2 and 4 must be `TRUE` or `FALSE`; field 5 must be a non-negative integer. Domain and cookie name values are not validated (too many legitimate edge cases). This rejects non-cookie files while accepting valid exports from any browser extension.

### 5. `delete_cookie_file_safe()` shared utility

Both `DELETE /settings/cookie-file` and `POST /factory-reset` delete the cookie file through a single shared function in `registry.py`. Safety invariants enforced before any `os.remove()` call:
1. Computed path must be prefixed by `os.path.abspath(data_dir) + os.sep`
2. Basename must match `re.fullmatch(r'cookies\.txt', filename)`
3. File must exist at the path

_Alternative considered_: Inline the delete in each caller. Rejected — duplicated safety checks are the classic way safety checks get skipped.

### 6. Toggle resolution mirrors SponsorBlock exactly

Per-playlist `cookies_enabled` column (NULL = follow global, 0 = force-off, 1 = force-on) with a `get_cookie_file(playlist_row)` resolution function that mirrors `get_sponsorblock_categories()`. Implementors already know this pattern. Global `cookies_enabled` setting defaults to `"true"`.

### 7. 1 MB upload limit

Realistic `cookies.txt` is 5–15 KB. 1 MB is ~70x headroom for unusually large cookie files while bounding DoS risk. Enforced at the `POST /settings/cookie-file` endpoint before file content is read.

## Risks / Trade-offs

- **Cookie rotation** → YouTube invalidates cookies if the same session is opened in a browser while yt-dlp uses them. Mitigated by UI guidance with a link to the yt-dlp export guide. Not a Siphon bug.
- **Account ban** → yt-dlp docs warn explicitly. Surfaced in the Settings UI description. Not a Siphon bug; users assume this risk.
- **Stale/expired cookies** → Silently appear as failed downloads with yt-dlp auth errors. The existing failure-recording path handles this. Future improvement: detect auth-specific error messages and surface a more actionable error. Out of scope here.
- **Factory reset race** → If factory reset fires while a download is in progress using cookies, the file is deleted mid-download. yt-dlp reads `cookiefile` at the start of each item, so partially completed items will not be affected; items that haven't started yet will fail. Acceptable — factory reset is intentionally destructive.
- **Plain HTTP upload** → Cookie file contents transmitted in a POST body over plain HTTP on a local network. Risk is low (Siphon is typically `localhost` or LAN-only with no auth), but the UI description should recommend HTTPS/VPN for remote access. Scope: UI note only.

## Migration Plan

- `ALTER TABLE playlists ADD COLUMN cookies_enabled INTEGER` — additive migration in `init_db()`, identical in structure to the existing `sponsorblock_categories` migration. Safe on all existing databases; new column defaults to `NULL` (follow global).
- No existing data is altered.
- Cookie file is absent on all existing installs by default; feature is fully opt-in.
- No rollback risk — new column is nullable, new endpoints are additive, no existing endpoints are modified.
