## MODIFIED Requirements

### Requirement: Single public download function
The engine SHALL expose one public function `download(url, output_dir, options, progress_callback=None, mb_user_agent=None, auto_rename=False, on_item_complete=None)`. The function SHALL accept either a single video URL or a playlist URL. In the parallel sync path, the engine is called with individual video URLs (one per thread); playlist URL support is retained for standalone and `__main__` usage.

The function SHALL be safe to call from multiple threads simultaneously. Each invocation creates its own `YoutubeDL` instance with no shared mutable state between invocations.

`ItemRecord` fields (unchanged):
- `video_id` (str)
- `playlist_id` (str | None)
- `yt_title` (str)
- `renamed_to` (str | None)
- `rename_tier` (str | None)
- `uploader` (str | None)
- `channel_url` (str | None)
- `duration_secs` (int | None)

#### Scenario: Single video URL dispatched from thread pool
- **WHEN** a single video URL is passed to `download()` from a worker thread
- **THEN** the engine SHALL download that one video, run postprocessors, invoke the rename chain, and return without affecting any other concurrently-running `download()` invocation

#### Scenario: Concurrent invocations from multiple threads
- **WHEN** `download()` is called simultaneously from N worker threads with N different video URLs
- **THEN** each invocation SHALL complete independently; no shared state corruption SHALL occur

#### Scenario: Playlist URL is provided (standalone use)
- **WHEN** a playlist URL is passed to `download()` (e.g. from `__main__` or direct API use)
- **THEN** the engine SHALL fetch playlist metadata and download each video item in sequence under `<output_dir>/<playlist_title>/`

#### Scenario: Single video URL is provided (standalone use)
- **WHEN** a single video URL is passed to `download()` directly
- **THEN** the engine SHALL download that one video directly into `<output_dir>/`

#### Scenario: on_item_complete invoked after each item
- **WHEN** `on_item_complete` is a callable and an item completes
- **THEN** the engine SHALL invoke `on_item_complete` with a populated `ItemRecord`. Errors in the callback SHALL be caught, logged as WARNING, and SHALL NOT abort the download.

## REMOVED Requirements

### Requirement: Archive file usage in download engine
**Reason**: The `download_archive` yt-dlp option is no longer set by the engine. Deduplication is now performed by the parallel engine's pre-dispatch filter using the `items` DB table. The archive file was yt-dlp's internal dedup mechanism; it is superseded by the DB-centric approach.
**Migration**: Existing `.data/archives/*.txt` files become inert. No migration tooling is provided; they can be deleted manually. Any item in the archive but not in the `items` table will be re-downloaded once on the next sync, then recorded in the DB and filtered correctly on all subsequent syncs.
