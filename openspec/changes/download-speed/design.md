## Context

`progress.py` already normalises yt-dlp hooks into `ProgressEvent` dicts containing `speed` (bytes/sec). The `_make_hook` in `downloader.py` forwards these to a `progress_callback`. In `watcher.py`, the callback (`_track_progress`) currently only checks `status == "finished"` — speed is discarded.

The SSE infrastructure (`JobStore` + `/jobs/{job_id}/stream`) already broadcasts per-job events to frontend subscribers via asyncio queues. The frontend (`DownloadQueue.vue`) consumes these events and updates item state.

## Goals / Non-Goals

**Goals:**
- Show live download speed in the queue header while items are downloading.
- Minimal code changes — reuse existing progress data and SSE plumbing.

**Non-Goals:**
- Per-item progress bars or byte counters (future work).
- ETA display.
- Throttling/debouncing (yt-dlp already ticks ~1/sec, which is fine).

## Decisions

### 1. New SSE event type `progress` on the existing job stream

Instead of creating a new endpoint, piggyback on the existing `/jobs/{job_id}/stream` SSE connection. `progress` events use the named SSE `event:` field so they don't interfere with the default `data:` state-change events the frontend already handles.

**Payload:** `{ "speed": <float|null> }`

**Why:** No new connections, no new endpoints. The frontend already has an `EventSource` per active job.

### 2. `JobStore.publish_progress(job_id, data)` — thin broadcast, no state mutation

A new method that pushes a dict into every subscriber's queue for that job, without touching job/item state. This keeps the state-transition path (`update_item_state`) clean.

**Why:** Progress ticks are ephemeral; they shouldn't touch the job model.

### 3. Wire `_track_progress` to call `publish_progress`

Modify the existing `_track_progress` closure (inside `_run_download_job`) to forward `speed` on `status == "downloading"` events. On `"finished"`, it continues to do what it does today.

**Why:** Single point of change — no new callbacks or plumbing needed.

### 4. Frontend: store speed as reactive ref, display in queue header

`DownloadQueue.vue` listens for the named `progress` event on the EventSource and stores speed in a reactive variable. A small helper formats bytes/sec → `"1.2 MB/s"`. When speed is `null` or no download is active, the display is hidden.

**Why:** One ref, one event listener, one formatter — minimal frontend change.

## Risks / Trade-offs

- **High-frequency events on slow clients** → yt-dlp ticks ~1/sec which is low; no throttle needed. If parallel downloads increase this, a simple `time.time()` gate can be added later.
- **Speed flicker between items** → Speed will be `null` between items in a playlist. The UI hides the indicator when `null`, so there may be brief flicker. Acceptable for v1.
