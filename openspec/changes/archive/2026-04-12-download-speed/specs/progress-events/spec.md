## ADDED Requirements

### Requirement: JobStore publish_progress method
The `JobStore` SHALL provide a `publish_progress(job_id, data)` method that broadcasts a dict to all SSE subscribers for the given job without mutating job or item state.

#### Scenario: Subscribers receive progress data
- **WHEN** `publish_progress(job_id, {"speed": 1200000})` is called and there are active SSE subscribers for that job
- **THEN** each subscriber's queue SHALL receive the event tagged as a `progress` event type

#### Scenario: No subscribers
- **WHEN** `publish_progress` is called for a job with no SSE subscribers
- **THEN** the call SHALL complete without error

### Requirement: SSE event generator forwards progress events
The SSE event generator SHALL distinguish `progress` events from state-change events and emit them with `event: progress` SSE field so the frontend can handle them via `addEventListener('progress', ...)`.

#### Scenario: Progress event serialization
- **WHEN** a progress event is placed in a subscriber's queue
- **THEN** the SSE generator SHALL emit `event: progress\ndata: <json>\n\n`

#### Scenario: State-change events unchanged
- **WHEN** a state-change event is placed in a subscriber's queue
- **THEN** the SSE generator SHALL emit it as before (unnamed `data:` event) with no change in format
