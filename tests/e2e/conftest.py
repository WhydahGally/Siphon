"""
tests/e2e/conftest.py — Session-level fixtures for the Siphon e2e test suite.

Provides:
  - preflight: warns on port 8000 conflict and existing files in downloads/
  - daemon: starts siphon as a subprocess, factory-resets, yields, terminates
  - base_url: "http://localhost:8000"
  - http: a requests.Session shared across the session
  - require_env(): helper to skip a test when a required secret env var is absent
  - poll_job_terminal(): helper to poll until a job reaches terminal state
  - poll_items_stable(): helper to poll playlist items until the count stabilises
"""
import os
import socket
import subprocess
import sys
import time

import pytest
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DOWNLOADS_DIR = os.path.join(_REPO_ROOT, "downloads")

# Mapping from db key (returned by GET /settings) → api key (used by PUT /settings/{key})
_SETTINGS_DB_TO_API = {
    "mb_user_agent": "mb-user-agent",
    "log_level": "log-level",
    "max_concurrent_downloads": "max-concurrent-downloads",
    "check_interval": "interval",
    "auto_rename_default": "auto-rename",
    "theme": "theme",
    "browser_logs": "browser-logs",
    "title_noise_patterns": "title-noise-patterns",
}


# ---------------------------------------------------------------------------
# Utility helpers (plain functions, not fixtures — call directly in tests)
# ---------------------------------------------------------------------------

def require_env(name: str) -> str:
    """Return the value of an env var, or skip the test if it is not set."""
    value = os.getenv(name)
    if not value:
        pytest.skip(f"Required secret not set: {name}")
    return value


def poll_job_terminal(http: requests.Session, base_url: str, job_id: str, timeout: int = 90) -> dict:
    """Poll GET /jobs until the given job reaches a fully terminal state (all items done/failed/cancelled)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = http.get(f"{base_url}/jobs")
        resp.raise_for_status()
        jobs = {j["job_id"]: j for j in resp.json()}
        if job_id in jobs:
            job = jobs[job_id]
            terminal = {"done", "failed", "cancelled"}
            if all(i["state"] in terminal for i in job["items"]):
                return job
        time.sleep(2)
    pytest.fail(f"Job {job_id} did not reach terminal state within {timeout}s")


def poll_items_stable(http: requests.Session, base_url: str, playlist_id: str, min_count: int = 1, timeout: int = 90) -> list:
    """
    Poll GET /playlists/{id}/items until the item count reaches min_count AND
    stabilises (same count on two consecutive polls separated by 3 s).
    """
    deadline = time.time() + timeout
    prev_count = -1
    while time.time() < deadline:
        resp = http.get(f"{base_url}/playlists/{playlist_id}/items")
        resp.raise_for_status()
        items = resp.json()
        count = len(items)
        if count >= min_count and count == prev_count:
            return items
        prev_count = count
        time.sleep(3)
    pytest.fail(f"Playlist {playlist_id} never reached a stable item count >= {min_count} within {timeout}s")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("localhost", port)) == 0


def _downloads_has_files() -> bool:
    if not os.path.isdir(_DOWNLOADS_DIR):
        return False
    for _root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        if any(not f.startswith(".") for f in files):
            return True
    return False


def _snapshot_downloads() -> set:
    """Return the set of absolute paths for all non-hidden files in downloads/."""
    snapshot: set = set()
    if not os.path.isdir(_DOWNLOADS_DIR):
        return snapshot
    for root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        for f in files:
            if not f.startswith("."):
                snapshot.add(os.path.join(root, f))
    return snapshot


def _cleanup_downloads(before: set) -> None:
    """Delete files created during the test run and prune empty subdirectories."""
    if not os.path.isdir(_DOWNLOADS_DIR):
        return
    for root, _dirs, files in os.walk(_DOWNLOADS_DIR):
        for f in files:
            if f.startswith("."):
                continue
            path = os.path.join(root, f)
            if path not in before:
                try:
                    os.remove(path)
                except OSError:
                    pass
    # Prune empty subdirectories (bottom-up)
    for root, _dirs, _files in os.walk(_DOWNLOADS_DIR, topdown=False):
        if root == _DOWNLOADS_DIR:
            continue
        remaining = [e for e in os.listdir(root) if not e.startswith(".")]
        if not remaining:
            try:
                os.rmdir(root)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def preflight():
    """
    Pre-flight check: warn on port 8000 conflict and existing files in downloads/.
    On CI (CI=true) warnings are printed and execution continues automatically.
    Locally the user is prompted to press Y to continue.
    """
    check_warnings = []
    if _is_port_open(8000):
        check_warnings.append(
            "  WARNING  Port 8000 is already in use -- is your dev daemon running?\n"
            "           Stop it before running e2e tests to avoid conflicts."
        )
    if _downloads_has_files():
        check_warnings.append(
            f"  WARNING  {_DOWNLOADS_DIR} contains existing files.\n"
            "           They will NOT be deleted, but may affect filename assertion tests."
        )

    if check_warnings:
        sys.stderr.write("\n[E2E PRE-FLIGHT]\n")
        for w in check_warnings:
            sys.stderr.write(w + "\n")
        sys.stderr.flush()

        is_ci = os.getenv("CI") == "true"
        if is_ci:
            sys.stderr.write("  Running on CI -- continuing automatically.\n")
            sys.stderr.flush()
        else:
            try:
                with open("/dev/tty") as tty:
                    sys.stderr.write("\nPress Y to continue, or Ctrl-C to abort: ")
                    sys.stderr.flush()
                    answer = tty.readline().strip().lower()
            except (KeyboardInterrupt, OSError):
                pytest.exit("E2E pre-flight aborted.", returncode=1)
            if answer != "y":
                pytest.exit("E2E pre-flight aborted by user.", returncode=1)


@pytest.fixture(scope="session", autouse=True)
def daemon(preflight):
    """
    Start the Siphon daemon as a subprocess, wait for it to become healthy,
    POST /factory-reset for a clean slate, then yield.
    Terminates the daemon after the session.
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "siphon", "start"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=_REPO_ROOT,
    )

    # Poll until healthy (up to 30 s)
    session = requests.Session()
    deadline = time.time() + 30
    healthy = False
    while time.time() < deadline:
        try:
            r = session.get(f"{BASE_URL}/health", timeout=2)
            if r.status_code == 200:
                healthy = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    if not healthy:
        proc.terminate()
        proc.wait()
        pytest.fail("Siphon daemon did not become healthy within 30 seconds.")

    # Factory reset -- wipe any leftover state from previous runs
    session.post(f"{BASE_URL}/factory-reset")

    # Snapshot settings and existing downloads so we can restore them after the run
    settings_snapshot = session.get(f"{BASE_URL}/settings").json()
    session.close()
    downloads_snapshot = _snapshot_downloads()

    yield

    # --- Teardown: restore settings and clean up downloaded files ---
    restore = requests.Session()
    try:
        current = restore.get(f"{BASE_URL}/settings").json()
        for db_key, original_value in settings_snapshot.items():
            if current.get(db_key) != original_value:
                api_key = _SETTINGS_DB_TO_API.get(db_key)
                if api_key:
                    restore.put(f"{BASE_URL}/settings/{api_key}", json={"value": original_value})
    finally:
        restore.close()

    _cleanup_downloads(downloads_snapshot)

    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session")
def base_url(daemon) -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def http(daemon) -> requests.Session:
    session = requests.Session()
    yield session
    session.close()
