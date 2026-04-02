## Context

Siphon currently has a `download()` function in `downloader.py` and a four-tier `rename_file()` in `renamer.py`. There is no persistent state — each run is stateless. The CLI is accessed via `python3 -m siphon.downloader`, with no installed entry point.

This design adds persistent state (SQLite), a proper CLI entry point, and the sync loop that compares remote playlist state against local records to drive incremental downloads.

## Goals / Non-Goals

**Goals:**
- Single SQLite file at `.data/siphon.db`, created on first startup, git-ignored
- Per-playlist yt-dlp archive files at `.data/archives/<playlist_id>.txt`, also git-ignored
- `siphon` CLI entry point with `add`, `sync`, and `list` subcommands
- `rename_file()` returns `RenameResult` instead of `None`
- `download()` accepts `on_item_complete` callback for per-item post-rename notifications
- All three sync error cases handled: non-existent playlist name, deleted/privated YT playlist, already up-to-date

**Non-Goals:**
- Playlist import from existing local files (deferred — see `openspec/notes/playlist-import-research.md`)
- Manual review workflow for low-confidence renames
- Any UI or web layer
- Multi-user or networked registry

## Decisions

### D1: SQLite at `.data/siphon.db`, not inside `src/`

Storing the DB under `src/` would include it in the installed package and require packaging exclusion logic. `.data/` at project root mirrors conventions for tool-managed runtime state (`.venv/`, `.git/`). It is added to `.gitignore` so nothing is accidentally committed.

**Alternatives considered:**
- `~/.siphon/siphon.db` — global, survives project deletion. Rejected: ties the tool's state to the host user account, which conflicts with the intent to containerize.
- `src/siphon/.db/siphon.db` — next to the source. Rejected: pollutes the package directory and complicates packaging.

---

### D2: Archive file keyed by YT playlist ID, not name

Playlist names can be edited on YouTube at any time. The yt-dlp archive format is one video ID per line; matching it to the correct playlist requires a stable key. The playlist ID (the `list=` query param) never changes.

File path: `.data/archives/<playlist_id>.txt`

---

### D3: Both archive file AND DB for tracking downloads

These two stores serve different consumers:
- **Archive file** → consumed directly by yt-dlp (`download_archive` option). Zero-code way to skip already-downloaded items.
- **DB** → consumed by the future UI and `siphon list`. Stores rich metadata: original title, renamed filename, rename tier, uploader, duration, timestamps.

They are updated together after each successful item download. The archive file is the skip gate; the DB is the record of truth.

**Alternatives considered:**
- DB only, with yt-dlp querying it via a custom hook. Rejected: yt-dlp's archive file mechanism is well-tested and requires no yt-dlp API changes.
- Archive file only. Rejected: no way to display history or power a future UI.

---

### D4: `RenameResult` dataclass returned from `rename_file()`

The renamer currently returns `None`. To persist rename outcomes in the DB, the caller needs the original title, final name, and tier. A `RenameResult` dataclass (stdlib `dataclasses`) is the cleanest interface — no dict key-hunting, type-safe, zero dependencies.

```python
@dataclass
class RenameResult:
    original_title: str
    final_name: str       # filename stem, no extension
    tier: str             # "yt_metadata" | "title_separator" | "musicbrainz" | "yt_title_fallback"
    new_path: str         # absolute path to renamed file
```

`_RenamePostProcessor.run()` in `downloader.py` captures this result. It is currently the only caller.

---

### D5: `on_item_complete` callback on `download()`

The downloader must not know about SQLite. An optional `on_item_complete: Callable[[ItemRecord], None]` parameter keeps the engines decoupled. The registry layer passes in a closure that writes to the DB. If not provided, the downloader behaves exactly as before.

`ItemRecord` is a dataclass carrying: `video_id`, `playlist_id`, `yt_title`, `renamed_to`, `rename_tier`, `uploader`, `channel_url`, `duration_secs`, `downloaded_at`.

---

### D6: `(video_id, playlist_id)` composite primary key in `items`

