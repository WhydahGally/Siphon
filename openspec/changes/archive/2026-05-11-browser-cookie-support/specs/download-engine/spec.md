## MODIFIED Requirements

### Requirement: Single public download function
The engine SHALL expose one public function `download(url, output_dir, options, progress_callback=None, mb_user_agent=None, auto_rename=False, on_item_complete=None, cookie_file=None)`. The function SHALL accept either a single video URL or a playlist URL from any yt-dlp-supported platform. In the parallel sync path, the engine is called with individual video URLs (one per thread); playlist URL support is retained for standalone and `__main__` usage.

The function SHALL be safe to call from multiple threads simultaneously. Each invocation creates its own `YoutubeDL` instance with no shared mutable state between invocations.

When `cookie_file` is a non-None string, it SHALL be passed to both the preflight `YoutubeDL` options and the main `_build_ydl_opts()` call as `ydl_opts["cookiefile"]`. When `None`, no `cookiefile` key SHALL appear in any ydl options dict.

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

#### Scenario: cookie_file provided — passed to yt-dlp
- **WHEN** `download(url, ..., cookie_file="/data/cookies.txt")` is called
- **THEN** both the preflight and main `YoutubeDL` instances SHALL have `ydl_opts["cookiefile"] = "/data/cookies.txt"`

#### Scenario: No cookie_file — no cookiefile opt
- **WHEN** `download(url, ..., cookie_file=None)` is called
- **THEN** no `cookiefile` key SHALL appear in any `YoutubeDL` options dict

---

### Requirement: enumerate_entries accepts cookie_file
`enumerate_entries(url, cookie_file=None)` SHALL accept an optional `cookie_file` parameter. When non-None, the `YoutubeDL` options for the `extract_flat` call SHALL include `"cookiefile": cookie_file`.

#### Scenario: enumerate_entries with cookie_file
- **WHEN** `enumerate_entries(url, cookie_file="/data/cookies.txt")` is called
- **THEN** the `extract_flat` yt-dlp call SHALL include `cookiefile` in its options

#### Scenario: enumerate_entries without cookie_file
- **WHEN** `enumerate_entries(url)` is called
- **THEN** no `cookiefile` key SHALL appear in the yt-dlp options

---

### Requirement: sync_parallel and run_download_job accept cookie_file
`sync_parallel()` and `run_download_job()` SHALL each accept a `cookie_file: Optional[str] = None` parameter and thread it through to all internal `download_worker()` and `download_parallel()` calls.

#### Scenario: cookie_file threaded through sync_parallel
- **WHEN** `sync_parallel(..., cookie_file="/data/cookies.txt")` is called
- **THEN** every item downloaded in that sync SHALL have the cookie file path in its yt-dlp options

#### Scenario: cookie_file threaded through run_download_job
- **WHEN** `run_download_job(..., cookie_file="/data/cookies.txt")` is called
- **THEN** every `download_worker()` invocation in that job SHALL receive the cookie file path
