## MODIFIED Requirements

### Requirement: Three-tier rename chain
After a file is fully downloaded and postprocessed, the renamer SHALL attempt to resolve a clean `Artist - Track` name by trying three strategies in order. The first strategy that produces a confident result SHALL be used. The file on disk SHALL be renamed to the resolved name, preserving its extension. The renamer SHALL return a `RenameResult` dataclass on every code path.

`RenameResult` fields:
- `original_title` (str): the raw YT title from `info_dict['title']`
- `final_name` (str): the resolved filename stem (no extension)
- `tier` (str): one of `"yt_metadata"`, `"musicbrainz"`, `"yt_title"`, `"manual"`
- `new_path` (str): absolute path to the renamed file on disk

The `"manual"` tier is not produced by the automatic rename chain. It is set exclusively by the manual rename API when a user overrides the resolved name after download.

#### Scenario: Tier 1 resolves — YT metadata has artist and track
- **WHEN** `info_dict` contains non-empty `artist` AND `track` fields
- **THEN** the renamer SHALL produce the name `"{artist} - {track}"`, apply noise stripping to the result, rename the file, and return a `RenameResult` with `tier="yt_metadata"` and the correct `final_name` and `new_path`

#### Scenario: Tier 1 resolves — multi-artist field
- **WHEN** `info_dict['artist']` contains a comma-separated list of multiple artists
- **THEN** the renamer SHALL resolve a single primary artist name before forming the output. If one of the names matches the channel/uploader exactly, that name is used. Otherwise the first entry is used. The returned `RenameResult.tier` SHALL be `"yt_metadata"`.

#### Scenario: Tier 1 fails, tier 2 resolves — MusicBrainz returns confident match
- **WHEN** `info_dict` lacks `artist` or `track`, AND `mb_user_agent` is configured, AND the top MusicBrainz result passes the phrase-match validator
- **THEN** the renamer SHALL produce the name from the MusicBrainz result, apply noise stripping, rename the file, and return a `RenameResult` with `tier="musicbrainz"`

#### Scenario: Tier 1 fails, tier 2 skipped — no user-agent configured
- **WHEN** `info_dict` lacks `artist` or `track`, AND `mb_user_agent` is not configured
- **THEN** the renamer SHALL skip tier 2 entirely, log a DEBUG message, and fall through to tier 3

#### Scenario: Tier 1 fails, tier 2 rejects — validator does not accept MB result
- **WHEN** `info_dict` lacks `artist` or `track`, AND the MusicBrainz result does not satisfy either BOTH_IN_TITLE or UPLOADER_MATCH validation
- **THEN** the renamer SHALL discard the MusicBrainz result and fall through to tier 3

#### Scenario: Tier 1 and tier 2 fail — tier 3 fallback with separator detection (auto-rename ON)
- **WHEN** neither tier 1 nor tier 2 produces a result, AND auto-rename is ON
- **AND** the title contains a known separator (`//`, `⧸⧸`, `–`, `—`, `-`)
- **THEN** the renamer SHALL split the title on the first matching separator into artist and track parts, format the result as `"{artist} - {track}"`, apply noise stripping, rename the file, and return a `RenameResult` with `tier="yt_title"`

#### Scenario: Tier 1 and tier 2 fail — tier 3 fallback without separator (auto-rename ON)
- **WHEN** neither tier 1 nor tier 2 produces a result, AND auto-rename is ON
- **AND** the title does NOT contain any known separator
- **THEN** the renamer SHALL apply the visual-equivalent character map to replace filesystem-unsafe ASCII characters with their Unicode lookalikes, apply noise stripping to the result, and return a `RenameResult` with `tier="yt_title"`
- **NOTE** the old `sanitize()` function (which stripped unsafe chars leaving gaps) SHALL NOT be used in this path

#### Scenario: No filepath available
- **WHEN** `info_dict` contains no `filepath` or `filename`
- **THEN** the renamer SHALL log a warning and return `None` (existing behaviour preserved)

#### Scenario: Manual tier is not produced by auto-rename
- **WHEN** the auto-rename chain runs during download
- **THEN** the tier SHALL never be `"manual"` — that value is reserved for post-download user overrides

