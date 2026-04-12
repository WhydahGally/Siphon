## Why

When a user starts a download job and then notices a misconfiguration (wrong format, VPN not connected, wrong output dir), there is no way to stop it — they must wait for all queued items to finish or restart the daemon. Adding cancel support lets users stop in-flight jobs immediately without losing any already-downloaded items.

## What Changes

- Add a `cancelled` item state to the job model alongside `pending`, `downloading`, `done`, `failed`
- Add `POST /jobs/cancel-all` API endpoint that marks all pending items in all active playlist jobs as `cancelled` and fires SSE events
- Items already `downloading` when cancel is called are not interrupted — they run to completion (yt-dlp cannot be safely interrupted mid-download)
- Cancelled items are resetable via the existing retry mechanism (same as failed items)
- When a job becomes terminal (all items in `done | failed | cancelled`), the scheduler marks it complete and the next sync is unaffected — cancelled items are never written to the DB, so they re-appear on the next sync as fresh entries
- Add three persistent action buttons to the Download Queue header: **Cancel**, **Retry**, **Clear** (always visible, enabled/disabled based on state)
- "Cancel" replaces no existing button; "Retry" replaces "Retry failed"; "Clear" replaces "Clear queue"
- Cancel button disables itself immediately on click and pulses (`Cancelling…`) until all active jobs reach terminal state
- Clear button removes all `done` items from the queue display (frontend-only filter); if a job block has no remaining visible items, the block disappears
- Retry resets both `failed` and `cancelled` items back to `pending` and re-dispatches them
- CLI: `siphon cancel` cancels all active jobs via the daemon API

## Capabilities

### New Capabilities
- `download-cancel`: Cancel all active download jobs; marks pending items as cancelled, drains in-flight items, resets terminal state so next sync picks up uncompleted videos

### Modified Capabilities
- `job-store`: `cancelled` added as a valid terminal item state; `is_terminal()` and `reset_failed_items()` updated to include it
- `progress-events`: SSE stream emits `cancelled` state events for items transitioned by cancel
- `web-ui`: Download Queue header buttons redesigned — Cancel / Retry / Clear replace the previous conditional buttons

## Impact

- `src/siphon/watcher.py`: `DownloadJob`, `JobStore`, `_run_download_job`, new `/jobs/cancel-all` endpoint, CLI `cancel` subcommand
- `src/ui/src/components/DownloadQueue.vue`: header button logic, cancel/retry/clear handlers, cancel pulse animation
- `src/ui/src/components/QueueItem.vue`: `cancelled` state branch (grey icon)
- No DB schema changes — cancelled items are never persisted
- No breaking changes to existing API endpoints
