## 1. Backend — JobStore progress broadcast

- [x] 1.1 Add `publish_progress(job_id, data)` method to `JobStore` that pushes a tagged event to all subscriber queues without mutating state
- [x] 1.2 Update SSE event generator in `api_stream_job` to emit `event: progress` for tagged progress events and unnamed `data:` for state-change events

## 2. Backend — Wire progress into SSE

- [x] 2.1 Modify `_track_progress` closure in `_run_download_job` to call `_job_store.publish_progress(job_id, {"speed": event["speed"]})` on `status == "downloading"` ticks

## 3. Frontend — Display speed in queue header

- [x] 3.1 Add `progress` event listener to EventSource in `DownloadQueue.vue` and store speed in a reactive ref
- [x] 3.2 Add speed formatter utility (bytes/sec → human-readable string with appropriate unit)
- [x] 3.3 Display formatted speed next to download count in queue header, hidden when speed is null or no download is active
