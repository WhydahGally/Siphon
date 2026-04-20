import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from siphon.models import ItemRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

# _data_dir is set at init_db() time and never changes. Thread-safe to read.
_data_dir: Optional[str] = None

# Each thread gets its own connection via thread-local storage.
# Main-thread connection is used for CLI commands; FastAPI worker threads each
# get their own lazily-created connection. WAL mode allows concurrent readers
# and serialises writers internally without a Python-level lock.
_local = threading.local()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS playlists (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    url                 TEXT NOT NULL,
    format              TEXT NOT NULL DEFAULT 'mp3',
    quality             TEXT NOT NULL DEFAULT 'best',
    output_dir          TEXT NOT NULL,
    auto_rename         INTEGER NOT NULL DEFAULT 0,
    watched             INTEGER NOT NULL DEFAULT 1,
    check_interval_secs INTEGER,
    added_at            TEXT NOT NULL,
    last_synced_at      TEXT
);

CREATE TABLE IF NOT EXISTS items (
    video_id       TEXT NOT NULL,
    playlist_id    TEXT NOT NULL REFERENCES playlists(id),
    yt_title       TEXT NOT NULL,
    renamed_to     TEXT,
    rename_tier    TEXT,
    uploader       TEXT,
    channel_url    TEXT,
    duration_secs  INTEGER,
    downloaded_at  TEXT NOT NULL,
    PRIMARY KEY (video_id, playlist_id)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS failed_downloads (
    video_id         TEXT NOT NULL,
    playlist_id      TEXT NOT NULL,
    yt_title         TEXT NOT NULL,
    url              TEXT NOT NULL,
    error_message    TEXT,
    attempt_count    INTEGER NOT NULL DEFAULT 1,
    last_attempted_at TEXT NOT NULL,
    PRIMARY KEY (video_id, playlist_id)
);

CREATE TABLE IF NOT EXISTS ignored_items (
    video_id    TEXT NOT NULL,
    playlist_id TEXT NOT NULL DEFAULT '',
    reason      TEXT,
    ignored_at  TEXT NOT NULL,
    PRIMARY KEY (video_id, playlist_id)
);
"""


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db(data_dir: str) -> None:
    """
    Initialise the registry.

    Creates .data/ on first run, opens (or creates) siphon.db, enables WAL
    mode, and applies the schema. Safe to call multiple times — idempotent.
    """
    global _data_dir

    _data_dir = data_dir
    os.makedirs(data_dir, exist_ok=True)

    # Open a connection on the calling thread and run schema/migrations.
    conn = _open_conn(data_dir)
    # WAL mode: allows concurrent readers, serialises writers internally.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    # Migrate existing DBs: add columns/tables introduced after initial schema.
    for stmt in (
        "ALTER TABLE playlists ADD COLUMN format TEXT NOT NULL DEFAULT 'mp3'",
        "ALTER TABLE playlists ADD COLUMN quality TEXT NOT NULL DEFAULT 'best'",
        "ALTER TABLE playlists ADD COLUMN output_dir TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE playlists ADD COLUMN auto_rename INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE playlists ADD COLUMN watched INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE playlists ADD COLUMN check_interval_secs INTEGER",
    ):
        try:
            conn.execute(stmt)
            logger.debug("Running migration: %s", stmt)
        except sqlite3.OperationalError:
            logger.debug("Migration already applied: %s", stmt.split("ADD COLUMN ")[1].split()[0] if "ADD COLUMN" in stmt else stmt)
    conn.commit()
    # Store as the calling thread's connection.
    _local.conn = conn
    logger.info("Database initialized at %s", os.path.join(data_dir, 'siphon.db'))


def _open_conn(data_dir: str) -> sqlite3.Connection:
    """Open a new SQLite connection for the given data directory."""
    db_path = os.path.join(data_dir, "siphon.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


def _get_conn() -> sqlite3.Connection:
    """
    Return a per-thread SQLite connection, creating one lazily if needed.

    Each OS thread (main thread, FastAPI worker threads, scheduler timer
    threads) gets its own connection. WAL mode on the DB means concurrent
    readers and serialised writers work correctly without a Python lock.
    """
    if _data_dir is None:
        raise RuntimeError("Registry not initialised. Call init_db() first.")
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _open_conn(_data_dir)
        _local.conn = conn
        logger.debug("New DB connection for thread %s", threading.current_thread().ident)
    return conn


def _thread_conn() -> sqlite3.Connection:
    """
    Open a short-lived SQLite connection for use from a worker thread.
    Callers must close it after use (use as a context manager or call .close()).
    Sets busy_timeout so concurrent writes wait rather than immediately failing.
    """
    if _data_dir is None:
        raise RuntimeError("Registry not initialised. Call init_db() first.")
    conn = sqlite3.connect(os.path.join(_data_dir, "siphon.db"))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 3000")
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Playlist CRUD
# ---------------------------------------------------------------------------

def add_playlist(
    playlist_id: str,
    name: str,
    url: str,
    fmt: str,
    quality: str,
    output_dir: str,
    auto_rename: bool = False,
    watched: bool = True,
    check_interval_secs: Optional[int] = None,
) -> None:
    """Insert a new playlist. Raises ValueError if the playlist ID already exists."""
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM playlists WHERE id = ?", (playlist_id,)
    ).fetchone()
    if existing:
        raise ValueError(f"Playlist '{playlist_id}' is already registered.")
    conn.execute(
        "INSERT INTO playlists (id, name, url, format, quality, output_dir, auto_rename, watched, check_interval_secs, added_at, last_synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (playlist_id, name, url, fmt, quality, output_dir, int(auto_rename), int(watched), check_interval_secs, _now()),
    )
    conn.commit()

    logger.info("Playlist registered: %s (%s)", name, playlist_id)


def list_playlists() -> list:
    """Return all playlists ordered by added_at ascending."""
    conn = _get_conn()
    return conn.execute(
        "SELECT * FROM playlists ORDER BY added_at ASC"
    ).fetchall()


def get_playlist_by_name(name: str) -> Optional[sqlite3.Row]:
    """Return the playlist row matching name, or None."""
    conn = _get_conn()
    return conn.execute(
        "SELECT * FROM playlists WHERE name = ?", (name,)
    ).fetchone()


def update_last_synced(playlist_id: str) -> None:
    """Set last_synced_at to now for the given playlist."""
    conn = _get_conn()
    conn.execute(
        "UPDATE playlists SET last_synced_at = ? WHERE id = ?",
        (_now(), playlist_id),
    )
    conn.commit()


def delete_playlist(playlist_id: str) -> None:
    """Delete all associated rows then the playlist row, in a single transaction."""
    conn = _get_conn()
    with conn:
        conn.execute("DELETE FROM items WHERE playlist_id = ?", (playlist_id,))
        conn.execute("DELETE FROM failed_downloads WHERE playlist_id = ?", (playlist_id,))
        conn.execute("DELETE FROM ignored_items WHERE playlist_id = ?", (playlist_id,))
        conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
    logger.info("Playlist removed: %s", playlist_id)


def get_playlist_by_id(playlist_id: str) -> Optional[sqlite3.Row]:
    """Return the playlist row matching id, or None."""
    conn = _get_conn()
    return conn.execute(
        "SELECT * FROM playlists WHERE id = ?", (playlist_id,)
    ).fetchone()


def get_watched_playlists() -> list:
    """Return all playlists with watched=1, ordered by added_at ascending."""
    conn = _get_conn()
    return conn.execute(
        "SELECT * FROM playlists WHERE watched = 1 ORDER BY added_at ASC"
    ).fetchall()


def set_playlist_watched(playlist_id: str, watched: bool) -> None:
    """Set the watched flag for a playlist."""
    conn = _get_conn()
    conn.execute(
        "UPDATE playlists SET watched = ? WHERE id = ?",
        (int(watched), playlist_id),
    )
    conn.commit()


def set_playlist_interval(playlist_id: str, interval_secs: Optional[int]) -> None:
    """Set (or clear) the per-playlist check interval."""
    conn = _get_conn()
    conn.execute(
        "UPDATE playlists SET check_interval_secs = ? WHERE id = ?",
        (interval_secs, playlist_id),
    )
    conn.commit()


def set_playlist_auto_rename(playlist_id: str, auto_rename: bool) -> None:
    """Enable or disable auto-rename for a playlist."""
    conn = _get_conn()
    conn.execute(
        "UPDATE playlists SET auto_rename = ? WHERE id = ?",
        (int(auto_rename), playlist_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Item persistence
# ---------------------------------------------------------------------------

def insert_item(record: ItemRecord, playlist_id: str) -> None:
    """
    Insert an item record. Silently ignored if (video_id, playlist_id) already exists.
    downloaded_at is set to now.

    Thread-safe: opens a short-lived connection so this can be called from worker threads.
    """
    now = _now()
    conn = _thread_conn()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO items
                (video_id, playlist_id, yt_title, renamed_to, rename_tier,
                 uploader, channel_url, duration_secs, downloaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.video_id,
                playlist_id,
                record.yt_title,
                record.renamed_to,
                record.rename_tier,
                record.uploader,
                record.channel_url,
                record.duration_secs,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def count_items(playlist_id: str) -> int:
    """Return the number of items recorded for a playlist."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT COUNT(*) FROM items WHERE playlist_id = ?", (playlist_id,)
    ).fetchone()
    return row[0] if row else 0


