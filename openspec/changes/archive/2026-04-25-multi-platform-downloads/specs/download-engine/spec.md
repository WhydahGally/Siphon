## MODIFIED Requirements

### Requirement: Single public download function
The engine SHALL expose one public function `download(url, output_dir, options, progress_callback=None, mb_user_agent=None, auto_rename=False, on_item_complete=None)`. The function SHALL accept either a single video URL or a playlist URL from any yt-dlp-supported platform. In the parallel sync path, the engine is called with individual video URLs (one per thread); playlist URL support is retained for standalone and `__main__` usage.

The function SHALL be safe to call from multiple threads simultaneously. Each invocation creates its own `YoutubeDL` instance with no shared mutable state between invocations.

The `on_item_complete` parameter is an optional callable that receives an `ItemRecord` after each item is fully downloaded and renamed.

`ItemRecord` fields:
- `video_id` (str)
- `playlist_id` (str | None): the playlist ID if this download is part of a playlist, else None
- `title` (str): the raw title as provided by yt-dlp
- `renamed_to` (str | None): final filename stem; None if renamer returned None
- `rename_tier` (str | None)
- `uploader` (str | None)
- `channel_url` (str | None)
- `duration_secs` (int | None)

#### Scenario: Playlist URL is provided
- **WHEN** a playlist URL is passed to `download()`
- **THEN** the engine SHALL fetch playlist metadata and download each video item in sequence under `<output_dir>/<playlist_title>/`

#### Scenario: Single video URL is provided
- **WHEN** a single video URL is passed to `download()`
- **THEN** the engine SHALL download that one video directly into `<output_dir>/`

#### Scenario: Single video URL dispatched from thread pool
- **WHEN** a single video URL is passed to `download()` from a worker thread
- **THEN** the engine SHALL download that one video, run postprocessors, invoke the rename chain, and return without affecting any other concurrently-running `download()` invocation

#### Scenario: Concurrent invocations from multiple threads
- **WHEN** `download()` is called simultaneously from N worker threads with N different video URLs
- **THEN** each invocation SHALL complete independently; no shared state corruption SHALL occur

#### Scenario: Playlist URL with on_item_complete provided
- **WHEN** a playlist URL is passed and `on_item_complete` is a callable
- **THEN** after each item is fully processed (downloaded + renamed), the engine SHALL invoke `on_item_complete` with a populated `ItemRecord`. Errors raised inside the callback SHALL be caught, logged as WARNING, and SHALL NOT abort the download.

#### Scenario: Playlist URL without on_item_complete
- **WHEN** a playlist URL is passed and `on_item_complete` is None
- **THEN** the engine SHALL behave exactly as before — no callback is invoked

#### Scenario: Single video URL with on_item_complete provided
- **WHEN** a single video URL is passed and `on_item_complete` is a callable
- **THEN** the engine SHALL invoke `on_item_complete` with a populated `ItemRecord` after the item is processed. `ItemRecord.playlist_id` SHALL be None.
