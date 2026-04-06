## 1. Backend — Daemon API (watcher.py)

- [x] 1.1 Define `JobItem` dataclass in `watcher.py` with fields: `video_id`, `yt_title`, `state` (literal `"pending"|"downloading"|"done"|"failed"`), `renamed_to`, `error`, `started_at`, `finished_at`
- [x] 1.2 Define `DownloadJob` dataclass with fields: `job_id`, `playlist_id`, `playlist_name`, `items`, `created_at`; add computed properties `total`, `done_count`, `failed_count` derived from `items`
- [x] 1.3 Implement `JobStore` class with `create_job()`, `get_job()`, `list_jobs()`, `delete_job()`, `update_item_state()`, and an `asyncio.Queue` per job for SSE fan-out; enforce 50-job cap with oldest-terminal eviction
- [x] 1.4 Instantiate module-level `_job_store: JobStore` alongside the existing `_scheduler`; initialise at daemon startup in `_lifespan`
- [x] 1.5 Remove the playlist-URL guard (`if "list=" not in url...`) from `api_add_playlist`
- [x] 1.6 Implement `POST /jobs` endpoint: probe URL with `_fetch_playlist_info`, register playlist if new (reusing `registry.add_playlist`), create job in `_job_store`, dispatch `_run_download_job` in a background thread, return `202 {"job_id": ...}`
- [x] 1.7 Implement `_run_download_job(job_id, ...)`: iterates job items, calls `_download_worker` per item, drives state transitions (`pending→downloading→done/failed`) via `_job_store.update_item_state()` after each worker result
- [x] 1.8 Implement `GET /jobs` endpoint: returns `[_job_to_dict(j) for j in _job_store.list_jobs()]`
- [x] 1.9 Implement `GET /jobs/{job_id}/stream` SSE endpoint using `StreamingResponse` with `text/event-stream`; subscribes to the job's `asyncio.Queue`, yields JSON events on state transitions, sends a final `event: done` and closes when all items are terminal; returns 404 if job not found
- [x] 1.10 Implement `DELETE /jobs/{job_id}` endpoint: returns 409 if any item is `pending` or `downloading`; removes job from store and returns 204
- [x] 1.11 Implement `POST /jobs/{job_id}/retry-failed` endpoint: resets failed items to `pending`, re-dispatches the subset to `_run_download_job` in a background thread, returns `200 {"retried": N}`
- [x] 1.12 Wire `app.mount("/", StaticFiles(directory="src/ui/dist", html=True))` at the bottom of `watcher.py` after all route registrations; guard with `os.path.isdir` so the daemon still starts without the built UI present (dev mode)

## 2. Vite + Vue 3 Project Scaffold

- [x] 2.1 Create `src/ui/` directory; initialise with `npm create vite@latest . -- --template vue` (or equivalent); verify `package.json` and `vite.config.js` are created
- [x] 2.2 In `vite.config.js`, add a `server.proxy` config that forwards `/playlists`, `/jobs`, `/settings`, `/health` to `http://localhost:8000`
- [x] 2.3 Add `.gitignore` entry for `src/ui/node_modules/` and `src/ui/dist/`
- [x] 2.4 Remove boilerplate from `src/ui/src/` (default Vite counter component, assets); confirm blank app loads at `http://localhost:5173`
- [x] 2.5 Install no additional runtime dependencies beyond Vue 3 (keep bundle lean); confirm `npm run build` produces `src/ui/dist/`

## 3. NavBar Component

- [x] 3.1 Create `src/ui/src/components/NavBar.vue` with "Siphon" text on the left and three nav buttons (Dashboard, Library, Settings)
- [x] 3.2 Implement active-page highlighting using Vue Router's `router-link-active` class or a simple prop passed from `App.vue`
- [x] 3.3 Wire routing in `App.vue`: Dashboard is the default route (`/`), Library is `/library`, Settings is `/settings`

## 4. Dashboard — URL Input and Format Controls

