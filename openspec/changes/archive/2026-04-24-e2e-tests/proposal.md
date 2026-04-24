## Why

Unit tests cover pure logic in isolation, but can't catch breakage from real YouTube API changes, yt-dlp version updates, or filesystem interactions. An end-to-end test suite validates the full system — daemon, downloader, renamer, scheduler, and MusicBrainz — against real-world URLs, giving confidence that the product actually works before merges and after dependency bumps.

## What Changes

- New `tests/e2e/` test suite using pytest, covering the running daemon via its HTTP API
- Pre-flight fixture: warns on port 8000 conflicts and existing files in `downloads/`, prompts Y/N locally, auto-continues on CI
- Factory-reset via API in session fixture to ensure clean state before each run
- `@pytest.mark.slow` marker on download-heavy tests; fast tests (sync, health, scheduler) run unmarked
- `pytest-rerunfailures` added as a dev dependency; CI runs with `--reruns 1 --reruns-delay 5`
- New `e2e-tests.yml` GitHub Actions workflow: triggers on every PR to `develop`/`main` and on `workflow_dispatch`; installs ffmpeg, runs full suite with one retry
- Updated `ytdlp-bump.yml`: after PR creation, triggers e2e workflow on the bump branch via `gh workflow run`
- Real playlist/video URLs and MusicBrainz user-agent sourced from GitHub secrets: `SIPHON_E2E_PLAYLIST_URL`, `SIPHON_E2E_VIDEO_URL`, `SIPHON_E2E_KNOWN_TRACK_URL`, `SIPHON_E2E_MB_USER_AGENT`

## Capabilities

### New Capabilities

- `e2e-tests`: End-to-end test suite covering daemon health, playlist sync, scheduler interval firing, single-video download, job cancellation, renamer (on/off, unsafe chars, noise stripping), renamer tier tracking (yt_metadata / musicbrainz / yt_title), MusicBrainz lookup and ID3 tag embedding, and CI workflows
- `e2e-ci`: GitHub Actions workflow for e2e tests triggered on PRs and yt-dlp bumps

### Modified Capabilities

- `unit-tests`: `pyproject.toml` updated to declare `e2e` markers and add `pytest-rerunfailures` to dev deps; `[tool.pytest.ini_options]` updated to register custom markers

## Impact

- `tests/e2e/` directory created (new)
- `.github/workflows/e2e-tests.yml` created (new)
- `.github/workflows/ytdlp-bump.yml` updated (minor — trigger e2e after PR creation)
- `pyproject.toml` updated: `pytest-rerunfailures` in `[dev]` extras, custom marker declarations
- No changes to application source code
