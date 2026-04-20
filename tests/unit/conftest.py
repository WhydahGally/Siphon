"""
Shared fixtures for the unit test suite.
"""
import threading
from unittest.mock import patch

import pytest

from siphon import registry
from siphon import renamer


# ---------------------------------------------------------------------------
# Registry fixture — fresh in-process SQLite per test
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    """
    Initialise the registry against a fresh temp directory for each test.
    Resets all thread-local and module-level state after the test.
    """
    registry.init_db(str(tmp_path))
    yield tmp_path
    # Teardown: close thread-local connection and reset globals.
    conn = getattr(registry._local, "conn", None)
    if conn is not None:
        conn.close()
    registry._local = threading.local()
    registry._data_dir = None


# ---------------------------------------------------------------------------
# Renamer fixture — reset module-level rate-limit state per test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=False)
def reset_mb_ratelimit():
    """Reset MusicBrainz rate-limit timestamp before and after each test."""
    renamer._last_mb_request_time = 0.0
    yield
    renamer._last_mb_request_time = 0.0


# ---------------------------------------------------------------------------
# API client fixture — TestClient with lifespan mocked
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client(tmp_path):
    """
    Return a Starlette TestClient for the FastAPI app.

    Patches:
    - _resolve_data_dir → tmp_path (so registry.init_db writes there)
    - PlaylistScheduler.start / .stop → no-ops (no real timers)
    """
    from starlette.testclient import TestClient
    from siphon.api import app

    with (
        patch("siphon.api._resolve_data_dir", return_value=str(tmp_path)),
        patch("siphon.scheduler.PlaylistScheduler.start"),
        patch("siphon.scheduler.PlaylistScheduler.stop"),
    ):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client
