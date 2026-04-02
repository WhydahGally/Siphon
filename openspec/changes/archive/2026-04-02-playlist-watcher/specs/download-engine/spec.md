## MODIFIED Requirements

### Requirement: Single public download function
The engine SHALL expose one public function `download(url, output_dir, options, progress_callback=None, mb_user_agent=None, auto_rename=False, on_item_complete=None)`. The `on_item_complete` parameter is an optional callable that receives an `ItemRecord` after each item is fully downloaded and renamed.

`ItemRecord` fields:
- `video_id` (str)
- `playlist_id` (str | None): the YT playlist ID if this download is part of a playlist, else None
- `yt_title` (str)
- `renamed_to` (str | None): final filename stem; None if renamer returned None
- `rename_tier` (str | None)
- `uploader` (str | None)
- `channel_url` (str | None)
- `duration_secs` (int | None)

#### Scenario: Playlist URL with on_item_complete provided
- **WHEN** a playlist URL is passed and `on_item_complete` is a callable
- **THEN** after each item is fully processed (downloaded + renamed), the engine SHALL invoke `on_item_complete` with a populated `ItemRecord`. Errors raised inside the callback SHALL be caught, logged as WARNING, and SHALL NOT abort the download.

#### Scenario: Playlist URL without on_item_complete
- **WHEN** a playlist URL is passed and `on_item_complete` is None
- **THEN** the engine SHALL behave exactly as before — no callback is invoked

#### Scenario: Single video URL with on_item_complete provided
- **WHEN** a single video URL is passed and `on_item_complete` is a callable
- **THEN** the engine SHALL invoke `on_item_complete` with a populated `ItemRecord` after the item is processed. `ItemRecord.playlist_id` SHALL be None.
