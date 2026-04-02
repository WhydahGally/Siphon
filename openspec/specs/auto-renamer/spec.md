## ADDED Requirements

### Requirement: Three-tier rename chain
After a file is fully downloaded and postprocessed, the renamer SHALL attempt to resolve a clean `Artist - Track` name by trying three strategies in order. The first strategy that produces a confident result SHALL be used. The file on disk SHALL be renamed to the resolved name, preserving its extension.

#### Scenario: Tier 1 resolves — YT metadata has artist and track
- **WHEN** `info_dict` contains non-empty `artist` AND `track` fields
- **THEN** the renamer SHALL produce the name `"{artist} - {track}"` and rename the file without making any network call

#### Scenario: Tier 1 resolves — multi-artist field
- **WHEN** `info_dict['artist']` contains a comma-separated list of multiple artists (as YouTube Music sometimes provides)
- **THEN** the renamer SHALL resolve a single primary artist name before forming the output. If one of the names matches the channel/uploader exactly, that name is used. Otherwise the first entry is used.

#### Scenario: Tier 1 fails, tier 1.5 resolves — YT title contains a separator
- **WHEN** `info_dict` lacks `artist` or `track`, AND the YT title contains a recognised separator (`⧸⧸`, `//`, `–`, `—`, or `-`) with non-empty text on both sides
- **THEN** the renamer SHALL split the title at the first matching separator (checked in that reliability order), treat the left side as the artist and the right side as the track, and rename the file without making any network call

#### Scenario: Tier 1 fails, tier 2 resolves — MusicBrainz returns confident match
- **WHEN** `info_dict` lacks `artist` or `track`, AND tier 1.5 did not match, AND `mb_user_agent` is configured, AND the top MusicBrainz result has score ≥ 85 AND token overlap with the YT title ≥ 0.4
- **THEN** the renamer SHALL produce the name from the MusicBrainz result and rename the file

#### Scenario: Tier 1 fails, tier 2 skipped — no user-agent configured
- **WHEN** `info_dict` lacks `artist` or `track`, AND `mb_user_agent` is not configured
- **THEN** the renamer SHALL skip tier 2 entirely, log a DEBUG message, and fall through to tier 3

#### Scenario: Tier 1 fails, tier 2 returns low-confidence result
- **WHEN** `info_dict` lacks `artist` or `track`, AND the MusicBrainz top result score is below 85 OR token overlap is below 0.4
- **THEN** the renamer SHALL discard the MusicBrainz result and fall through to tier 3

#### Scenario: Tier 1 and tier 2 fail — tier 3 fallback
- **WHEN** neither tier 1 nor tier 2 produces a result
- **THEN** the renamer SHALL use the sanitized YT video title as the filename

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

### Requirement: MusicBrainz token overlap scoring
The renamer SHALL compute token overlap between the MusicBrainz result and the YouTube title to guard against high-scoring but incorrect matches. The check is directional and independent: the MB artist tokens are checked against the YT title, and the MB track title tokens are checked against the YT title separately. This prevents false positives from cover recordings whose titles contain the original artist's name (e.g. "Space Song (Beach House)" by Miles McLaughlin).

#### Scenario: Token overlap meets threshold for both artist and track
- **WHEN** at least 40% of the lowercased, punctuation-stripped word tokens of the MB primary artist are present in the YT title **AND** at least 40% of the MB recording title tokens are present in the YT title
- **THEN** the MB result MAY be accepted (subject to score threshold also being met)

#### Scenario: Artist token overlap below threshold
- **WHEN** fewer than 40% of the MB primary artist's tokens appear in the YT title
- **THEN** the renamer SHALL discard the MB result regardless of its score and fall through to tier 3

#### Scenario: Track token overlap below threshold
- **WHEN** fewer than 40% of the MB recording title's tokens appear in the YT title
- **THEN** the renamer SHALL discard the MB result regardless of its score and fall through to tier 3
---

### Requirement: Opt-in rename activation
The rename chain SHALL only execute when explicitly enabled. Enabling without opt-in must not alter existing download behaviour.

#### Scenario: Auto-rename disabled (default)
- **WHEN** `auto_rename=False` (the default) is passed to `download()`
- **THEN** no rename shall occur; downloaded files retain the yt-dlp output template names

#### Scenario: Auto-rename enabled
- **WHEN** `auto_rename=True` is passed to `download()`
- **THEN** the four-tier rename chain SHALL run for every file in the session
