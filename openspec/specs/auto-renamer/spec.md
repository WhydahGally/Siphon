## Requirements

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

---

### Requirement: MusicBrainz phrase-match validator
The renamer SHALL validate MusicBrainz results using phrase-based substring matching against the YouTube title. Two acceptance paths are supported. Both require MB score ≥ 85.

Normalization for all comparisons: lowercase the string, replace all non-alphanumeric characters (punctuation, separators) with a single space, collapse consecutive spaces.

**BOTH_IN_TITLE path:**
- normalized(mb_primary_artist) is a contiguous substring of normalized(yt_title)
- AND normalized(mb_track) is a contiguous substring of (normalized(yt_title) with the first occurrence of normalized(mb_primary_artist) removed)

**UPLOADER_MATCH path:**
- normalized(mb_track) is a contiguous substring of normalized(yt_title) with the first occurrence of normalized(mb_primary_artist) removed (consistent with the BOTH_IN_TITLE artist-exclusion step; in practice a no-op when the artist is not in the title)
- AND normalized(uploader) equals normalized(mb_primary_artist) exactly

If neither path passes, the result SHALL be rejected.

#### Scenario: Both artist and track found in title — BOTH_IN_TITLE
- **WHEN** the normalized MB artist appears as a substring in the normalized title AND the normalized MB track appears as a substring in the normalized title (after artist removal)
- **THEN** the validator SHALL accept the result via BOTH_IN_TITLE

#### Scenario: Artist not in title but uploader matches — UPLOADER_MATCH
- **WHEN** the normalized MB track appears in the normalized title AND the normalized channel uploader equals the normalized MB primary artist exactly
- **THEN** the validator SHALL accept the result via UPLOADER_MATCH

#### Scenario: Cover song — artist name not in title, uploader does not match
- **WHEN** the MB result's artist name is not present in the title AND the uploader does not equal the MB artist
- **THEN** the validator SHALL reject the result and the renamer SHALL fall through to tier 3

#### Scenario: Scrambled words do not pass track check
- **WHEN** the MB track title is `"This is a song"` and the YT title contains the words in a different order (e.g. `"Artist - This a song is"`)
- **THEN** the substring check SHALL fail and the result SHALL be rejected

#### Scenario: Score below threshold — rejected regardless of text match
- **WHEN** the MB result score is below 85
- **THEN** the validator SHALL reject the result regardless of phrase matching results

---

### Requirement: YT noise stripping
The renamer SHALL expose a `strip_noise(title, patterns)` function that strips common YouTube title suffixes from a string. The function SHALL apply the noise patterns iteratively until no further matches are found (handles multiple suffixes). Noise stripping SHALL be applied:
1. To the cleaned title before sending it as a MusicBrainz query input
2. To the final resolved filename at the end of every tier before emitting `RenameResult`

The active pattern list SHALL be sourced from the `title-noise-patterns` settings key if set; otherwise the built-in default list SHALL be used.

Patterns match suffixes of the form `(pattern)` or `[pattern]` (case-insensitive). The outer bracket wrapper is fixed; only the inner content is configurable.

#### Scenario: Noise suffix stripped from MB query input
- **WHEN** the YT title is `"Pearl Jam - Black (Official Audio)"`
- **THEN** the title sent to MusicBrainz SHALL be `"Pearl Jam - Black"`

#### Scenario: Noise suffix stripped from final filename
- **WHEN** tier 3 fallback is reached and the YT title is `"Wicked Game (Official Video)"`
- **THEN** the emitted `final_name` SHALL be `"Wicked Game"` (not `"Wicked Game (Official Video)"`)

#### Scenario: Multiple noise suffixes stripped
- **WHEN** the title is `"Song Name [HD] (Official Audio)"`
- **THEN** both suffixes SHALL be stripped, resulting in `"Song Name"`

#### Scenario: No noise suffix present
- **WHEN** the title contains no recognised noise suffix
- **THEN** the title SHALL be returned unchanged

#### Scenario: Non-noise brackets preserved
- **WHEN** the title is `"Street Spirit (Fade Out)"`
- **THEN** the title SHALL be returned unchanged (the suffix is not in the noise list)

### Requirement: Separator detected — INFO log
When the cleaned YT title contains any of the recognised separator characters (`⧸⧸`, `//`, `–`, `—`, `-`), the renamer SHALL log a single INFO-level message before issuing the MusicBrainz query. This log is diagnostic only and does not alter any code path.

#### Scenario: Separator character present in title
- **WHEN** the cleaned title contains `//`, `⧸⧸`, `–`, `—`, or ` - `
- **THEN** the renamer SHALL emit an INFO log: `"renamer: separator detected in title — using free-text MB query"`

#### Scenario: No separator present
- **WHEN** the cleaned title contains none of the recognised separator characters
- **THEN** no separator log line SHALL be emitted

