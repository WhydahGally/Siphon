## 1. Renamer — Remove Tier 1.5

- [x] 1.1 Delete `_parse_title_separator` function and the `_TITLE_SEPARATORS` constant from `renamer.py`
- [x] 1.2 Remove the tier 1.5 early-return block from `rename_file` (the `artist_hint`/`track_hint` path and its `RenameResult` with `tier="title_separator"`)
- [x] 1.3 Update the `RenameResult.tier` docstring to reflect the 3-value enum: `"yt_metadata"` | `"musicbrainz"` | `"yt_title_fallback"`

## 2. Renamer — Noise Stripping

- [x] 2.1 Add `_DEFAULT_NOISE_PATTERNS` constant — list of inner regex strings (official video, official audio, lyric video, lyrics, audio, visualizer, visual, hd, 4k, 1080p, official)
- [x] 2.2 Implement `strip_noise(title: str, patterns: list[str] | None = None) -> str` — compiles outer bracket wrapper + inner patterns into a single regex; applies iteratively until no change; uses defaults when `patterns` is `None` or empty
- [x] 2.3 Call `strip_noise` on the cleaned title before building the MB query in `rename_file`
- [x] 2.4 Call `strip_noise` on `final_name` before constructing each `RenameResult` across all three tiers (yt_metadata, musicbrainz, yt_title_fallback)
- [x] 2.5 Accept `noise_patterns: list[str] | None = None` parameter in `rename_file` and thread it through to `strip_noise` calls

## 3. Renamer — Phrase-Match Validator

- [x] 3.1 Add `_normalize(s: str) -> str` helper — lowercase, replace non-alphanumeric with space, collapse whitespace
- [x] 3.2 Implement `_mb_artist_in_title(mb_artist: str, title: str) -> bool` — checks normalized(mb_artist) is a contiguous substring of normalized(title)
- [x] 3.3 Implement `_mb_track_in_title_excl_artist(mb_track: str, mb_artist: str, title: str) -> bool` — removes first occurrence of normalized(mb_artist) from normalized(title), then checks if normalized(mb_track) is a contiguous substring of the remainder
- [x] 3.4 Replace `_mb_passes_threshold` with updated `_mb_passes_threshold(recording, yt_title, uploader)` implementing BOTH_IN_TITLE and UPLOADER_MATCH paths (score ≥ 85 required for both); remove the old token-overlap logic
- [x] 3.5 Add separator detection INFO log in `rename_file` before the MB query — check if cleaned title contains any of `//`, `⧸⧸`, `–`, `—`, ` - ` and log if found
- [x] 3.6 Update the `_mb_search` call site in `rename_file` to pass `uploader` from `info_dict` into `_mb_passes_threshold`

## 4. Backend — `title-noise-patterns` Config Key

- [x] 4.1 Add `"title-noise-patterns"` entry to `_KNOWN_KEYS` in `watcher.py` with db key `title_noise_patterns` and a description
- [x] 4.2 Add PUT validation for `title-noise-patterns` in the settings write handler: parse JSON array, validate each string compiles as a Python regex; return `400` with the offending pattern on failure
- [x] 4.3 Wire `title-noise-patterns` value into the `rename_file` call — load from DB at download time and pass as `noise_patterns`

## 5. Settings UI — Noise Patterns Editor

- [x] 5.1 Add "Edit noise patterns" toggle button in the MusicBrainz section of `Settings.vue`, below the user-agent input
- [x] 5.2 Add collapsible textarea that expands when the toggle is clicked; on expand, call `GET /settings/title-noise-patterns` and populate the textarea (one pattern per line); show muted note if null
- [x] 5.3 Add Save button that serializes textarea lines into a JSON array and calls `PUT /settings/title-noise-patterns`; show success toast on `200`, error toast on `400` with server message
- [x] 5.4 Add Cancel button that collapses the editor and reverts textarea content without making an API call

## 6. Spec Updates

- [x] 6.1 Apply delta spec `specs/auto-renamer/spec.md` to `openspec/specs/auto-renamer/spec.md` — update tier enum, remove tier 1.5 and token-overlap scoring requirements, add phrase-match validator and noise stripping requirements
- [x] 6.2 Apply delta spec `specs/global-config-keys/spec.md` to `openspec/specs/global-config-keys/spec.md` — add `title-noise-patterns` key requirement
- [x] 6.3 Apply delta spec `specs/settings-ui/spec.md` to `openspec/specs/settings-ui/spec.md` — add noise patterns editor requirement
- [x] 6.4 Promote `specs/title-noise-patterns/spec.md` from change to `openspec/specs/title-noise-patterns/spec.md`
