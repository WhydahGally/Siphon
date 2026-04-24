## MODIFIED Requirements

### Requirement: Dev dependencies are declared and installable
The project SHALL declare `pytest`, `pytest-asyncio`, `httpx`, and `pytest-rerunfailures` as optional dev dependencies installable via `pip install -e ".[dev]"`.

#### Scenario: Dev install succeeds
- **WHEN** `pip install -e ".[dev]"` is run in a clean virtual environment
- **THEN** `pytest`, `pytest-asyncio`, `httpx`, and `pytest-rerunfailures` are importable

#### Scenario: Pytest configuration exists in pyproject.toml
- **WHEN** `pyproject.toml` is inspected
- **THEN** a `[tool.pytest.ini_options]` section exists with `testpaths = ["tests/unit"]`, `asyncio_mode = "auto"`, and a `markers` list declaring `slow` and `e2e`
