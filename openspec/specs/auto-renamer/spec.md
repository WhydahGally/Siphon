## ADDED Requirements

### Requirement: Three-tier rename chain
After a file is fully downloaded and postprocessed, the renamer SHALL attempt to resolve a clean `Artist - Track` name by trying three strategies in order. The first strategy that produces a confident result SHALL be used. The file on disk SHALL be renamed to the resolved name, preserving its extension. The renamer SHALL return a `RenameResult` dataclass on every code path.

`RenameResult` fields:
- `original_title` (str): the raw YT title from `info_dict['title']`
- `final_name` (str): the resolved filename stem (no extension)
- `tier` (str): one of `"yt_metadata"`, `"musicbrainz"`, `"yt_title_fallback"`
- `new_path` (str): absolute path to the renamed file on disk

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

#### Scenario: Tier 1 and tier 2 fail — tier 3 fallback
- **WHEN** neither tier 1 nor tier 2 produces a result
- **THEN** the renamer SHALL apply noise stripping to the sanitized YT video title and use the result as the filename, returning a `RenameResult` with `tier="yt_title_fallback"`

#### Scenario: No filepath available
- **WHEN** `info_dict` contains no `filepath` or `filename`
- **THEN** the renamer SHALL log a warning and return `None` (existing behaviour preserved)

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
The rename chain SHALL only execute when explicitly enabled. Enabling without opt-in must not alter existing download behaviour.

#### Scenario: Auto-rename disabled (default)
- **WHEN** `auto_rename=False` (the default) is passed to `download()`
- **THEN** no rename shall occur; downloaded files retain the yt-dlp output template names

#### Scenario: Auto-rename enabled
- **WHEN** `auto_rename=True` is passed to `download()`
- **THEN** the three-tier rename chain SHALL run for every file in the session
