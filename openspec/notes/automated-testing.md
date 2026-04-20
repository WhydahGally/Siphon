# Automated Testing

## Current State

- Zero tests, zero test infrastructure
- No pytest in dependencies, no `tests/` directory
- All verification done manually via `python -c` in terminal sessions

## Phase 1: Unit Tests

**Framework:** pytest + pytest-asyncio

**Target:** runs on every PR against develop and on develop pushes.
Speed target: <10 seconds total.

```
tests/
├── conftest.py                ← shared fixtures
├── test_progress.py           ← make_progress_event()
├── test_formats.py            ← DownloadOptions validation
├── test_renamer.py            ← sanitize, strip_noise, tier logic,
│                                 embed_original_title (tmpdir),
│                                 MusicBrainz (mocked HTTP)
├── test_registry.py           ← in-memory SQLite CRUD
├── test_job_store.py          ← JobStore operations, eviction
├── test_models.py             ← DownloadJob/JobItem properties
├── test_watcher_utils.py      ← _parse_bool, _normalise_youtube_url,
│                                 _build_options, _filter_entries
└── test_api.py                ← FastAPI routes via TestClient
                                  (mock registry + job store)
```

### Module testability breakdown

| Module       | Testability | Notes                                                    |
|--------------|-------------|----------------------------------------------------------|
| progress.py  | TRIVIAL     | Pure data transform, no deps, no I/O                     |
| formats.py   | EASY        | Dataclass validation, only shutil.which for ffmpeg check  |
| renamer.py   | MEDIUM      | Pure logic (sanitize, noise strip, tier resolution) but has MusicBrainz HTTP calls & file renames |
| registry.py  | MEDIUM      | SQLite DB, but in-memory `:memory:` makes it easy to isolate |
| downloader   | HARD        | Wraps yt-dlp, needs mocking or integration setup          |
| watcher.py   | HARD        | FastAPI daemon, scheduler, CLI argparse, threading. Splitting planned before adding tests. |

### What's testable in watcher.py without extraction

| What | How | Needs extraction? |
|------|-----|:-:|
| `DownloadJob` properties (`.is_terminal()`, `.done_count`) | Direct import, pure logic | No |
| `JobStore` create/update/evict/cancel | Instantiate in test, no daemon needed | No |
| `_parse_bool()`, `_normalise_youtube_url()`, `_build_options()` | Pure functions | No |
| `_filter_entries()`, `enumerate_entries()` | Mock yt-dlp, test filtering logic | No |
| API routes | `httpx.AsyncClient` with TestClient | Partially — lifespan needs work |
| CLI commands | They hit HTTP, need running daemon or mocking | Yes, eventually |
| Scheduler | Threading + timers + real downloads | Yes, the hardest |

## Phase 2: Integration Tests

**Trigger:** yt-dlp bump workflow + manual dispatch (not on every PR).

```
tests/integration/
├── conftest.py                ← real daemon startup/teardown,
│                                 playlist URLs from env vars
├── test_download_audio.py     ← real download, auto-rename on/off
├── test_download_video.py     ← format/quality combos
├── test_polling.py            ← interval changes, scheduler behavior
└── test_sync_failed.py        ← retry logic with real failures
```

- Playlist URLs stored in GitHub secrets/variables
- Scenarios: auto-rename on/off, polling interval on/off, changing intervals
- Validates against real-world playlists
- Attached to yt-dlp bump workflow to catch breakage from version updates
- Unit tests not needed here — integration-only

## Phase 3: UI Testing (future, optional)

### Approaches

**Option A: Playwright (browser E2E)**
- Real browser, real daemon, real interactions
- Pros: tests actual user experience, catches CSS/layout issues
- Cons: slow, flaky, heavy CI setup, hard to debug

**Option B: Vitest + Vue Test Utils (component unit tests)**
- Individual Vue components in isolation with mocked API
- Pros: fast (milliseconds), deterministic, no browser/daemon needed
- Cons: doesn't catch real integration bugs or CSS/layout issues

**Option C: Playwright Component Testing (hybrid)**
- Renders components in real browser without full app
- Middle ground, newer/less mature ecosystem

### Recommendation

Component tests (Option B) give 80% of value at 5% of cost. Full E2E (Option A) has diminishing returns for a personal tool. If E2E is ever added, keep it minimal — one or two happy-path tests maximum.

Real bug risk is backend (renamer edge cases, download failures, metadata embedding), not frontend. The UI is a thin layer over the API.

## Sequencing

1. **Extract watcher.py** into smaller modules (prerequisite — already needed for maintainability)
2. **Phase 1: Unit tests** for all modules + CI workflow
3. **Phase 2: Integration tests** tied to yt-dlp bump workflow
4. **Phase 3: UI component tests** if/when the UI grows complex enough to warrant it
