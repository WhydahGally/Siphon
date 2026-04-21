# Automated Testing

## Current State

- Zero tests, zero test infrastructure
- No pytest in dependencies, no `tests/` directory
- All verification done manually via `python -c` in terminal sessions
- `watcher.py` has been split into `api.py`, `app.py`, `cli.py`, `downloader.py`, `scheduler.py`

## Phase 1: Unit Tests

**Framework:** pytest + pytest-asyncio

**Target:** runs on every PR against develop and on develop pushes.
Speed target: <10 seconds total.

`pytest-asyncio` is included in deps for potential async API client use in `test_api.py`.
For `test_job_store.py`, only the synchronous operations (create/update/evict/cancel) are
tested here — the SSE queue subscription path is covered implicitly via `test_api.py`'s
SSE route tests through the sync `TestClient`.

```
tests/
└── unit/
    ├── conftest.py            ← shared fixtures (in-memory registry, tmp dirs)
    ├── test_progress.py       ← make_progress_event()
    ├── test_formats.py        ← DownloadOptions validation,
    │                             build_video_format_selector(),
    │                             build_audio_postprocessors(),
    │                             build_options()
    ├── test_models.py         ← DownloadJob/JobItem properties
    │                             (.done_count, .failed_count, .is_terminal()),
    │                             Pydantic model validation
    ├── test_renamer.py        ← sanitize(), strip_noise(),
    │                             resolve_file_path(), extract_extension(),
    │                             update_title_metadata(),
    │                             embed_original_title() (tmpdir),
    │                             MusicBrainz tier (mocked HTTP)
    ├── test_registry.py       ← in-memory SQLite CRUD
    ├── test_job_store.py      ← JobStore create/update/evict/cancel
    │                             (sync operations only; no event loop needed)
    ├── test_downloader.py     ← filter_entries() with hand-crafted dicts,
    │                             enumerate_entries() with mocked yt-dlp
    └── test_api.py            ← FastAPI routes via TestClient,
                                  _normalise_youtube_url() (pure helper)
```

### Module testability breakdown (post-watcher-split)

| Module        | Testability | Notes                                                                  |
|---------------|-------------|------------------------------------------------------------------------|
| progress.py   | TRIVIAL     | Pure data transform, zero deps, zero I/O                               |
| formats.py    | EASY        | Dataclass validation; only external dep is `shutil.which` (ffmpeg)    |
| models.py     | TRIVIAL     | Pure dataclass properties + Pydantic validation; zero I/O              |
| renamer.py    | MEDIUM      | Pure logic (sanitize, noise strip, file path resolution) + MusicBrainz HTTP (mock) + file I/O (tmpdir) |
| registry.py   | MEDIUM      | SQLite CRUD; use `:memory:` for full isolation                         |
| job_store.py  | MEDIUM      | Threading + asyncio.Queue bridge; sync ops testable without event loop |
| downloader.py | HARD        | `filter_entries` testable with hand-crafted dicts; `download`/`sync_parallel` wrap yt-dlp deeply — integration only |
| api.py        | MEDIUM      | Routes via sync `TestClient`; `_normalise_youtube_url` is a pure importable helper |
| scheduler.py  | HARD        | threading.Timer + live sync_fn; skip for unit tests                    |
| cli.py        | SKIP        | Thin HTTP clients — require running daemon; skip for unit tests         |
| app.py        | SKIP        | Argparse wiring + uvicorn startup; no pure logic to test               |

### What moved from watcher.py

| Old (watcher.py)         | Now                                          |
|--------------------------|----------------------------------------------|
| `_parse_bool()`          | Removed (no longer needed)                   |
| `_normalise_youtube_url()` | `api.py` — private helper, still pure      |
| `_build_options()`       | `formats.build_options()` — public           |
| `_filter_entries()`      | `downloader.filter_entries()` — public       |
| `enumerate_entries()`    | `downloader.enumerate_entries()` — public    |

`test_watcher_utils.py` (from the original plan) is superseded by `test_downloader.py`
and coverage of `_normalise_youtube_url` in `test_api.py`.

## Phase 2: E2E Tests

**Trigger:** Every PR to `develop`/`main`, `workflow_dispatch`, and automatically after yt-dlp bump PR creation.
**Retry:** `--reruns 1 --reruns-delay 5` — one retry on failure, then manual re-trigger.

### Key decisions

- No env var isolation — factory-reset via `POST /factory-reset` in session fixture wipes DB state
- Port 8000 hardcoded; pre-flight warns if dev daemon already running
- Pre-flight prompts Y/N locally; auto-continues on CI (`CI=true`)
- `@pytest.mark.slow` on download-heavy tests; run `pytest tests/e2e/ -m "not slow"` locally for fast iteration
- Real URLs and MusicBrainz user-agent in GitHub secrets: `SIPHON_E2E_PLAYLIST_URL`, `SIPHON_E2E_VIDEO_URL`, `SIPHON_E2E_KNOWN_TRACK_URL`, `SIPHON_E2E_MB_USER_AGENT`
- Tests skip gracefully when required secrets are absent

```
tests/
└── e2e/
    ├── conftest.py              ← pre-flight, daemon subprocess, factory-reset,
    │                               base_url/http fixtures, require_env(),
    │                               poll_job_terminal(), poll_items_stable()
    ├── test_health.py           ← GET /health, GET /version
    ├── test_playlist_sync.py    ← registration (fast), sync populates items (@slow),
    │                               no duplicates on second sync (@slow)
    ├── test_scheduler.py        ← auto-sync with short interval (@slow),
    │                               interval change takes effect on next cycle (@slow)
    ├── test_single_video.py     ← POST /jobs, file on disk, mutagen duration > 0,
    │                               job state transitions (@slow)
    ├── test_cancel.py           ← cancel-all mid-flight, pending → cancelled (@slow)
    ├── test_renamer.py          ← auto_rename on/off, unsafe chars → visual Unicode,
    │                               noise suffix stripped (@slow)
    ├── test_renamer_tiers.py    ← musicbrainz / yt_metadata / yt_title tiers (@slow)
    └── test_musicbrainz.py      ← TXXX:original_title embedded in ID3, no 429 (@slow)
```

### CI workflows

- **`e2e-tests.yml`** — new workflow: triggers on PRs + manual dispatch, runs `pytest tests/e2e/ --reruns 1 --reruns-delay 5`
- **`ytdlp-bump.yml`** — updated: triggers `gh workflow run e2e-tests.yml --ref chore/bump-ytdlp` after bump PR is created

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

1. ~~**Extract watcher.py** into smaller modules~~ ✓ Done
2. ~~**Phase 1: Unit tests** — `tests/unit/` + CI workflow on every PR~~ ✓ Done
3. **Phase 2: E2E tests** — `tests/e2e/` + `e2e-tests.yml` + `ytdlp-bump.yml` update
4. **Phase 3: UI component tests** if/when the UI grows complex enough to warrant it
