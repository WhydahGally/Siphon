## Context

Siphon's FastAPI daemon already runs on port 8000 and exposes a REST API for all playlist and settings operations. The CLI is intentionally a thin HTTP client over this API. The daemon is the authoritative process — it owns the DB, the scheduler, and now the in-memory job state.

The Unraid WebUI button expects a URL (typically `http://<container-ip>:<port>`) to open in a browser. Serving the SPA from the same port 8000 as the API means zero additional configuration — one port, one container entry point.

Current state: no web UI exists. Downloads initiated via CLI fire and are never observable again until they complete and appear in the DB.

## Goals / Non-Goals

**Goals:**
- Serve a Vue 3 SPA from `GET /` on the existing port 8000 in production
- Provide a Dashboard with URL input, format/quality controls, download queue with real-time item-level state
- Track in-memory job state in the daemon (session-scoped, not persisted)
- Push item state transitions to the browser via SSE
- Support both playlist URLs and single-video URLs in the web UI and daemon API
- Development workflow: Vue Vite dev server on `:5173` proxies API calls to `:8000`, no Docker rebuild required
- Multi-stage Dockerfile: Node build stage compiles SPA; Python image copies `dist/`

**Non-Goals:**
- Library and Settings pages are stubs (navigation routing only, no full implementation)
- Byte-level download progress (no per-item progress bar, no speed/ETA display)
- Persisting job history to SQLite
- Multi-user / auth
- WebSockets (SSE is sufficient for unidirectional push)

## Decisions

### D1: SSE over polling for real-time queue updates

**Decision**: Use Server-Sent Events (`GET /jobs/{id}/stream`) to push item state changes to the browser.

**Alternatives considered**:
- **Polling** (`GET /jobs/{id}` every 2–3 seconds): Simple but introduces visible lag between state transitions and UI update. Gets choppy when N items are cycling through `downloading → done` rapidly.
- **WebSockets**: Bidirectional — more than needed here. SSE is a one-way push channel, which is exactly the shape of "daemon tells browser what happened". FastAPI supports SSE natively via `StreamingResponse` + `asyncio.Queue`.

**Rationale**: SSE is the right primitive. Item-level state changes are low-frequency events (one per completed download). The browser opens one persistent HTTP connection and receives newline-delimited JSON events. Clean, simple, fits the existing FastAPI stack.

### D2: In-memory JobStore (not persisted)

**Decision**: `JobStore` is a plain Python dict keyed by `job_id` (UUID), held in module-level state on the daemon. Not written to SQLite.

**Alternatives considered**:
- **SQLite jobs table**: Persistent across restarts, but jobs in flight at restart time would show a frozen/inconsistent state. Added schema complexity for ephemeral data.
- **Redis**: Overkill — adds an external dependency to a self-contained container tool.

**Rationale**: A page refresh doesn't restart the daemon. As long as the daemon is running, `GET /jobs` returns current state. If the daemon restarts (container restart), downloads were interrupted anyway — stale job records would be misleading. Session-scoped is the honest model.

**Structure**:
```python
@dataclass
class JobItem:
    video_id: str
    yt_title: str
    state: str          # "pending" | "downloading" | "done" | "failed"
    renamed_to: Optional[str]
    error: Optional[str]
    started_at: Optional[float]
    finished_at: Optional[float]

@dataclass
class DownloadJob:
    job_id: str
    playlist_id: Optional[str]   # None for single-video jobs
    playlist_name: Optional[str]
    items: List[JobItem]
    created_at: float
```

`total` and `done` are computed properties to avoid sync bugs.

### D3: `POST /jobs` as the UI download trigger (not `POST /playlists/{id}/sync`)

**Decision**: The UI posts to `POST /jobs`, which:
1. Probes the URL (playlist or single video) to get metadata
2. Registers the playlist in the DB if it's a new playlist URL (same as `POST /playlists` but merged)
3. Creates a `DownloadJob`, enumerates items, and dispatches workers
4. Returns `{ job_id }` immediately (202 Accepted)

