## Context

Siphon wraps yt-dlp and stores per-playlist configuration in a SQLite database. yt-dlp has native SponsorBlock support via the `sponsorblock_remove` option dict key, which calls the SponsorBlock API and uses ffmpeg (stream copy, no re-encode) to cut matched segments at postprocessing time. ffmpeg is already a hard dependency (baked into the Docker image as a static binary). No new dependencies are introduced.

The existing `auto_rename` feature establishes the pattern this change follows end-to-end: a global default setting seeds the form toggle at add time, the value is committed into the playlist record, and per-playlist overrides are possible via CLI. SponsorBlock replicates this pattern exactly, with the addition of a second global setting for the category list. The `--sponsorblock` flag on `siphon add` is opt-in (same as `--auto-rename`); both default to `False`.

## Goals / Non-Goals

**Goals:**
- Remove SponsorBlock-identified segments from downloaded files using yt-dlp's built-in postprocessor.
- Global default toggle + category list in Settings, seeding new playlists at creation.
- Per-playlist enable toggle in the UI (DownloadForm at add time; PlaylistRow after).
- Per-playlist category override via CLI (`sb-cats` key on `config-playlist`).
- Empty category array = SponsorBlock disabled (same semantics as mb-user-agent empty = unset).

**Non-Goals:**
- `--sponsorblock-mark` (chapter markers) — remove-only mode.
- `poi_highlight` and `chapter` categories (mark-only in yt-dlp).
- Per-playlist category picker in the UI (future improvement).
- `--force-keyframes-at-cuts` (precise but requires re-encode; stream copy is sufficient).

## Decisions

### D1: Two separate global settings keys, not one JSON blob

`sb-enabled` (`true`/`false`) and `sb-cats` (JSON array string) are stored as separate rows in the `settings` table, following the existing pattern for all other settings. A single JSON blob would be inconsistent and harder to query/patch individually via CLI.

### D2: `NULL` vs `""` in `playlists.sponsorblock_categories`

- `NULL` → no per-playlist override; use global categories at sync time.
- `""` (empty string) → explicitly disabled at per-playlist level regardless of global. This value is written by the API when `sponsorblock_enabled=false` is PATCHed from the UI toggle; it is **not** a valid CLI input.
- Non-empty string → JSON-encoded per-playlist category list.

This mirrors how `check_interval_secs = NULL` means "use global interval". To silence the global default for a specific playlist via CLI, use `siphon config-playlist <name> sponsorblock false`.

### D3: Empty categories in the UI → toggle off

When all chips are deselected in Settings.vue, the toggle flips to off and the chevron closes. The categories value is NOT cleared — it retains its last state. Re-enabling the toggle with empty categories is the user's responsibility; no automatic default restoration is applied.

### D4: Category resolution at download time, not at playlist creation

When a job runs, the resolved category list is: `playlist.sponsorblock_categories` (if non-NULL and non-empty) → else `settings.sb-cats` (global). This means changing the global categories retroactively affects all playlists without a per-playlist override — intentional, matches how `check_interval_secs` works.

### D5: CLI rejects empty string and empty array for `sb-cats`

Empty string and `[]` are both rejected with a clear error message directing the user to `siphon config-playlist <name> sponsorblock false` to disable. Passing a comma-separated list like `music_offtopic,intro` or a JSON array like `["music_offtopic"]` are the valid input formats; the CLI normalises comma-separated input to a JSON array before sending to the API.

### D6: yt-dlp SponsorBlock via Python API requires explicit post-processors

`ydl_opts["sponsorblock_remove"]` is only processed by the yt-dlp CLI arg parser — it is ignored when calling the Python API directly. The correct approach is to call `ydl.add_post_processor(SponsorBlockPP(ydl, categories=cats), when='after_filter')` and `ydl.add_post_processor(ModifyChaptersPP(ydl, remove_sponsor_segments=set(cats)), when='post_process')` after the `YoutubeDL` object is constructed.

ffmpeg is always present in the Docker image. On bare-metal installs without ffmpeg, yt-dlp logs a warning itself ("segment cutter not available") which surfaces through `_YtdlpLogger` into Siphon's logging and browser logs. No extra application-level guard needed.

## Risks / Trade-offs

- **SponsorBlock API unavailability** → yt-dlp handles this gracefully (logs a warning, skips removal, download proceeds normally). No Siphon-level handling needed.
- **Imprecise cuts at keyframe boundaries** → accepted; stream copy is fast and lossless. Maximum imprecision is ~4 seconds. Acceptable for music use case.
- **DB migration on existing installs** → `ALTER TABLE playlists ADD COLUMN sponsorblock_categories TEXT` is additive and safe. SQLite allows this with no data loss; existing rows get `NULL` (= use global).
- **yt-dlp SponsorBlock API changes** → category keys are stable (unchanged since 2021). If categories are renamed upstream, the stored values silently do nothing; yt-dlp logs a warning.

## Migration Plan

1. On daemon start, `init_db()` runs `ALTER TABLE IF NOT EXISTS` — idempotent.
2. Existing playlists get `sponsorblock_categories = NULL` (use global default at sync time).
3. Global `sb-enabled` defaults to `true`; `sb-cats` defaults to `["music_offtopic"]` — applied at read time if the key is absent from the settings table (same pattern as all other defaults).
4. No rollback required — the column is additive and the two new settings keys are ignored by older daemon versions.
