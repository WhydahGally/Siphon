import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from siphon.downloader import ItemRecord


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

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
"""


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db(data_dir: str) -> None:
    """
    Initialise the registry.

    Creates .data/ and .data/archives/ on first run.
    Opens (or creates) siphon.db and applies the schema.
    Safe to call multiple times — idempotent.
    """
    global _conn, _data_dir

    _data_dir = data_dir
    archives_dir = os.path.join(data_dir, "archives")
    os.makedirs(archives_dir, exist_ok=True)

    db_path = os.path.join(data_dir, "siphon.db")
    _conn = sqlite3.connect(db_path)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.executescript(_SCHEMA)
    # Migrate existing DBs: add columns introduced after initial schema.
    for stmt in (
        "ALTER TABLE playlists ADD COLUMN format TEXT NOT NULL DEFAULT 'mp3'",
        "ALTER TABLE playlists ADD COLUMN quality TEXT NOT NULL DEFAULT 'best'",
        "ALTER TABLE playlists ADD COLUMN output_dir TEXT NOT NULL DEFAULT ''",
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Playlist CRUD
# ---------------------------------------------------------------------------

def add_playlist(playlist_id: str, name: str, url: str, fmt: str, quality: str, output_dir: str) -> None:
    """Insert a new playlist. Raises ValueError if the playlist ID already exists."""
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM playlists WHERE id = ?", (playlist_id,)
    ).fetchone()
    if existing:
        raise ValueError(f"Playlist '{playlist_id}' is already registered.")
    conn.execute(
        "INSERT INTO playlists (id, name, url, format, quality, output_dir, added_at, last_synced_at) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
        (playlist_id, name, url, fmt, quality, output_dir, _now()),
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
    """Delete all items then the playlist row, in a single transaction."""
    conn = _get_conn()
    with conn:
        conn.execute("DELETE FROM items WHERE playlist_id = ?", (playlist_id,))
        conn.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))


# ---------------------------------------------------------------------------
# Item persistence
# ---------------------------------------------------------------------------

def insert_item(record: ItemRecord, playlist_id: str) -> None:
    """
    Insert an item record. Silently ignored if (video_id, playlist_id) already exists.
    downloaded_at is set to now.
    """
    conn = _get_conn()
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
            _now(),
        ),
    )
    conn.commit()


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


# ---------------------------------------------------------------------------
# Archive path helper
# ---------------------------------------------------------------------------

def archive_path(playlist_id: str) -> str:
    """Return the absolute path to the yt-dlp archive file for a playlist."""
    if _data_dir is None:
        raise RuntimeError("Registry not initialised. Call init_db() first.")
    return os.path.join(_data_dir, "archives", f"{playlist_id}.txt")
