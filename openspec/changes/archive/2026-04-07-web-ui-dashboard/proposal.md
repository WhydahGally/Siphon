## Why

Siphon runs as a Docker container (e.g., on Unraid) with no way to interact with it other than the CLI, which is unwieldy for day-to-day use. A web UI served by the existing FastAPI daemon makes the tool self-contained and accessible via the Unraid WebUI button — no terminal required.

## What Changes

- **New**: A Vue 3 + Vite single-page application served by the FastAPI daemon at port 8000
- **New**: In-memory `JobStore` in the daemon that tracks active download jobs and per-item state for the current session
- **New**: SSE endpoint (`GET /jobs/{id}/stream`) for real-time item-level state push to the browser
- **New**: `POST /jobs` endpoint — creates a download job (playlist or single video) from the UI
- **New**: `GET /jobs` endpoint — returns all active/recent session jobs
- **New**: Static file serving by FastAPI — in production, `GET /` serves the compiled Vue SPA
- **Modified**: Remove the "playlist URL only" guard from `POST /playlists` — single-video URLs are now valid inputs (**BREAKING** for any caller relying on that 400)
- **Modified**: `playlist-watcher-cli` spec — remove the requirement that `siphon add` rejects single-video URLs (the guard was at the wrong layer; `download()` already handles both)

## Capabilities

### New Capabilities

- `web-ui`: The Vue 3 SPA — Dashboard page with URL input, format/quality selectors, auto-rename and auto-sync toggles, and a live download queue. Navigation bar with Dashboard, Library, and Settings tabs (Library and Settings are stubs in this change).
- `job-store`: In-memory job tracking in the daemon. A `DownloadJob` holds the job ID, associated playlist (or None for single videos), total item count, and a list of `JobItem` entries each with state (`pending` | `downloading` | `done` | `failed`), original title, renamed title, and error message. Jobs are session-scoped — not persisted to SQLite.
- `job-api`: REST + SSE API for the job store. `POST /jobs` creates a job and enqueues items for download. `GET /jobs` lists all session jobs. `GET /jobs/{id}/stream` is an SSE endpoint that pushes `JobItemEvent` messages as item states transition.

### Modified Capabilities

- `playlist-watcher-cli`: Remove the scenario "URL is not a playlist → error". Single-video URLs are now accepted by `siphon add` (and the daemon's `POST /playlists`). The `download()` engine already handles both; the check was an incorrect early guard.

## Impact

- `src/siphon/watcher.py`: Add `JobStore`, `DownloadJob`, `JobItem` dataclasses; add `/jobs` endpoints; add SSE streaming response; remove playlist-URL guard; wire FastAPI `StaticFiles` mount for production
- `src/ui/`: New directory — Vue 3 + Vite project with Dashboard, stub Library and Settings pages, and the download queue component
- `Dockerfile`: Add `node` build stage to compile the Vue SPA into `src/ui/dist/`; final image copies `dist/` into the Python image
- `pyproject.toml`: No Python dependency changes (FastAPI already serves static files natively)
- `openspec/specs/playlist-watcher-cli/spec.md`: Delta — remove the single-video rejection requirement