### NEW Requirement: Passthrough rename when auto-rename is OFF

When auto-rename is disabled, the renamer SHALL still run a lightweight rename pass to ensure the DB's `renamed_to` field matches the actual file on disk. This prevents mismatches caused by yt-dlp's own filename sanitisation (e.g. replacing `/` with `⧸`).

`RenameResult` for passthrough:
- `tier`: `"yt_title"`
- `final_name`: the YT title with filesystem-unsafe chars replaced by visual-equivalent Unicode lookalikes
- No noise stripping, no MusicBrainz lookup, no metadata extraction

#### Scenario: Auto-rename OFF — passthrough rename applied
- **WHEN** auto-rename is OFF
- **THEN** the renamer SHALL apply the visual-equivalent character map to the raw YT title, rename the file on disk to the result (preserving extension), and return a `RenameResult` with `tier="yt_title"`
- **NOTE** noise stripping SHALL NOT be applied. The title's original appearance is preserved, with only unsafe characters swapped for safe lookalikes.

#### Scenario: Auto-rename OFF — separator characters preserved
- **WHEN** auto-rename is OFF AND the title contains separator characters (e.g. `//`, `–`)
- **THEN** the renamer SHALL NOT attempt to split the title into artist/track. Separators are replaced only if they contain unsafe characters (e.g. `/` → `⧸`), but the title structure is preserved as-is.

### NEW Requirement: Visual-equivalent character map

The renamer SHALL maintain a map of filesystem-unsafe ASCII characters to visually identical Unicode replacements:

| Unsafe | Safe | Unicode name |
|--------|------|-------------|
| `/` | `⧸` | BIG SOLIDUS (U+29F8) |
| `\` | `⧹` | BIG REVERSE SOLIDUS (U+29F9) |
| `:` | `꞉` | MODIFIER LETTER COLON (U+A789) |
| `*` | `＊` | FULLWIDTH ASTERISK (U+FF0A) |
| `?` | `？` | FULLWIDTH QUESTION MARK (U+FF1F) |
| `"` | `＂` | FULLWIDTH QUOTATION MARK (U+FF02) |
| `<` | `＜` | FULLWIDTH LESS-THAN SIGN (U+FF1C) |
| `>` | `＞` | FULLWIDTH GREATER-THAN SIGN (U+FF1E) |
| `|` | `｜` | FULLWIDTH VERTICAL LINE (U+FF5C) |

This map SHALL be used:
1. In the passthrough tier (auto-rename OFF)
2. In tier 3 when no separator is found (auto-rename ON)

The map SHALL NOT be used:
1. In tier 1 or tier 2 (those already produce clean names)
2. In tier 3 when a separator IS found (the split-and-reformat logic handles that)

### NEW Requirement: Metadata embedding at download time

After renaming, the renamer SHALL embed metadata into the downloaded file using mutagen:

- **ORIGINAL_TITLE**: the raw YT title before any renaming (MP3: `TXXX` frame with desc `original_title`; Opus: `ORIGINAL_TITLE` Vorbis comment)
- **TITLE**: the resolved filename stem used for the rename (MP3: `TIT2` frame; Opus: `TITLE` Vorbis comment)

This ensures media players (e.g. Jellyfin) display the resolved name rather than the raw YT title.

#### Scenario: Metadata embedded on download
- **WHEN** a file is renamed (any tier, including passthrough)
- **THEN** the renamer SHALL write both `ORIGINAL_TITLE` and `TITLE` into the file's metadata
- **NOTE** only MP3 and Opus formats are supported; other formats are silently skipped

#### Scenario: TITLE updated on manual rename
- **WHEN** a user manually renames an item via API or UI
- **THEN** the rename endpoint SHALL update the `TITLE` metadata field to match the new name
- **NOTE** `ORIGINAL_TITLE` is NOT modified — it always preserves the raw YT title

### NEW Requirement: Remaster noise pattern

The default noise pattern list SHALL include a pattern to strip year-prefixed remaster suffixes: `\d{4}\s*remaster(?:ed)?`

This matches patterns like `(2016 Remaster)`, `(2016 Remastered)`, `[2024 REMASTER]` (case-insensitive via `re.IGNORECASE`).
