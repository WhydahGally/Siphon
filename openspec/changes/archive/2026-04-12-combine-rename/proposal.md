## Why

The current rename chain has a standalone "title separator" tier (tier 1.5) that resolves filenames by blindly splitting the YouTube title on separator characters without any validation. Testing proves this produces covers and wrong artists at a meaningful rate — a 100% MB score is no protection against cover recordings. The design was always intended to be a hint mechanism rather than a standalone resolver; this change completes that intent, simplifying the pipeline and improving accuracy.

## What Changes

- **Remove tier 1.5 (title_separator)** as a standalone renaming tier. The separator is no longer a resolver.
- **Collapse to 3 tiers**: `yt_metadata` → `musicbrainz` → `yt_title_fallback`.
- **Rework MB validation** from token-bag overlap to phrase-based substring matching with artist-exclusion. Two acceptance paths only: `BOTH_IN_TITLE` and `UPLOADER_MATCH`. The `HIGH_SCORE_TRACK_ONLY` path is removed — testing on real playlist data showed cover songs score 100 and cannot be distinguished by score alone.
- **Add YT noise stripping** as a standalone utility called before the MB query and again before emitting the final filename at every tier. Strip common YouTube suffixes such as `(Official Video)`, `(Lyric Video)`, `(Audio)` etc. The pattern list is configurable via a new `title-noise-patterns` setting.
- **Add `title-noise-patterns` global config key** stored as a JSON array in the settings DB. Readable and writable via `GET/PUT /settings/title-noise-patterns` and `siphon config title-noise-patterns`. Exposed in the Settings UI under the MusicBrainz section as a collapsible textarea editor.
- **Remove `title_separator` tier badge from UI** (Dashboard download queue and Library items panel). The badge renders the tier string directly — once the backend stops emitting `title_separator` this is automatic. Update the `RenameResult` docstring to reflect the 3-tier enum.
- **Log separator usage at INFO** when the title contains a known separator character, for debugging purposes.

## Capabilities

### New Capabilities

- `title-noise-patterns`: Configurable list of regex patterns for stripping YouTube title noise (Official Video, Lyric Video, etc.) from filenames and MB query inputs. Stored as a JSON array in the settings table. Readable/writable via API and CLI. Default patterns embedded in the renamer and used when the setting is absent.

### Modified Capabilities

- `auto-renamer`: Requirements changing — tier 1.5 removed, 3-tier enum, MB validation logic replaced with phrase-based matching, noise stripping applied at end of all tiers.
- `settings-ui`: New MusicBrainz section control for editing `title-noise-patterns` as a collapsible textarea.
- `global-config-keys`: New known key `title-noise-patterns`.

## Impact

- `src/siphon/renamer.py` — primary change surface: remove `_parse_title_separator`, revamp `_mb_passes_threshold`, add `strip_noise`, update `rename_file` tier flow.
- `src/siphon/watcher.py` — add `title-noise-patterns` to `_KNOWN_KEYS`, add GET/PUT handler, wire noise patterns into `rename_file` call.
- `src/ui/src/components/Settings.vue` — add collapsible textarea for `title-noise-patterns` in MusicBrainz section.
- `openspec/specs/auto-renamer/spec.md` — delta: update tier enum, remove tier 1.5 scenarios, add new validation scenarios.
- `openspec/specs/global-config-keys/spec.md` — delta: add `title-noise-patterns` key requirement.
- `openspec/specs/settings-ui/spec.md` — delta: add noise patterns control requirement.
- No new dependencies. No DB schema changes (settings table already stores arbitrary key/value strings; JSON array fits in the existing `value` TEXT column).
