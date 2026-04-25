## Context

Siphon uses yt-dlp for all media fetching. Despite yt-dlp supporting 1000+ platforms, Siphon's code is peppered with YouTube-specific assumptions: a URL-pattern heuristic for playlist detection, `yt_title` column names in the DB, `yt_metadata`/`yt_title` tier constants in the renamer, YouTube-branded log and error messages, and no stored record of which platform a playlist came from.

None of these constraints are functional — the downloader, scheduler, and sync logic are already platform-agnostic. The work is primarily: fix the one behavioral issue (`is_playlist` detection), rename identifiers to be generic, and add `platform` as a first-class field.

Current state of `is_playlist` in `downloader.py`:
```python
is_playlist = "list=" in url or "/playlist" in url
```
This fires on the URL string and is YouTube-shaped. It affects only the `outtmpl` path selection inside `download()`. In all production code paths (`sync_parallel` → `download_worker` → `download()`), this check fires on individual video URLs that have already been enumerated — so it always evaluates to `False` and has no practical effect. The fix matters for correctness and for any future direct caller.

## Goals / Non-Goals

**Goals:**
- Replace `is_playlist` URL heuristic with a yt-dlp `_type` pre-flight call inside `download()`
- Rename `yt_title` to `title` throughout: DB schema, Python models, API responses, UI bindings
- Rename rename-tier constants: `yt_metadata` → `metadata`, `yt_title` → `title`
- Add `platform` column to `playlists` table, populated at registration from a sanitized `extractor_key`
- Expose `platform` in API responses and library UI meta area
- Strip all YouTube-specific strings from user-facing messages, log lines, docstrings
- Add a tier display label map in the UI

**Non-Goals:**
- Authentication / cookies for private content (future change)
- Per-platform format or quality overrides
- Multi-platform e2e tests (existing e2e suite is YouTube-focused, stays as-is)
- Any change to the enumerate-then-diff sync model

## Decisions

### D1: `_type`-based playlist detection via pre-flight `extract_info`

`download()` will call `yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True}).extract_info(url, download=False)` before building the `outtmpl`. It reads `info.get("_type", "video")` and branches:
- `"playlist"` or `"channel"` → `%(playlist_title)s/%(title)s.%(ext)s` template
- anything else → `%(title)s.%(ext)s`

**Alternatives considered:**
- Add `is_playlist: Optional[bool]` parameter — avoids the extra network call but requires all callers to know the answer upfront. Inconsistent with the "ask yt-dlp" philosophy and adds cognitive overhead.
- Keep URL heuristic but extend it with more patterns — fundamentally unmaintainable across 1000+ platforms.

**Performance note:** In the `sync_parallel` path, `download()` is always called with a single video URL. `extract_flat` on a single video is a very lightweight metadata call (no format resolution). The overhead is negligible.

### D2: DB schema — drop and recreate

Since there are no production users, the cleanest path is to drop and recreate `siphon.db` on next daemon start. The `init_db()` function will be updated to use `CREATE TABLE` (without `IF NOT EXISTS` for tables being renamed) after dropping them, rather than a migration chain.

`yt_title` → `title` in `items` and `failed_downloads` tables.  
New `platform TEXT` column added to `playlists` table (nullable — populated at add time).

**Alternatives considered:**
- `ALTER TABLE` migration: SQLite doesn't support `DROP COLUMN` before 3.35, and renaming involves `CREATE TABLE AS ... SELECT` anyway. Since we're dropping data, recreating is strictly simpler.
- Keep `yt_title` column name, rename only in Python: Leaves the YouTube branding embedded in the DB schema permanently. Not worth it.

### D3: `platform` stored as sanitized extractor key, populated at registration

At `POST /playlists`, after `_fetch_playlist_info()` returns the info dict, extract `info.get("extractor_key", "")` and pass it through a sanitizer that strips known yt-dlp suffixes (`Tab`, `Playlist`, `Channel`, `Album`, `User`, `Search`, `Feed`, `Tag`, `Set`, `IE`) using a regex. Result is stored directly in the `platform` column.

```python
import re
_EXTRACTOR_SUFFIXES = re.compile(r'(?:Tab|Playlist|Channel|Album|User|Search|Feed|Tag|Set|IE)$')

def sanitize_platform(extractor_key: str) -> str:
    return _EXTRACTOR_SUFFIXES.sub('', extractor_key).strip() or extractor_key
```

Examples: `YoutubeTab` → `Youtube`, `BandcampAlbum` → `Bandcamp`, `Soundcloud` → `Soundcloud`.

`platform` is stored clean. No raw extractor key retained.

**Alternatives considered:**
- Store `webpage_url_domain` (`youtube.com`, `soundcloud.com`): Human readable but loses the capitalized brand-name style the user preferred.
- Store raw `extractor_key` and sanitize at display time: More flexible but means the API leaks internal yt-dlp identifiers.

### D4: Rename tier constants in code and DB

`renamer.py` tier string constants updated: `"yt_metadata"` → `"metadata"`, `"yt_title"` → `"title"`. These values are stored in `items.rename_tier` and `failed_downloads` (unused there). Since the DB is being dropped anyway, no migration is needed.

UI tier badge display: A label map is introduced in the Vue components rather than displaying the raw value:

```js
const TIER_LABELS = {
  metadata: 'Metadata',
  musicbrainz: 'MusicBrainz',
  title: 'Title',
  manual: 'Manual',
}
```

`item.rename_tier` is passed through this map before rendering. If a value is not in the map, the raw string is shown as a fallback.

### D5: `yt_title` field in Python models renamed to `title`

`ItemRecord.yt_title`, `JobItem.yt_title`, `FailureRecord.title` (already named `title`) — the field on `ItemRecord` and `JobItem` becomes `.title`. All API response dicts that previously emitted `"yt_title"` emit `"title"` instead. UI bindings updated from `item.yt_title` to `item.title`.

**Note on `FailureRecord`**: Already uses `.title`, no change needed.

### D6: `passthrough_rename` tier label

`passthrough_rename()` in `renamer.py` currently returns a `RenameResult` with `tier=None`. The "passthrough" case (auto-rename OFF) means the filename is exactly what yt-dlp would have produced — the raw download title. No tier badge is shown when `tier=None`. This behavior is preserved unchanged; no new tier value is needed.

## Risks / Trade-offs

- **`extract_flat` pre-flight adds a network call in `download()`**: In production this fires on individual video URLs (always `_type = "video"`), so it's a quick metadata-only fetch. For truly direct playlist URL calls (tests, future CLI), it adds one round trip. Acceptable trade-off for correctness. → *Mitigation: None needed; production path impact is negligible.*

- **Regex suffix stripping may mis-strip**: If yt-dlp adds an extractor named something that ends in one of the stripped suffixes (e.g. a hypothetical `AlbumArt` extractor), `Album` at the end would be stripped. → *Mitigation: The sanitizer is applied only to `extractor_key`, and the suffix list is conservative. Review on yt-dlp major version bumps.*

- **API contract breakage (`yt_title` → `title`)**: Any existing clients (tests, curl scripts, CI) that reference `yt_title` in JSON responses will break. → *Mitigation: DB is being dropped, tests updated as part of this change.*

## Migration Plan

1. Stop the daemon
2. Delete `.data/siphon.db`
3. Deploy new code
4. Start daemon — `init_db()` creates fresh schema with new column names
5. Re-add playlists via `siphon add` or UI (platform field auto-populated)