def get_item(video_id: str, playlist_id: str) -> Optional[dict]:
    """Fetch a single item row by its composite PK. Returns None if not found."""
    conn = _get_conn()
    row = conn.execute(
        """
        SELECT video_id, playlist_id, yt_title, renamed_to, rename_tier,
               uploader, channel_url, duration_secs, downloaded_at
        FROM items
        WHERE video_id = ? AND playlist_id = ?
        """,
        (video_id, playlist_id),
    ).fetchone()
    return dict(row) if row else None


def update_item_rename(video_id: str, playlist_id: str, new_name: str) -> None:
    """Update renamed_to and set rename_tier='manual' for the given item."""
    conn = _get_conn()
    cursor = conn.execute(
        """
        UPDATE items SET renamed_to = ?, rename_tier = 'manual'
        WHERE video_id = ? AND playlist_id = ?
        """,
        (new_name, video_id, playlist_id),
    )
    conn.commit()
    if cursor.rowcount == 0:
        raise ValueError(f"Item not found: video_id={video_id}, playlist_id={playlist_id}")


def list_items_for_playlist(playlist_id: str) -> list:
    """Return all item rows for a playlist ordered by downloaded_at ascending."""
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT video_id, playlist_id, yt_title, renamed_to, rename_tier,
               uploader, channel_url, duration_secs, downloaded_at
        FROM items
        WHERE playlist_id = ?
        ORDER BY downloaded_at ASC
        """,
        (playlist_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicates() -> list:
    """
    Return a list of dicts: {video_id, playlist_names} for videos that appear
    in more than one registered playlist.
    """
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT i.video_id, GROUP_CONCAT(p.name, ', ') AS playlist_names
        FROM items i
        JOIN playlists p ON p.id = i.playlist_id
        GROUP BY i.video_id
        HAVING COUNT(DISTINCT i.playlist_id) > 1
        ORDER BY i.video_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def set_setting(key: str, value: str) -> None:
    """Upsert a key-value setting."""
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    logger.debug("Setting updated: %s=%s", key, value)


def get_setting(key: str) -> Optional[str]:
    """Return the stored value for key, or None if not set."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return row[0] if row else None


