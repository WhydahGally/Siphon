## ADDED Requirements

### Requirement: Progress callback interface
The engine SHALL call the `progress_callback` with a single dict argument on each yt-dlp progress event. The callback is optional; if not provided, progress events are silently dropped. In the parallel engine, each worker thread has its own callback bound to its slot index so the renderer can direct updates to the correct display slot.

#### Scenario: Callback provided (single download)
- **WHEN** a `progress_callback` is passed to `download()` and a download is in progress
- **THEN** the engine SHALL call it with a dict on each progress tick

#### Scenario: Callback provided (parallel engine)
- **WHEN** the parallel engine creates N worker callbacks (one per slot)
- **THEN** each callback SHALL only receive events from its own worker thread; events from different workers SHALL NOT be mixed in any single callback invocation

#### Scenario: No callback provided
- **WHEN** `progress_callback` is `None`
- **THEN** the engine SHALL proceed without error and emit no progress output

---

### Requirement: Progress event shape
Each progress event dict passed to the callback SHALL contain the following fields:

- `status`: one of `"downloading"`, `"finished"`, `"error"`
- `filename`: the local file path being written (str)
- `downloaded_bytes`: bytes downloaded so far (int, may be None if unknown)
- `total_bytes`: total expected bytes (int, may be None if unknown)
- `speed`: download speed in bytes/sec (float, may be None)
- `eta`: estimated seconds remaining (int, may be None)
- `slot_index`: (int, present only in parallel mode) the worker slot index this event belongs to

#### Scenario: Downloading event (parallel mode)
- **WHEN** a file download is in progress in the parallel engine
- **THEN** the callback SHALL receive a dict with `status="downloading"`, available byte/speed/eta fields, and a `slot_index` identifying the worker

#### Scenario: Downloading event (single)
- **WHEN** a file download is in progress in standalone (non-parallel) usage
- **THEN** the callback SHALL receive a dict with `status="downloading"` and available byte/speed/eta fields; `slot_index` is not present

#### Scenario: Finished event
- **WHEN** a file download completes
- **THEN** the callback SHALL receive a dict with `status="finished"` and the final `filename`

#### Scenario: Error event
- **WHEN** yt-dlp reports a download error for an item
- **THEN** the callback SHALL receive a dict with `status="error"` and `filename` set to the attempted path

---

### Requirement: Callback error isolation
If the progress callback raises an exception, the engine SHALL catch it, log a WARNING, and continue the download. A misbehaving callback SHALL NOT abort a download.

#### Scenario: Callback raises an exception
- **WHEN** the progress callback throws any exception
- **THEN** the engine SHALL log a WARNING and continue downloading the current item

---

### Requirement: JobStore publish_progress method
The `JobStore` SHALL provide a `publish_progress(job_id, data)` method that broadcasts a dict to all SSE subscribers for the given job without mutating job or item state.

#### Scenario: Subscribers receive progress data
- **WHEN** `publish_progress(job_id, {"speed": 1200000})` is called and there are active SSE subscribers for that job
- **THEN** each subscriber's queue SHALL receive the event tagged as a `progress` event type

#### Scenario: No subscribers
- **WHEN** `publish_progress` is called for a job with no SSE subscribers
- **THEN** the call SHALL complete without error

---

### Requirement: SSE event generator forwards progress events
The SSE event generator SHALL distinguish `progress` events from state-change events and emit them with `event: progress` SSE field so the frontend can handle them via `addEventListener('progress', ...)`.

#### Scenario: Progress event serialization
- **WHEN** a progress event is placed in a subscriber's queue
- **THEN** the SSE generator SHALL emit `event: progress\ndata: <json>\n\n`

#### Scenario: State-change events unchanged
- **WHEN** a state-change event is placed in a subscriber's queue
- **THEN** the SSE generator SHALL emit it as before (unnamed `data:` event) with no change in format
