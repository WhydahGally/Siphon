## Why

Downloaded files are named after the raw YouTube video title, which is inconsistent and unsuitable for music libraries. A chained rename strategy — YouTube music metadata → MusicBrainz lookup → original title fallback — produces clean `Artist - Track` names automatically after each download completes.

## What Changes

- `renamer.py`: Replace the no-op `rename_file` stub with a three-tier resolution chain that produces `Artist - Track` formatted filenames.
- `downloader.py`: Register a `post_hooks` entry (separate from the existing `progress_hooks`) that fires after all yt-dlp postprocessors finish, passing the full `info_dict` to the renamer. Progress hooks are untouched.
- `renamer.py` hook signature changes from `rename_file(filepath: str) -> str` to `rename_file(info_dict: dict) -> None`. **BREAKING** for any external callers of `rename_file`.
- New dependency: `requests` (for direct MusicBrainz HTTP calls).

## Capabilities

### New Capabilities
- `auto-renamer`: Three-tier rename chain — resolves artist/track from YT metadata, MusicBrainz, or YT title fallback — and renames the downloaded file to `Artist - Track.ext`. MusicBrainz tier is skipped if no User-Agent is configured.

### Modified Capabilities
- `download-engine`: Registers a `post_hooks` entry in yt-dlp opts. The `rename_file` hook point signature changes to accept `info_dict` instead of a filepath string.

## Impact

- `src/siphon/renamer.py` — full rewrite
- `src/siphon/downloader.py` — add `post_hooks` entry; update `_make_hook` to remove renamer call; update `__main__` CLI to accept optional `--mb-user-agent` arg
- New outbound HTTP calls to `musicbrainz.org/ws/2/` — sequential, rate-limited to 1 req/sec via a global threading lock
- No changes to `progress.py`, `formats.py`, or `progress_hooks` wiring