def delete_all_playlists() -> None:
    """Remove all playlists and their associated data. Settings are preserved."""
    conn = _get_conn()
    with conn:
        conn.execute("DELETE FROM items")
        conn.execute("DELETE FROM failed_downloads")
        conn.execute("DELETE FROM ignored_items")
        conn.execute("DELETE FROM playlists")


def factory_reset() -> None:
    """Wipe all data including settings. Leaves an empty, initialised database."""
    delete_all_playlists()
    conn = _get_conn()
    with conn:
        conn.execute("DELETE FROM settings")


def get_downloaded_ids(playlist_id: str) -> set:
    """Return the set of video_ids already in `items` for a playlist."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT video_id FROM items WHERE playlist_id = ?", (playlist_id,)
    ).fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Failed downloads
# ---------------------------------------------------------------------------

def insert_failed(
    video_id: str,
    playlist_id: str,
    yt_title: str,
    url: str,
    error_message: str,
) -> None:
    """
    Insert or increment a failure record for (video_id, playlist_id).
    Thread-safe: opens a short-lived connection.
    """
    now = _now()
    conn = _thread_conn()
    try:
        conn.execute(
            """
            INSERT INTO failed_downloads
                (video_id, playlist_id, yt_title, url, error_message, attempt_count, last_attempted_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(video_id, playlist_id) DO UPDATE SET
                attempt_count     = attempt_count + 1,
                error_message     = excluded.error_message,
                last_attempted_at = excluded.last_attempted_at
            """,
            (video_id, playlist_id, yt_title, url, error_message, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_failed(playlist_id: str) -> list:
    """Return all failed_downloads rows for a playlist, ordered by last_attempted_at."""
    conn = _get_conn()
    return conn.execute(
        "SELECT * FROM failed_downloads WHERE playlist_id = ? ORDER BY last_attempted_at ASC",
        (playlist_id,),
    ).fetchall()


def clear_failed(video_id: str, playlist_id: str) -> None:
    """
    Delete the failure record for (video_id, playlist_id) after a successful retry.
    Thread-safe: opens a short-lived connection.
    """
    conn = _thread_conn()
    try:
        conn.execute(
            "DELETE FROM failed_downloads WHERE video_id = ? AND playlist_id = ?",
            (video_id, playlist_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_failed_attempt_count(video_id: str, playlist_id: str) -> int:
    """Return the attempt_count for a failure record, or 0 if no record exists."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT attempt_count FROM failed_downloads WHERE video_id = ? AND playlist_id = ?",
        (video_id, playlist_id),
    ).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Ignored items
