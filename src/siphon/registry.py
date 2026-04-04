import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from siphon.downloader import ItemRecord


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

# The module-level connection is used only on the main thread (CLI commands).
# Worker threads open their own short-lived connections via _thread_conn().
_conn: Optional[sqlite3.Connection] = None
_data_dir: Optional[str] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS playlists (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    url            TEXT NOT NULL,
    format         TEXT NOT NULL DEFAULT 'mp3',
    quality        TEXT NOT NULL DEFAULT 'best',
    output_dir     TEXT NOT NULL,
    auto_rename    INTEGER NOT NULL DEFAULT 0,
    added_at       TEXT NOT NULL,
    last_synced_at TEXT
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
    global _conn, _data_dir

    _data_dir = data_dir
    os.makedirs(data_dir, exist_ok=True)

    db_path = os.path.join(data_dir, "siphon.db")
    _conn = sqlite3.connect(db_path)
    _conn.row_factory = sqlite3.Row
    # WAL mode: allows concurrent readers, serialises writers internally.
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.executescript(_SCHEMA)
    # Migrate existing DBs: add columns/tables introduced after initial schema.
    for stmt in (
        "ALTER TABLE playlists ADD COLUMN format TEXT NOT NULL DEFAULT 'mp3'",
        "ALTER TABLE playlists ADD COLUMN quality TEXT NOT NULL DEFAULT 'best'",
        "ALTER TABLE playlists ADD COLUMN output_dir TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE playlists ADD COLUMN auto_rename INTEGER NOT NULL DEFAULT 0",
    ):
        try:
            _conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    _conn.commit()


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Registry not initialised. Call init_db() first.")
    return _conn


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

def add_playlist(playlist_id: str, name: str, url: str, fmt: str, quality: str, output_dir: str, auto_rename: bool = False) -> None:
    """Insert a new playlist. Raises ValueError if the playlist ID already exists."""
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM playlists WHERE id = ?", (playlist_id,)
    ).fetchone()
    if existing:
        raise ValueError(f"Playlist '{playlist_id}' is already registered.")
    conn.execute(
        "INSERT INTO playlists (id, name, url, format, quality, output_dir, auto_rename, added_at, last_synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)",
        (playlist_id, name, url, fmt, quality, output_dir, int(auto_rename), _now()),
    )
    conn.commit()


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


def get_setting(key: str) -> Optional[str]:
    """Return the stored value for key, or None if not set."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    ).fetchone()
    return row[0] if row else None


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