**Alternatives considered**:
- **Reuse `POST /playlists` + `POST /playlists/{id}/sync`**: Would require two roundtrips from the UI. The sync endpoint fires and forgets with no job ID returned — the UI would have no handle to subscribe to SSE.
- **Add job_id return to existing sync endpoints**: Possible, but sync endpoints are also called by the scheduler internally. Mixing job tracking into the scheduler path adds complexity.

**Rationale**: `POST /jobs` is a clean new surface. It handles the full flow the UI needs (probe → register if needed → download → stream). The CLI and scheduler continue using their existing paths unchanged.

### D4: Vue 3 + Vite over Svelte

**Decision**: Vue 3 with Composition API (`<script setup>`) and Vite.

**Rationale**: Explicit lifecycle hooks (`onMounted`, `onUnmounted`) make SSE setup/teardown easy to reason about. Template syntax is plain HTML with directives — familiar to someone with HTML/CSS/JS background. Scales well to Library and Settings pages. Vite's HMR proxy feature enables the local dev workflow with zero Docker rebuilds.

### D5: Folder structure

```
src/
  siphon/          ← Python backend (unchanged)
  ui/              ← Vue 3 + Vite frontend
    index.html
    vite.config.js
    package.json
    src/
      main.js
      App.vue
      components/
        NavBar.vue
        Dashboard.vue
        DownloadForm.vue
        DownloadQueue.vue
        QueueItem.vue
        Library.vue      (stub)
        Settings.vue     (stub)
```

In production, FastAPI mounts `src/ui/dist/` as `StaticFiles(html=True)` at `/`. The API routes (`/playlists`, `/jobs`, `/settings`, `/health`) are registered before the static mount — FastAPI resolves routes in order.

### D6: Dockerfile multi-stage build

```
Stage 1 (node:22-slim):
  COPY src/ui/ .
  RUN npm ci && npm run build
  → produces src/ui/dist/

Stage 2 (python:3.12-slim):
  (existing steps)
  COPY --from=stage1 /build/dist /app/src/ui/dist
```

In development, `src/ui/dist/` doesn't need to exist — the Vite dev server serves the SPA separately, and Vite's proxy config routes `/playlists`, `/jobs`, `/settings` to `http://localhost:8000`.

### D7: Single-video URL support

The "playlist URL only" guard lives at line 627 of `watcher.py` inside `api_add_playlist`. The `download()` engine has always handled both. The guard is removed from `api_add_playlist`. The `playlist-watcher-cli` spec delta removes the corresponding scenario. For single-video URLs:
- `playlist_name` is set to the video title
- `DownloadJob.playlist_id` is `None` (single-video jobs are not registered in the playlist DB)
- No scheduler timer is armed (watched=False implicitly, no auto-sync concept)
- DB tracking (items table, failed_downloads) is skipped — job state is in-memory only
- Downloaded file goes directly into `output_dir` (no subfolder)

## Risks / Trade-offs

- **SSE connection management**: Each open browser tab holds one SSE connection per active job. If many jobs exist simultaneously, this multiplies. Mitigation: the SSE endpoint should close gracefully when the job transitions to a terminal state (all items done or failed).
- **Job accumulation**: `JobStore` grows indefinitely within a daemon session. Mitigation: cap at last N=50 jobs, or expose a `DELETE /jobs/{id}` endpoint so the UI's "Clear list" button prunes the store.
- **Vite proxy in dev only**: If someone runs the Vue dev server against a remote Siphon daemon (not localhost), they need to update `vite.config.js`. Acceptable — this is a dev-time concern.
- **Static file mount order in FastAPI**: `app.mount("/", StaticFiles(...))` must come after all API route registrations. If a future route is added without care, it could be shadowed by the static mount. Mitigation: document the ordering constraint in a comment.

## Migration Plan

1. No DB schema changes required — `JobStore` is in-memory only
2. Remove the playlist-URL guard (small, safe, unbreaks single-video support)
3. Add `/jobs` endpoints alongside existing endpoints (additive, no existing routes change)
4. Add `StaticFiles` mount — API routes registered first, so existing API callers are unaffected
5. Dockerfile multi-stage build is additive — existing single-stage build can remain for dev until the UI is ready

## Open Questions

- None blocking implementation. Format/quality selectors, SSE behavior, and job structure are fully specified from the exploration session.