---

### Requirement: Featured artist formatting
When a MusicBrainz recording has multiple entries in its `artist-credit` list, the renamer SHALL include featured artists in the output name.

#### Scenario: Single artist in MB result
- **WHEN** the MusicBrainz recording has exactly one artist credit
- **THEN** the output SHALL be `"Artist - Track"` with no featuring suffix

#### Scenario: Multiple artists in MB result
- **WHEN** the MusicBrainz recording has more than one artist credit
- **THEN** the output SHALL be `"PrimaryArtist - Track feat. Artist2"` where additional artists are joined with `, ` if more than two featured

---

### Requirement: Filename sanitization
The resolved name SHALL be sanitized before use as a filename by stripping characters that are illegal on common filesystems.

#### Scenario: Name contains filesystem-unsafe characters
- **WHEN** the resolved name contains any of `/ \ : * ? " < > |`
- **THEN** the renamer SHALL strip those characters before constructing the final filename

#### Scenario: Name is safe
- **WHEN** the resolved name contains no filesystem-unsafe characters
- **THEN** the renamer SHALL use it unchanged

---

### Requirement: File extension preserved
The rename operation SHALL preserve the original file extension.

#### Scenario: File has an extension
- **WHEN** the original file is `some-title.mp3`
- **THEN** the renamed file SHALL be `Artist - Track.mp3`

---

### Requirement: Rename failure is non-fatal
If the rename operation fails (e.g. permissions error, file not found), the renamer SHALL log a WARNING and leave the original file untouched. It SHALL NOT raise an exception that would abort the download session.

#### Scenario: OS rename fails
- **WHEN** `os.rename()` raises an `OSError`
- **THEN** the renamer SHALL catch the exception, log a WARNING with the original path and error, and return without aborting

---

### Requirement: MusicBrainz User-Agent configuration
The MusicBrainz tier SHALL only be active when a User-Agent string has been supplied. The User-Agent is passed as the `mb_user_agent` parameter to the rename chain and is set once per download session via the `--mb-user-agent` CLI argument.

#### Scenario: User-Agent provided
- **WHEN** `--mb-user-agent` is passed at CLI and is non-empty
- **THEN** the renamer SHALL include tier 2 in the chain for all files in that session

#### Scenario: User-Agent not provided
- **WHEN** `--mb-user-agent` is absent or empty
- **THEN** the renamer SHALL skip tier 2 for all files in that session and log a single DEBUG message at session start

---

### Requirement: MusicBrainz rate limiting
The renamer SHALL enforce a maximum of one MusicBrainz HTTP request per second across all concurrent callers within the same process.

#### Scenario: Single caller makes sequential requests
- **WHEN** two MusicBrainz lookups are made in sequence
- **THEN** the second request SHALL NOT be sent until at least 1 second has elapsed since the first

#### Scenario: Multiple concurrent callers attempt MB lookup simultaneously
- **WHEN** multiple threads attempt a MusicBrainz lookup at the same time
- **THEN** requests SHALL be serialized via a global lock such that no two requests are sent within the same 1-second window

---

### Requirement: MusicBrainz network failure handling
If the MusicBrainz HTTP request fails for any reason (network error, timeout, non-200 response), the renamer SHALL fall through to tier 3 without aborting.

#### Scenario: Network error during MB lookup
- **WHEN** the HTTP request to MusicBrainz raises a `requests.RequestException`
- **THEN** the renamer SHALL log a WARNING and proceed to tier 3

#### Scenario: MusicBrainz returns non-200 response
- **WHEN** the HTTP response status code is not 200
- **THEN** the renamer SHALL log a WARNING and proceed to tier 3

---

### Requirement: Opt-in rename activation
A rename post-processor SHALL always be registered, regardless of the `auto_rename` flag. The flag controls which rename path is taken.

#### Scenario: Auto-rename disabled (default)
- **WHEN** `auto_rename=False` (the default) is passed to `download()`
- **THEN** the passthrough rename SHALL run (visual-equivalent char map only, no noise stripping, no MusicBrainz); files are renamed to match the DB

#### Scenario: Auto-rename enabled
- **WHEN** `auto_rename=True` is passed to `download()`
- **THEN** the three-tier rename chain SHALL run for every file in the session

---

### Requirement: Passthrough rename when auto-rename is OFF

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

---

### Requirement: Visual-equivalent character map

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

---

### Requirement: Metadata embedding at download time

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

---

### Requirement: Remaster noise pattern

The default noise pattern list SHALL include a pattern to strip year-prefixed remaster suffixes: `\d{4}\s*remaster(?:ed)?`

This matches patterns like `(2016 Remaster)`, `(2016 Remastered)`, `[2024 REMASTER]` (case-insensitive via `re.IGNORECASE`).
