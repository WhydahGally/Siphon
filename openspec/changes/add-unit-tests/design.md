## Context

The codebase currently has zero tests. The recent watcher-split change produced five well-isolated modules (`api.py`, `app.py`, `cli.py`, `downloader.py`, `scheduler.py`) alongside the existing pure modules (`progress.py`, `formats.py`, `models.py`, `renamer.py`, `registry.py`, `job_store.py`). This is the right moment to add a unit test layer — the surfaces are stable and the modules are importable in isolation.

This change adds only the unit test layer (`tests/unit/`). Integration tests (`tests/integration/`) are a separate future change.

## Goals / Non-Goals

**Goals:**
- pytest suite covering all pure/mockable modules
- Tests run in CI on every PR and push to `develop`, completing in <10 seconds
- No changes to application source code

**Non-Goals:**
- Integration tests (real yt-dlp, real network, real daemon) — separate change
- UI/component tests — separate future change
- Testing `scheduler.py`, `cli.py`, `app.py` — too coupled to timers, HTTP, or uvicorn

## Decisions

### D1: `tests/unit/` subdirectory (not flat `tests/`)

`tests/unit/` reserves space for `tests/integration/` in the same parent. This is the agreed layout. A root-level `tests/__init__.py` is not needed — pytest discovers by path. Each subdirectory gets its own `conftest.py`.

**Alternative considered:** flat `tests/` with a marker (`@pytest.mark.integration`) to separate later. Rejected because directory separation makes CI filtering trivial (`pytest tests/unit/`) without needing marker maintenance.

### D2: `unittest.mock` for HTTP mocking, not `respx`

MusicBrainz calls in `renamer.py` use `requests.get`. Standard `unittest.mock.patch` is sufficient — no need to add `respx` (an async-first HTTP mock for `httpcore`/`httpx`). This keeps the dependency count low.

**Alternative considered:** `responses` library. Rejected — `unittest.mock.patch("requests.get")` is simpler for a single external call site.

### D3: Registry isolation via `init_db(":memory:")`

`registry.init_db()` accepts a data directory; tests pass a `tmp_path` fixture. Inside the test, we also patch `registry._local` to ensure each test gets a fresh connection. This avoids any shared state between test functions.

**Alternative considered:** Use a real temp SQLite file. Rejected — `:memory:` is faster and guaranteed clean.

### D4: FastAPI `TestClient` (sync) for `test_api.py`

`starlette.testclient.TestClient` runs the ASGI app synchronously in a thread, handling lifespan internally. This avoids needing `pytest-asyncio` for the API tests. The lifespan handler in `api.py` calls `registry.init_db()` and `scheduler.start()` — both are patched in the test conftest so no real I/O occurs.

`pytest-asyncio` is still added as a dependency for completeness (future async tests won't need infrastructure changes), but it is not exercised in this change.

**Alternative considered:** `httpx.AsyncClient` with `pytest-asyncio`. Rejected — adds complexity with no benefit for this change's scope.

### D5: `filter_entries` tested with hand-crafted dicts

`filter_entries` takes a `List[dict]` and a `playlist_id` string; it calls `registry.get_item_ids_for_playlist()` to know which video IDs are already downloaded. The test fixture patches `registry.get_item_ids_for_playlist` and passes raw dicts — no yt-dlp involved.

`enumerate_entries` calls `YoutubeDL.extract_info()` directly. This is integration territory — it is **not** unit tested in this change.

### D6: pytest config in `pyproject.toml`

All pytest settings live in `[tool.pytest.ini_options]`. `testpaths = ["tests/unit"]` scopes discovery to unit tests only (integration tests live in `tests/integration/` and are excluded by default). `asyncio_mode = "auto"` is set so any future async test functions work without decorators.

### D7: Dev dependencies in `pyproject.toml` optional group

```toml
[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "httpx>=0.27"]
```

`requirements.in` gets a `-c requirements.txt` constraint + `siphon[dev]` line to keep the lockfile consistent. Or they're added as direct entries in `requirements.in` under a comment — whichever is consistent with how the project currently manages dev deps. Since `requirements.in` currently lists only runtime deps, dev deps go in `pyproject.toml` optional group only and are installed via `pip install -e ".[dev]"` in CI.

## Risks / Trade-offs

- **`api.py` lifespan patching is fragile** → If the lifespan adds new startup side effects, tests silently miss them. Mitigation: keep `conftest.py` patch list in sync with `api.py` lifespan; document the coupling.
- **`registry` thread-locals complicate isolation** → `registry._local` holds per-thread connections. Patching `init_db` isn't enough if thread-local state leaks between tests. Mitigation: `conftest.py` fixture resets `registry._data_dir` and `registry._local` between tests.
- **`renamer.py` MusicBrainz rate-limit state** → `_last_mb_request_time` is a module-level float. If one test sets it, the next test may see a stale value. Mitigation: reset `renamer._last_mb_request_time = 0.0` in the renamer fixture teardown.
