## 1. Project Setup

- [x] 1.1 Add `pytest-rerunfailures` to `[dev]` extras in `pyproject.toml`
- [x] 1.2 Add `markers` to `[tool.pytest.ini_options]` in `pyproject.toml` declaring `slow` and `e2e`
- [x] 1.3 Create `tests/e2e/__init__.py`

## 2. Conftest and Fixtures

- [x] 2.1 Create `tests/e2e/conftest.py` with session-scoped pre-flight fixture: check port 8000 conflict and warn on existing files in `downloads/`; prompt Y/N locally, auto-continue on CI
- [x] 2.2 Add session-scoped daemon fixture: `subprocess.Popen("siphon start")`, poll `GET /health` until 200, yield base URL, terminate on teardown
- [x] 2.3 Add session-scoped `POST /factory-reset` call after daemon is ready
- [x] 2.4 Add `base_url` and `http` (requests.Session) fixtures available to all tests
- [x] 2.5 Add `pytest.skip` helper for missing secret env vars (used per-test via `pytest.importorskip`-style guard)

## 3. Health Tests

- [x] 3.1 Create `tests/e2e/test_health.py`: `GET /health` → 200
- [x] 3.2 Add `GET /version` → non-empty `version` string

## 4. Playlist Sync Tests

- [x] 4.1 Create `tests/e2e/test_playlist_sync.py`: add playlist from `SIPHON_E2E_PLAYLIST_URL`, trigger sync, assert items count > 0
- [x] 4.2 Add scenario: sync twice → item count unchanged (no duplicates)
- [x] 4.3 Assert each item has non-empty `video_id` and `title`
- [x] 4.4 Cleanup: `DELETE /playlists/{id}` in fixture teardown

## 5. Scheduler Tests

- [x] 5.1 Create `tests/e2e/test_scheduler.py`: add playlist with `watched=true, interval=15`, wait 20s polling, assert items > 0 without manual sync call
- [x] 5.2 Add scenario: patch interval, assert next fire uses new interval (compare timestamps)
- [x] 5.3 Cleanup: delete playlist in teardown

## 6. Single Video Download Tests

- [x] 6.1 Create `tests/e2e/test_single_video.py` with `@pytest.mark.slow`
- [x] 6.2 `POST /jobs` with `SIPHON_E2E_VIDEO_URL`, poll until job is terminal, assert status is `done`
- [x] 6.3 Assert at least one `.mp3` file exists under `downloads/`
- [x] 6.4 Assert mutagen can open the file and `info.length > 0`
- [x] 6.5 Assert job transitions: poll history for `pending` → `downloading` → `done`

## 7. Cancel Tests

- [x] 7.1 Create `tests/e2e/test_cancel.py` with `@pytest.mark.slow`
- [x] 7.2 `POST /jobs` with a long video URL, wait until job reaches `downloading`, call `DELETE /jobs/{id}`
- [x] 7.3 Poll until job is terminal, assert final status is `cancelled`

## 8. Renamer Tests

- [x] 8.1 Create `tests/e2e/test_renamer.py` with `@pytest.mark.slow`
- [x] 8.2 Download with `auto_rename=true`: assert filename matches `<something> - <something>.<ext>` pattern
- [x] 8.3 Download with `auto_rename=false`: assert filename does NOT contain ` - ` prefix (raw yt-dlp output)
- [x] 8.4 For a video with unsafe chars in title: assert filename contains visual-equivalent Unicode (e.g. `⧸` not `/`)
- [x] 8.5 For a video with noise suffix: assert `(Official Music Video)` or `[Official Audio]` absent from filename

## 9. Renamer Tier Tests

- [x] 9.1 Create `tests/e2e/test_renamer_tiers.py` with `@pytest.mark.slow`
- [x] 9.2 Download `SIPHON_E2E_KNOWN_TRACK_URL` with `auto_rename=true` and `mb_user_agent` set: assert `rename_tier` from `GET /playlists/{id}/items` is `musicbrainz`
- [x] 9.3 Download a video known to have yt metadata artist/track tags: assert `rename_tier=yt_metadata`
- [x] 9.4 Download a video with no reliable metadata: assert `rename_tier=yt_title`

## 10. MusicBrainz Tests

- [x] 10.1 Create `tests/e2e/test_musicbrainz.py` with `@pytest.mark.slow`
- [x] 10.2 After download of `SIPHON_E2E_KNOWN_TRACK_URL`, open file with mutagen and assert `TXXX:original_title` frame is present and non-empty
- [x] 10.3 Assert no HTTP 429 in daemon logs during test run (check log output or SSE stream)

## 11. GitHub Workflow — E2E

- [x] 11.1 Create `.github/workflows/e2e-tests.yml`: triggers on `pull_request` (branches: develop, main) and `workflow_dispatch`
- [x] 11.2 Add steps: checkout, Python 3.12 setup, `apt-get install ffmpeg`, `pip install -e ".[dev]"`
- [x] 11.3 Add step: `pytest tests/e2e/ --reruns 1 --reruns-delay 5` with all four secrets injected as env vars

## 12. GitHub Workflow — yt-dlp Bump Update

- [x] 12.1 Add step to `ytdlp-bump.yml` after `gh pr create`: `gh workflow run e2e-tests.yml --ref chore/bump-ytdlp`

## 13. Notes Update

- [x] 13.1 Update `openspec/notes/automated-testing.md`: rename "Phase 2: Integration Tests" to "Phase 2: E2E Tests" and update the section to reflect all decisions made during explore
