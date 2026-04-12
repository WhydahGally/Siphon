## Context

The download engine uses a `ThreadPoolExecutor` per job, dispatching `_download_worker` threads — each wrapping a blocking `YoutubeDL.download()` call. `JobStore` tracks per-item state and fans SSE events to browser subscribers. There is currently no way to halt a job once started. The `retry-failed` flow (reset items → re-dispatch) is the template for cancel+retry.

The daemon is a FastAPI app; all state is in-process and in-memory (`_job_store`). No filesystem IPC, no shared queues between processes.

## Goals / Non-Goals

**Goals:**
- Allow a user to cancel all active (non-terminal) playlist download jobs in one action
- Pending items are immediately marked `cancelled` and broadcast via SSE
- In-flight (`downloading`) items are not interrupted — they drain naturally
- Cancelled items are recoverable via Retry (same path as failed items)
- Three persistent header buttons in Download Queue: Cancel / Retry / Clear — always rendered, enabled/disabled by state
- CLI `siphon cancel` command posts to the daemon

**Non-Goals:**
- Per-job or per-item cancel (cancel-all is sufficient for the use case)
- Interrupting an in-flight `YoutubeDL.download()` call (not safe without yt-dlp API support)
- Single-video job cancellation (cancel button is hidden/disabled when only single-video jobs are active)
- Persisting cancelled state to the DB

## Decisions

### 1. Cancel-all endpoint (`POST /jobs/cancel-all`) rather than per-job

**Chosen:** Single endpoint that cancels every non-terminal playlist job.

**Rationale:** The user's mental model is "stop all downloads" (VPN off, wrong settings). A per-job cancel would require the UI to enumerate jobs and fire multiple requests. Cancel-all is simpler on both sides and matches the UX of a single "Cancel" button.

**Alternative considered:** `POST /jobs/{job_id}/cancel` per job — rejected for over-engineering a use case that doesn't need it.

---

### 2. Cancellation is mark-then-drain, not interrupt

**Chosen:** `cancel_all_jobs()` atomically marks all `pending` items as `cancelled` under the `JobStore` lock, then broadcasts SSE events. Items already `downloading` are left alone.

**Rationale:** `YoutubeDL.download()` is a blocking call with no safe abort hook. Python thread kill is not safe. Progress callback exceptions are swallowed by yt-dlp. The drain approach is the only viable option. Practical impact: at most `max_workers` (default 5) items finish before the job goes terminal.

**Alternative considered:** Passing a `threading.Event` cancel flag into `_download_worker` and checking it inside the progress callback — rejected because yt-dlp swallows callback exceptions, so the flag can't actually stop it.

---

### 3. `cancelled` is a terminal item state

**Chosen:** Add `cancelled` to the set `{done, failed}` that `is_terminal()` recognises. `reset_failed_items()` resets both `failed` and `cancelled` items so a single Retry button covers both.

**Rationale:** Treating cancelled as terminal lets the existing job lifecycle logic work unchanged — once all items are `done | failed | cancelled`, `notify_terminal()` fires, SSE subscribers close, and the scheduler proceeds. No special cases needed.

---

### 4. Three always-visible buttons, enabled/disabled by computed state

**Chosen:** Cancel / Retry / Clear always rendered. Disabled via `:disabled` binding. Cancel disables itself on click and shows `Cancelling…` pulse until all playlist jobs are terminal.

**Rationale:** Layout stability — buttons appearing and disappearing would shift surrounding elements. Disabled state communicates clearly what's actionable. The alternative of `v-if` toggling would require placeholder elements anyway to preserve layout.

**Cancel pulse:** CSS `@keyframes` opacity animation on the button text. No spinner needed — text pulse is lightweight and reads as "acknowledged, working."

---

### 5. Clear is frontend-only filtering

**Chosen:** Clear button filters `done` items out of the local `jobs` ref in Vue. Job blocks with zero remaining items are removed from the array. No API call for Clear.

**Rationale:** The backend job store already has `DELETE /jobs/{job_id}` (requires terminal job). But Clear's purpose is just visual cleanup — in-progress jobs can sit alongside cleared-done-rows. A frontend filter is simpler and avoids an API round-trip per job. The progress counter (`N / M`) locks at the job's total item count so it doesn't jump when done rows are cleared.

---

### 6. No confirm dialog on Cancel

**Consistency with Retry:** Retry fires immediately without confirm. Cancel follows the same pattern. Cancelled items are recoverable via Retry, so no destructive data loss occurs.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Race: thread transitions item to `downloading` just before `cancel_all_jobs()` marks it `cancelled` | `cancel_all_jobs()` only transitions items currently in state `pending`. A thread that has already called `update_item_state(…, "downloading")` gets left alone — benign, the item simply drains. |
| User cancels, then immediately starts a new job for the same playlist | `create_job()` already rejects if an active (non-terminal) job exists for the playlist. Once drained items finish and the job goes terminal, a new job can be created. |
| Cancel pulse never resolves (stuck downloading item) | The pulse ends when the job reaches terminal state via SSE `done` event. If SSE drops, terminal state is checked on reconnect/remount via the existing catch-up snapshot in `event_generator`. |
| `siphon cancel` CLI with no active jobs | Returns a clear message: "No active downloads to cancel." Exit 0. |

## Migration Plan

- No DB schema changes — no migration needed
- No breaking changes to existing API endpoints
- Phased: backend first, then UI, then CLI
- Rollback: revert `watcher.py` changes; the UI degrades gracefully (Cancel button stays disabled if endpoint 404s)
