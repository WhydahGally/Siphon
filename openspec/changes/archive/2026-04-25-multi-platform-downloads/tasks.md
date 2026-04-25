## 1. Database Schema

- [x] 1.1 Drop and recreate `siphon.db` schema in `registry.py`: rename `yt_title` → `title` in `items` and `failed_downloads` tables, add `platform TEXT` column to `playlists` table
- [x] 1.2 Update all SQL queries in `registry.py` that reference `yt_title` to use `title`
- [x] 1.3 Remove all `ALTER TABLE` migration stmts for columns that no longer exist; verify `init_db()` recreates cleanly from scratch

## 2. Python Models

- [x] 2.1 Rename `yt_title` field to `title` on `ItemRecord` and `JobItem` dataclasses in `models.py`
- [x] 2.2 Update all usages of `.yt_title` across `downloader.py`, `api.py`, and `renamer.py` to `.title`

## 3. Renamer Tier Constants

- [x] 3.1 In `renamer.py`, change tier string `"yt_metadata"` → `"metadata"` and `"yt_title"` → `"title"` at all return sites
- [x] 3.2 Update the `RenameResult` tier docstring comment to reflect new tier names
- [x] 3.3 Update `_KNOWN_KEYS` or any tier-aware logic in `api.py` / `cli.py` that references old tier strings

## 4. Platform Sanitizer & Population

- [x] 4.1 Add `sanitize_platform(extractor_key: str) -> str` helper in `api.py` using the suffix-stripping regex
- [x] 4.2 In `POST /playlists` handler, extract `info.get("extractor_key", "")`, sanitize, and pass to `registry.add_playlist()` as `platform`
- [x] 4.3 Update `registry.add_playlist()` signature and INSERT to accept and store `platform`
- [x] 4.4 Update `registry.get_playlist_by_id()` and `get_watched_playlists()` to return `platform` in the row

## 5. Playlist-Type Detection

- [x] 5.1 In `downloader.py:download()`, replace the `is_playlist = "list=" in url or "/playlist" in url` heuristic with a yt-dlp `extract_flat` pre-flight call that reads `info.get("_type", "video")`
- [x] 5.2 Treat `_type in ("playlist", "channel")` as playlist, everything else as single video

## 6. API Response Cleanup

- [x] 6.1 Replace all `"yt_title"` keys in API JSON response dicts with `"title"` in `api.py`
- [x] 6.2 Update `_normalise_youtube_url` → rename to `_normalise_url` in `api.py`
- [x] 6.3 Replace "YouTube" in error messages and log strings throughout `api.py` (e.g. `"Fetching playlist info from YouTube…"` → `"Fetching playlist info…"`)
- [x] 6.4 Add `platform` field to all playlist response objects in `api.py`

## 7. UI — Field Renames

- [x] 7.1 In `PlaylistItemsPanel.vue`, replace all `item.yt_title` references with `item.title`
- [x] 7.2 In `QueueItem.vue`, replace all `item.yt_title` references with `item.title`

## 8. UI — Tier Badge Labels

- [x] 8.1 Add `TIER_LABELS` map (`metadata` → "Metadata", `musicbrainz` → "MusicBrainz", `title` → "Title", `manual` → "Manual") in the relevant Vue components
- [x] 8.2 Update `tier-badge` rendering in `PlaylistItemsPanel.vue` and `QueueItem.vue` to use `TIER_LABELS[item.rename_tier] ?? item.rename_tier`

## 9. UI — Platform in Library Meta Area

- [x] 9.1 Add `platform` display to the playlist meta area in the library UI (the component that shows format, item count, etc.)

## 10. Docstrings & Comments

- [x] 10.1 Update `downloader.py` docstring examples (remove hardcoded `youtube.com` URLs; use generic placeholder)
- [x] 10.2 Update `renamer.py` Tier 1 comment from "YouTube music catalog metadata" to "Embedded metadata"
- [x] 10.3 Update `downloader.py` function-level docstrings that say "YouTube playlist or video URL" to "URL of a playlist or video (any yt-dlp-supported platform)"

## 11. Tests

- [x] 11.1 Update unit tests in `tests/unit/` that reference `yt_title` field or old tier strings (`yt_metadata`, `yt_title`)
- [x] 11.2 Update e2e tests in `tests/e2e/` that assert on `yt_title` JSON keys or old tier values in API responses
