## 1. Backend — JobStore & DownloadJob model

- [x] 1.1 Add `cancelled: bool = False` field to `DownloadJob` dataclass
- [x] 1.2 Update `DownloadJob.is_terminal()` to treat `cancelled` as a terminal item state alongside `done` and `failed`
- [x] 1.3 Add `cancel_all_jobs()` method to `JobStore`: under the lock, iterate all non-terminal playlist jobs, transition all `pending` items to `cancelled`, fire SSE events for each, and call `notify_terminal()` for any job that became terminal; return count of items transitioned
- [x] 1.4 Update `JobStore._evict_if_needed()` to recognise `cancelled` as a terminal item state for eviction eligibility
- [x] 1.5 Update `JobStore.reset_failed_items()` to also reset items in `cancelled` state back to `pending` (in addition to `failed`)

## 2. Backend — Download worker

- [x] 2.1 In `_run_download_job` / `run_item()`, check `_job_store.is_cancelled(job_id)` (or `job.cancelled`) before transitioning each entry to `downloading`; if cancelled, skip the entry without calling `_download_worker`

## 3. Backend — API endpoint

- [x] 3.1 Add `POST /jobs/cancel-all` endpoint: call `_job_store.cancel_all_jobs()` and return `{ "cancelled": <count> }`

## 4. Backend — CLI command

- [x] 4.1 Add `cancel` subcommand to the CLI argument parser
- [x] 4.2 Implement `cmd_cancel()`: POST to `/jobs/cancel-all`, handle ConnectionError (daemon not running), print result summary or "No active downloads to cancel." when count is 0

## 5. Frontend — QueueItem cancelled state

- [x] 5.1 Add `cancelled` branch to `QueueItem.vue`: display a grey/neutral icon (e.g., `–` dash or `○` circle) and apply a muted background style
- [x] 5.2 Remove the per-item Retry button from `QueueItem.vue` (replaced by the global Retry button in the header)

## 6. Frontend — DownloadQueue header buttons

- [x] 6.1 Replace existing conditional `v-if` buttons with three always-rendered buttons in order: Cancel, Retry, Clear
- [x] 6.2 Wire Cancel button: `disabled` when no non-terminal playlist job exists; on click POST to `/jobs/cancel-all`, disable self, set `cancelling = true` ref, apply pulse CSS animation with text `Cancelling…`; once all playlist jobs are terminal (detected via SSE `done` event or polling jobs ref), set `cancelling = false` and revert button text
- [x] 6.3 Wire Retry button: `disabled` when no item across all jobs is `failed` or `cancelled`; on click call existing `retryFailed()` targeting the first job with failed/cancelled items; ensure `retryFailed()` re-enables SSE if needed
- [x] 6.4 Wire Clear button: `disabled` when no item across all jobs is `done`; on click call `POST /jobs/{id}/clear-done` for each job with done items, then re-fetch `/jobs` to update display (backend-backed so cleared items do not return on page reload)
- [x] 6.5 Lock progress summary counter to job's original `total` item count (not a count of currently-visible items)
- [x] 6.6 Add CSS `@keyframes pulse` animation for the Cancel button's `Cancelling…` state (opacity oscillation)
- [x] 6.7 Handle SSE `cancelled` state in the existing `es.onmessage` handler — update item state from the event as with other states

## 7. Frontend — QueueItem sort order

- [x] 7.1 Update `STATE_ORDER` in `DownloadQueue.vue` to put `failed` first: `{ failed: 0, downloading: 1, pending: 2, cancelled: 3, done: 4 }`
