## MODIFIED Requirements

### Requirement: Three-tier rename chain
After a file is fully downloaded and postprocessed, the renamer SHALL attempt to resolve a clean `Artist - Track` name by trying three strategies in order. The first strategy that produces a confident result SHALL be used. The file on disk SHALL be renamed to the resolved name, preserving its extension. The renamer SHALL return a `RenameResult` dataclass on every code path.

`RenameResult` fields:
- `original_title` (str): the raw YT title from `info_dict['title']`
- `final_name` (str): the resolved filename stem (no extension)
- `tier` (str): one of `"yt_metadata"`, `"musicbrainz"`, `"yt_title_fallback"`, `"manual"`
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

#### Scenario: Tier 1 and tier 2 fail — tier 3 fallback
- **WHEN** neither tier 1 nor tier 2 produces a result
- **THEN** the renamer SHALL apply noise stripping to the sanitized YT video title and use the result as the filename, returning a `RenameResult` with `tier="yt_title_fallback"`

#### Scenario: No filepath available
- **WHEN** `info_dict` contains no `filepath` or `filename`
- **THEN** the renamer SHALL log a warning and return `None` (existing behaviour preserved)

#### Scenario: Manual tier is not produced by auto-rename
- **WHEN** the auto-rename chain runs during download
- **THEN** the tier SHALL never be `"manual"` — that value is reserved for post-download user overrides