- [x] 4.1 Create `src/ui/src/components/DownloadForm.vue`; add a URL text input and a Download button
- [x] 4.2 Add the Format dropdown with all five formats (mp3, opus, mp4, mkv, webm); implement a visual separator (e.g., `<optgroup>` or a styled divider `<li>`) between the audio group (mp3, opus) and video group (mp4, mkv, webm)
- [x] 4.3 Add the Quality selector; bind its `disabled` state to whether the selected format is audio; when disabled, always show "best" and add a `title` attribute (tooltip) with the text "Audio is always downloaded at the best quality available"
- [x] 4.4 Implement computed `isAudio` flag based on the selected format; when `isAudio` is true, Quality selector is non-interactive
- [x] 4.5 Add "Auto rename" toggle (default: on); on component mount, call `GET /settings/mb-user-agent`; if the returned value is null, show a warning icon (`⚠`) adjacent to the toggle with a tooltip explaining that mb-user-agent must be configured
- [x] 4.6 Add "Auto sync" toggle (default: on); compute `isPlaylist` from the URL input value (contains `list=`); show the toggle only when `isPlaylist` is true; when toggle is on and `isPlaylist` is true, show an interval input with default value 86400 and placeholder "24 hours"
- [x] 4.7 Implement Download button click handler: validate URL is non-empty; disable button during request; POST to `/jobs` with `{ url, format, quality, auto_rename, watched: autoSync, check_interval_secs: interval (if playlist + autoSync) }`; on 202, emit `job-created` event with `job_id`; re-enable button on error and show error message

## 5. Dashboard — Download Queue

- [x] 5.1 Create `src/ui/src/components/DownloadQueue.vue`; on mount, call `GET /jobs` and populate local `jobs` reactive array
- [x] 5.2 Implement `connectSSE(job_id)` method: opens `EventSource('/jobs/{job_id}/stream')`; on each message, finds the matching job in `jobs` and updates the item's state fields; closes the `EventSource` on receipt of `event: done`
- [x] 5.3 Listen for `job-created` event from `DownloadForm`; push the new job to `jobs` and call `connectSSE(job_id)` immediately
- [x] 5.4 Implement item-level sort order within each job: `downloading` first, then `pending`, then `done`, then `failed` — use a computed sorted list
- [x] 5.5 Create `src/ui/src/components/QueueItem.vue`; render state-specific UX: spinner for `downloading`, check mark for `done` (with `yt_title → renamed_to` if `renamed_to` is set), red-tinted row for `failed` (with error text and per-row Retry button), neutral row for `pending`
- [x] 5.6 Implement the progress summary line: "X / Y downloaded" where X is `done_count` and Y is `total` for the active job
- [x] 5.7 Implement "Retry failed" button: POST to `/jobs/{id}/retry-failed`; on success, update failed items back to `pending` state in the local `jobs` array
- [x] 5.8 Implement per-item Retry button: POST to `/jobs/{id}/retry-failed` (same endpoint handles subset — server resets all failed; UI re-establishes SSE if not already open)
- [x] 5.9 Implement "Clear list" button: for each job where all items are terminal, call `DELETE /jobs/{id}`; on success, remove those jobs from the local `jobs` array
- [x] 5.10 Handle SSE reconnection on page refresh: on mount, after fetching `GET /jobs`, call `connectSSE` for any job that has items still in `pending` or `downloading` state

## 6. Library and Settings Stubs

- [x] 6.1 Create `src/ui/src/components/Library.vue` with a placeholder message ("Library — coming soon")
- [x] 6.2 Create `src/ui/src/components/Settings.vue` with a placeholder message ("Settings — coming soon")

## 7. Dockerfile Multi-stage Build

- [x] 7.1 Add a first build stage to `Dockerfile` using `node:22-slim`; copy `src/ui/`; run `npm ci && npm run build`; output lands in `/build/dist`
- [x] 7.2 In the Python stage, add `COPY --from=0 /build/dist /app/src/ui/dist`
- [ ] 7.3 Verify `docker build` succeeds end-to-end and `GET /` from the container returns the Vue SPA index page

## 8. Verification

- [ ] 8.1 Run `siphon watch` locally and `npm run dev` in `src/ui/`; confirm the Dashboard loads at `http://localhost:5173` and the Vite proxy correctly reaches the daemon at `:8000`
- [ ] 8.2 Submit a playlist URL via the UI; confirm the job appears in the queue with items in `pending` state, transitions to `downloading`, and eventually `done`
- [ ] 8.3 Submit a single-video URL; confirm auto-sync toggle is hidden and the download completes successfully
- [ ] 8.4 Trigger a deliberately failing URL; confirm the item row turns red and the Retry button appears
- [ ] 8.5 Click "Retry failed"; confirm items return to `pending` and re-attempt download
- [ ] 8.6 Click "Clear list" after a job completes; confirm the job is removed from the UI and `DELETE /jobs/{id}` returns 204
- [ ] 8.7 Refresh the browser mid-download; confirm the queue repopulates from `GET /jobs` and SSE resumes
- [ ] 8.8 Select an audio format; confirm Quality selector shows "best" and is non-interactive; hover over it and confirm tooltip text appears
- [ ] 8.9 Enable Auto rename with no `mb-user-agent` configured; confirm the warning icon and tooltip appear
- [ ] 8.10 Build the Docker image; open `http://localhost:8000` in a browser; confirm the SPA loads and all Dashboard features work
