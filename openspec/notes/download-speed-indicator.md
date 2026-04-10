# Download Speed Indicator

Show live download speed next to the "Y/X downloaded" summary in the dashboard queue.

## What's needed

1. **Backend** — `_track_progress` in `watcher.py` currently only checks `status == "finished"` and discards speed. Needs to forward mid-download `speed` (bytes/sec from yt-dlp) into a new lightweight `progress` SSE event type on the job stream, separate from state-transition events.

2. **Job store** — new method to publish a progress event (speed only, no state change) to SSE subscribers for a given job.

3. **Frontend (DownloadQueue.vue)** — SSE handler needs to handle the new `progress` event type and store the current speed on the active downloading item. Display formatted speed (e.g. `1.2 MB/s`) next to the "Y/X downloaded" text in the queue header.

## Notes

- `progress.py` already normalises `speed` from the yt-dlp hook — the raw data is available.
- Speed will tick ~once per second while yt-dlp is active; will be `null` between items.
- Speed display should disappear (not show 0) when no item is actively downloading.
- A bytes/sec → human-readable formatter will be needed on the frontend.