# ---------------------------------------------------------------------------

def insert_ignored(video_id: str, playlist_id: Optional[str] = None, reason: Optional[str] = None) -> None:
    """
    Add a video to the ignore list.
    playlist_id=None (or '') means globally ignored (skipped across all playlists).
    Silently does nothing if already ignored (INSERT OR IGNORE).
    """
    pid = playlist_id or ""
    conn = _get_conn()
    conn.execute(
        """
        INSERT OR IGNORE INTO ignored_items (video_id, playlist_id, reason, ignored_at)
        VALUES (?, ?, ?, ?)
        """,
        (video_id, pid, reason, _now()),
    )
    conn.commit()


def is_ignored(video_id: str, playlist_id: str) -> bool:
    """Return True if video_id is globally ignored (playlist_id='') or ignored for this specific playlist."""
    conn = _get_conn()
    row = conn.execute(
        """
        SELECT 1 FROM ignored_items
        WHERE video_id = ?
          AND (playlist_id = '' OR playlist_id = ?)
        LIMIT 1
        """,
        (video_id, playlist_id),
    ).fetchone()
    return row is not None


def get_noise_patterns() -> Optional[list]:
    """Load title-noise-patterns from settings DB. Returns None when unset."""
    raw = get_setting("title_noise_patterns")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
