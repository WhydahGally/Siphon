## Context

The rename pipeline currently runs four tiers: YT metadata → title separator → MusicBrainz text search → YT title fallback. The title separator tier (1.5) resolves filenames by splitting the YouTube title on characters like `//`, `–`, `—`, `-` and using the left/right sides directly as artist and track. No validation is performed — the result is used as-is.

Empirical testing against a real YouTube playlist showed that:
- The separator tier has no ability to detect ordering (artist could be left or right)
- MB text search returns cover recordings and wrong artists at score 100
- Token-bag overlap validation fails on scrambled word order
- Uploader channel name is the most reliable local signal for artist corroboration

The existing `_mb_passes_threshold` function uses Jaccard-style token overlap which is symmetric and order-blind, allowing false positives from cover songs.

## Goals / Non-Goals

**Goals:**
- Remove the standalone title separator tier; separator logic is deleted entirely
- Replace token-bag validation with phrase-based substring matching
- Prevent cover-song false positives by requiring artist corroboration from the title or uploader
- Add a configurable noise-stripping function applied before MB queries and before final filename emission
- Expose `title-noise-patterns` as a user-editable setting via API, CLI, and Settings UI

**Non-Goals:**
- AcoustID / Chromaprint fingerprinting (future change)
- Structured MB queries (abandoned — free-text is better when we have no reliable split)
- Migration of existing DB rows with `rename_tier = "title_separator"` (DB will be reset; system is beta)
- Any change to the download engine, scheduler, or watcher behavior

## Decisions

### Decision 1: Remove title separator as a resolver

**Chosen:** Delete `_parse_title_separator` and the tier 1.5 early-return entirely.

**Rationale:** The separator was designed as a hint for MB, never a standalone resolver. It was shipped that way temporarily. Testing confirms it produces wrong results when the artist puts their name on the right side of the separator, or when a hyphen appears in an artist name (Alt-J, A-ha). The separator gives no reliable split direction.

**Alternative considered:** Use separator as a query hint (structured MB query). Rejected — a bad structured query (`recording:"J - Breezeblocks" AND artist:"Alt"`) actively misleads MB. Free-text MB handles these cases better without the structured hint.

### Decision 2: Two-path validator replacing token overlap

**Chosen:** Phrase-based substring matching with two acceptance paths:

```
BOTH_IN_TITLE:
  normalize(mb_artist) is a substring of normalize(yt_title)
  AND normalize(mb_track) is a substring of (normalize(yt_title) with mb_artist removed)

UPLOADER_MATCH:
  normalize(mb_track) is a substring of normalize(yt_title)
  AND normalize(uploader) == normalize(mb_artist)
```

`normalize(s)` = lowercase, replace all non-alphanumeric with space, collapse whitespace.

**Rationale:** Token-bag approach allowed "This a - song is" to match "This is a song" — it only checks set membership, not phrase continuity. Substring matching is order-sensitive. The artist-exclusion step (remove mb_artist from title before checking track) prevents false positives on titles like "Red % Blue Sky" where "Blue" is the artist and "Sky" the track — without exclusion, "blue" would appear in the track search space.

**Alternative considered:** Keeping `HIGH_SCORE_TRACK_ONLY` path at a ≥95 threshold. Rejected — testing showed cover songs score 100. Score is a matching-quality signal, not an artist-authenticity signal. No score threshold can distinguish an original from a cover.

### Decision 3: Noise stripping as a standalone utility, applied twice

**Chosen:** A `strip_noise(title, patterns)` function called:
1. Before the MB query (cleans the search input, removes tokens like "Official Audio" that don't exist in MB's database)
2. Before emitting the final filename at every tier (ensures Tier 3 fallback doesn't produce "Song Name (Official Audio).mp3")

Calling it twice is intentional — MB responses occasionally include version suffixes and we want the final filename clean regardless of source.

**Alternative considered:** Applying only at Tier 3. Rejected — the proposal requires it before MB queries too. Calling it only at Tier 3 would leave "Official Audio" in MB query input and miss cases where MB response contains noise patterns.

### Decision 4: title-noise-patterns as a JSON array in the settings DB

**Chosen:** Store as a JSON string in the existing `settings` table under key `title_noise_patterns`. Parse on read; the renamer receives a `list[str]` of pattern strings. The patterns are compiled into a single regex at startup (or per-call if changed at runtime).

**Rationale:** The settings table already holds arbitrary `TEXT` values. A JSON array is the simplest list representation without schema changes. Consistent with how the rest of the settings system works.

**Default behaviour:** When the setting is absent or null, the renamer uses a hardcoded default list embedded in `renamer.py`. This ensures noise stripping works out-of-the-box with no configuration required.

**Patterns stored as plain regex strings** (not full regex objects). The outer wrapper `\s*[\(\[]\s*(...)\s*[\)\]]\s*$` is fixed in the application; users supply only the inner pattern strings, e.g. `"official video"`, `"lyric video"`.

Default pattern list:
```
official music video
official video
official audio
official lyric video
lyric video
lyrics?
audio(?: only)?
visuali[sz]er
visual
hd
4k
1080p
official
```

### Decision 5: UI noise patterns control

**Chosen:** Collapsible textarea in the Settings page under the MusicBrainz section. Hidden behind a "Edit noise patterns" toggle button. When opened, the textarea is pre-populated with the stored patterns (one per line). A Save button calls `PUT /settings/title-noise-patterns`. Cancel reverts. Same save/cancel UX pattern as the MB user-agent field.

**Rationale:** A raw textarea is the simplest control for a list of strings that users may want to edit. Hiding it behind a toggle keeps the settings page clean — most users will never need to change this.

### Decision 6: Tier string enum shrinks to 3 values

`RenameResult.tier` becomes: `"yt_metadata"` | `"musicbrainz"` | `"yt_title_fallback"`.

`"title_separator"` is removed. The UI badge renders the tier string directly — no per-tier visual mapping exists, so removing the value from the backend automatically stops the old label appearing for new downloads.

### Decision 7: Separator usage logged at INFO

When the cleaned title contains a known separator character (`//`, `⧸⧸`, `–`, `—`, `-`) a single INFO-level log line is emitted before the MB query, e.g.:
```
renamer: separator detected in title — using free-text MB query
```
This preserves the diagnostic signal without influencing any code path.

## Risks / Trade-offs

**Fewer renames succeed** → Acceptable. Precision over recall was explicitly chosen. Songs with artist names not present in the title and uploaded from aggregator channels (e.g. "Wicked Game" from "Music Compilation") now fall to Tier 3 rather than taking a risky guess. Tier 3 with noise stripping produces a usable filename in most cases (e.g. `Wicked Game.mp3`).

**`UPLOADER_MATCH` is strict (exact normalized equality)** → The uploader field on YouTube is not always the canonical artist name. "Beach House - Topic" would not match MB artist "Beach House". A fuzzy uploader match (substring or token overlap) would improve recall here at a small false-positive risk. This is deferred — exact match is the safe default.

**Noise pattern regex errors from user input** → If a user saves an invalid regex string via `PUT /settings/title-noise-patterns`, the renamer will fail to compile the pattern. Mitigation: validate the patterns on write in the PUT handler and return `400 Bad Request` with the compile error message.

**Existing `title_separator` rows in DB** → Not migrated. System is in beta and DB will be reset. Existing items will continue to show the old `title_separator` badge string in the UI, which is a cosmetic issue only.

## Open Questions

None — all decisions above are settled from the explore session.
