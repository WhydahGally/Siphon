## Why

When downloads are in progress, the UI shows item state transitions (pending → downloading → done) but gives no indication of download speed. Users have no way to know if a download is crawling or healthy without checking the terminal. Surfacing live speed in the dashboard queue header gives immediate feedback.

## What Changes

- Extend `_track_progress` in `watcher.py` to forward mid-download `speed` from yt-dlp progress events through the existing SSE job stream as a lightweight `progress` event type.
- Add a `publish_progress` method to `JobStore` to broadcast speed-only events to SSE subscribers without triggering state transitions.
- Handle the new `progress` SSE event in `DownloadQueue.vue` and display a human-readable speed (e.g. `1.2 MB/s`) next to the "Y/X downloaded" text in the queue header. Speed disappears when no item is actively downloading.

## Capabilities

### New Capabilities
- `download-speed-indicator`: Live download speed display in the dashboard queue header, fed by a new SSE progress event type carrying speed data from the existing yt-dlp progress hook.

### Modified Capabilities
- `progress-events`: The progress callback data is already captured; the change is that `_track_progress` now forwards speed into SSE instead of discarding it. No new fields in the event shape — just a new consumer of existing data.

## Impact

- **Backend**: `watcher.py` — `_track_progress` callback, `JobStore` class, SSE event generator.
- **Frontend**: `DownloadQueue.vue` — SSE handler, queue header template.
- **No new dependencies.** All data already exists in `progress.py`; this change wires it through to the UI.
