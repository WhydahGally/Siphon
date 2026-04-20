## ADDED Requirements

### Requirement: Unit test suite covers all pure and mockable modules
The project SHALL have a pytest-based unit test suite under `tests/unit/` that covers `progress.py`, `formats.py`, `models.py`, `renamer.py`, `registry.py`, `job_store.py`, `downloader.py` (filter/enumerate), and `api.py` (routes and pure helpers).

#### Scenario: Tests run without network access
- **WHEN** `pytest tests/unit/` is executed in an environment with no network
- **THEN** all tests pass (all external calls are mocked)

#### Scenario: Tests complete within 10 seconds
- **WHEN** the full `tests/unit/` suite is executed
- **THEN** total wall-clock time SHALL be under 10 seconds

#### Scenario: Each module has a dedicated test file
- **WHEN** the `tests/unit/` directory is listed
- **THEN** one test file exists per tested module (`test_progress.py`, `test_formats.py`, `test_models.py`, `test_renamer.py`, `test_registry.py`, `test_job_store.py`, `test_downloader.py`, `test_api.py`)

### Requirement: Tests are isolated from each other and from real state
The test suite SHALL use fixtures to ensure no shared state between tests.

#### Scenario: Registry tests use in-memory SQLite
- **WHEN** any `test_registry.py` test runs
- **THEN** it uses an in-memory SQLite database (`:memory:`) and not the real `.data/` directory

#### Scenario: Renamer module-level state is reset between tests
- **WHEN** a `test_renamer.py` test modifies `_last_mb_request_time`
- **THEN** the next test sees `_last_mb_request_time = 0.0`

#### Scenario: API tests mock all startup side effects
- **WHEN** `test_api.py` creates a `TestClient`
- **THEN** `registry.init_db`, `scheduler.start`, and `scheduler.stop` are patched so no real I/O occurs

### Requirement: Dev dependencies are declared and installable
The project SHALL declare `pytest`, `pytest-asyncio`, and `httpx` as optional dev dependencies installable via `pip install -e ".[dev]"`.

#### Scenario: Dev install succeeds
- **WHEN** `pip install -e ".[dev]"` is run in a clean virtual environment
- **THEN** `pytest`, `pytest-asyncio`, and `httpx` are importable

#### Scenario: Pytest configuration exists in pyproject.toml
- **WHEN** `pyproject.toml` is inspected
- **THEN** a `[tool.pytest.ini_options]` section exists with `testpaths = ["tests/unit"]` and `asyncio_mode = "auto"`

### Requirement: CI runs unit tests on every PR and develop push
The project SHALL have a GitHub Actions workflow that runs `pytest tests/unit/` on every pull request targeting `develop` and on every push to `develop`.

#### Scenario: Workflow triggers on PR
- **WHEN** a pull request targeting `develop` is opened or updated
- **THEN** the `unit-tests` CI job runs automatically

#### Scenario: Workflow triggers on push to develop
- **WHEN** a commit is pushed directly to `develop`
- **THEN** the `unit-tests` CI job runs automatically

#### Scenario: Workflow installs dev dependencies before running tests
- **WHEN** the CI job executes
- **THEN** it runs `pip install -e ".[dev]"` before invoking `pytest`