A single video can appear in multiple playlists. Using `video_id` alone as PK would prevent this. The composite key `(video_id, playlist_id)` is the correct model — each row represents a video's presence in a specific playlist.

The direct video URL is always reconstructed as `https://youtube.com/watch?v={video_id}` and is never stored.

---

### D7: `siphon sync <name>` matches by playlist name, errors on no match

Matching by name (not ID) is more ergonomic at the CLI. If no playlist with that name exists, we print a clear error and list the known playlists. Names are stored as fetched from YT; if a YT playlist name changes, the local name in the DB does not auto-update (sync does not rename existing entries).

---

### D8: `siphon add` fetches the playlist name from YT, no user-supplied name

The YT playlist title is the source of truth. Requiring users to supply a name creates a divergence risk. On `add`, we call `yt-dlp --dump-json` (or `YoutubeDL.extract_info` with `download=False`) to fetch the playlist title before any downloads start.

---

### D9: DB schema

```sql
CREATE TABLE playlists (
    id             TEXT PRIMARY KEY,    -- YT playlist ID
    name           TEXT NOT NULL,       -- YT playlist title at time of add
    url            TEXT NOT NULL,
    added_at       TEXT NOT NULL,       -- ISO 8601 UTC
    last_synced_at TEXT                 -- NULL until first sync
);

CREATE TABLE items (
    video_id       TEXT NOT NULL,
    playlist_id    TEXT NOT NULL REFERENCES playlists(id),
    yt_title       TEXT NOT NULL,
    renamed_to     TEXT,
    rename_tier    TEXT,                -- "yt_metadata"|"title_separator"|"musicbrainz"|"yt_title_fallback"
    uploader       TEXT,
    channel_url    TEXT,
    duration_secs  INTEGER,
    downloaded_at  TEXT NOT NULL,
    PRIMARY KEY (video_id, playlist_id)
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

### D10: CLI structure — `argparse` with subcommands, stdlib only

No third-party CLI framework (click, typer) to keep dependencies minimal. `argparse` subparsers cover the required surface. The entry point is `siphon.cli:main`, registered in `pyproject.toml`.

```
siphon add <url> [--download] [--format mp3|opus|mp4|...] [--mb-user-agent UA]
siphon sync [<name>] [--format mp3|...] [--mb-user-agent UA]
siphon list
```

## Risks / Trade-offs

**[Risk] yt-dlp archive file and DB diverge** → If a download completes but the DB write fails (e.g., crash), the archive has the ID but the DB has no record. Mitigation: write the DB record first, then let yt-dlp update the archive file. If the DB write fails, yt-dlp will re-attempt the download on next sync (safe, just redundant).

Alternatively: write DB after yt-dlp confirms success via `on_item_complete` callback. The archive file is written by yt-dlp itself atomically per item. The DB is then written by our callback immediately after. Crash between yt-dlp archive write and DB write would leave the archive ahead of the DB — the item would be skipped on next sync forever. Acceptable for now given the low-stakes nature of the data.

**[Risk] Playlist name collision** → If two different playlists happen to have the same YT title, `siphon sync <name>` would match the first found. Mitigation: unique-ify display names by appending the playlist ID suffix when listing/syncing if duplicates exist. Out of scope for now.

**[Risk] YT playlist title changes** → `playlists.name` is set at `add` time and never auto-updated. User would use the old name to sync. Mitigation: `siphon sync` could warn if the fetched YT title differs from the stored name. Out of scope for now.

**[Risk] `.data/` missed from `.gitignore`** → Accidentally committing large db/archive files. Mitigation: `.data/` is explicitly added to the root `.gitignore`.

## Migration Plan

No migration needed — there is no existing persistent state. The `.data/` folder and `siphon.db` are created fresh on first `siphon add` or `siphon sync` invocation.

After implementing, re-install the package to pick up the new CLI entry point:
```
pip install -e .
```

## Open Questions

- None — all decisions above were made during the explore phase.
