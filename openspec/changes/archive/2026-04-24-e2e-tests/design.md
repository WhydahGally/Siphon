## Context

Unit tests exist under `tests/unit/` and run on every PR. They cover pure logic with mocks — no network, no real filesystem, no running daemon. There is no test coverage for the integrated system: real yt-dlp behaviour, actual downloads, scheduler timing, renamer outcomes on real files, or MusicBrainz API responses.

The e2e suite starts the real Siphon daemon as a subprocess and drives it exclusively through its HTTP API (`http://localhost:8000`). Tests assert on HTTP responses, DB state (via API), and filesystem artifacts (files in `downloads/`). The daemon is identical to production — no mocking, no test-mode flag.

## Goals / Non-Goals

**Goals:**
- Validate the full stack end-to-end using the real daemon, real yt-dlp, real YouTube, and real MusicBrainz
- Catch yt-dlp version breakage before it reaches users (primary use case)
- Run on every PR to `develop`/`main` and automatically after yt-dlp bumps
- Distinguish fast (no-download) tests from slow (download) tests via `@pytest.mark.slow`

**Non-Goals:**
- Testing the Vue UI (separate concern, not in scope)
- Replacing unit tests (complementary, not a substitute)
- Hermetic isolation via env vars or test-only data directories (not needed; factory-reset handles state)
- Parallel test execution (sequential is fine; tests share one daemon process)

## Decisions

### D1: Single daemon subprocess, session-scoped

**Decision:** One daemon process per test session, started once in `conftest.py` as a session-scoped autouse fixture.

**Rationale:** Starting a daemon per test would be prohibitively slow. Session scope means all tests share one daemon instance. Factory-reset at session start wipes state. Individual tests that add playlists should clean up via `DELETE /playlists/{id}` (or accept that other tests see it — ordering is controlled by file/test name).

**Alternative considered:** Function-scoped daemon (one per test). Rejected: too slow, 5–10s startup each.

---

### D2: Port 8000 hardcoded, pre-flight check on conflict

**Decision:** Tests always target `http://localhost:8000`. If port 8000 is in use at conftest startup, print a warning and prompt for confirmation locally (auto-continue on CI via `CI` env var).

**Rationale:** Adding a `--port` flag to `siphon start` is application code changes that aren't needed for correctness. The pre-flight check provides enough safety. Users running e2e tests alongside their dev daemon are doing something unusual and should be warned.

**Alternative considered:** Configurable port via env var. Rejected: requires app code changes and adds complexity for a rare local scenario.

---

### D3: Factory-reset at session start, not between tests

**Decision:** `POST /factory-reset` is called once at session startup. Individual tests clean up their own playlists/jobs where needed. Download files in `downloads/` are NOT automatically deleted — the pre-flight warning surfaces any existing files.

**Rationale:** Factory-reset between every test would be very slow (DB reinit + filesystem). Test ordering is deterministic; a one-time reset at the start is sufficient.

---

### D4: Pre-flight fixture for local safety

**Decision:** A session-scoped autouse fixture runs before the daemon starts and checks:
1. Is port 8000 already in use? (`socket.connect_ex`)
2. Does `downloads/` contain any files?

On local: prints warnings and prompts `Press Y to continue`. On CI (`CI=true`): logs warnings and continues without input.

**Rationale:** Prevents silent corruption of a developer's real data by making the conflict visible.

---

### D5: `@pytest.mark.slow` for download tests, no marker for fast tests

**Decision:** Tests that perform real downloads are marked `@pytest.mark.slow`. Tests that only enumerate, sync metadata, or hit the scheduler without downloading are unmarked.

Local developers can run `pytest tests/e2e/ -m "not slow"` for a fast feedback loop (~30s). CI always runs the full suite.

---

### D6: One retry on failure via `pytest-rerunfailures`

**Decision:** CI runs `pytest tests/e2e/ --reruns 1 --reruns-delay 5`. If a test fails twice, the job turns red and requires manual re-trigger.

**Rationale:** YouTube and MusicBrainz are occasionally flaky from CI IPs. One retry catches transient failures without masking real bugs or creating infinite loops.

**Alternative considered:** `continue-on-error: true` at the workflow step level. Rejected: masks real failures.

---

### D7: Secrets for real-world URLs

**Decision:** Playlist/video URLs and MusicBrainz user-agent are stored as GitHub secrets and passed as environment variables to the test process:

| Secret | Purpose |
|---|---|
| `E2E_PLAYLIST_URL` | A small public playlist (~5 items) owned by the repo maintainer |
| `E2E_SINGLE_VIDEO_URL` | A single video for download + MusicBrainz tests (well-known track, < 60s) |
| `E2E_MB_USER_AGENT` | MusicBrainz-compliant user agent string |

Tests skip gracefully if the relevant secret env var is not set (for contributors running locally without secrets).

---

### D8: yt-dlp bump workflow triggers e2e after PR creation

**Decision:** After `ytdlp-bump.yml` creates the bump PR via `gh pr create`, it calls `gh workflow run e2e-tests.yml --ref chore/bump-ytdlp` to trigger e2e on the bump branch. This gives the PR a real e2e signal before merge.

**Rationale:** The yt-dlp bump is the highest-risk event for e2e regressions. Running e2e automatically on the bump branch closes the loop without manual steps.

## Risks / Trade-offs

- **YouTube bot detection on CI IPs** → Mitigated by `--reruns 1`; playlist is small (5 items); manual re-trigger available if both attempts fail
- **MusicBrainz rate limiting** → Mitigated by the existing 1-req/s rate limiter in `renamer.py`; e2e only makes 1–2 MB lookups per run
- **Test pollution between runs (download files accumulate)** → Pre-flight warns; user manually clears `downloads/` before local runs; CI `downloads/` is ephemeral per job
- **Scheduler test relies on real time (20s sleep)** → Accepted; scheduler tests are not marked `@slow` but do add wall-clock time; total session time with downloads is expected to be 2–5 minutes
- **Tests are order-dependent if cleanup is missed** → Factory-reset at session start provides a clean baseline; individual test cleanup is belt-and-suspenders
