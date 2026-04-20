## Why

Siphon has zero automated tests. All verification is done manually via one-off `python -c` terminal snippets. As the codebase grows — and especially now that `watcher.py` has been split into well-isolated modules — adding unit tests locks in correct behaviour, prevents regressions on every PR, and makes future refactors safe.

## What Changes

- Add a `tests/unit/` directory with pytest test files covering all pure and mockable modules
- Add `pytest` and `pytest-asyncio` as dev dependencies in `pyproject.toml` and `requirements.in`/`requirements.txt`
- Add a `pyproject.toml` `[tool.pytest.ini_options]` section configuring test discovery and asyncio mode
- Add a GitHub Actions CI workflow (`.github/workflows/unit-tests.yml`) that runs on every PR and push to `develop`
- **No changes to application source code**

## Capabilities

### New Capabilities

- `unit-tests`: pytest test suite covering `progress.py`, `formats.py`, `models.py`, `renamer.py`, `registry.py`, `job_store.py`, `downloader.py` (filter/enumerate), and `api.py` (routes + pure helpers); includes CI workflow and pytest configuration

### Modified Capabilities

_(none — no existing spec-level requirements change)_

## Impact

- **New files**: `tests/unit/conftest.py`, `tests/unit/test_progress.py`, `tests/unit/test_formats.py`, `tests/unit/test_models.py`, `tests/unit/test_renamer.py`, `tests/unit/test_registry.py`, `tests/unit/test_job_store.py`, `tests/unit/test_downloader.py`, `tests/unit/test_api.py`, `.github/workflows/unit-tests.yml`
- **Modified files**: `pyproject.toml` (dev deps + pytest config), `requirements.in`, `requirements.txt`
- **Not tested** (too coupled to I/O or external processes): `downloader.download()`, `downloader.sync_parallel()`, `scheduler.py`, `cli.py`, `app.py`
- **Dependencies added**: `pytest`, `pytest-asyncio`, `httpx` (for FastAPI `TestClient`), `respx` or `unittest.mock` (for MusicBrainz HTTP mocking)
