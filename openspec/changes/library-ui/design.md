## Context

The daemon (`watcher.py`) is a FastAPI server that already serves the UI as static files. Playlist data lives in SQLite via `registry.py`. The `items` table stores all downloaded tracks per playlist but has no read API. Sync operations run on background threads, currently bypassing the job store entirely. The frontend uses Vue 3 with Vite; the existing Dashboard uses SSE for live download progress via a per-job event queue pattern.

The Library tab is a stub. No playlist management UI exists.

## Goals / Non-Goals

**Goals:**
- Fully implement the Library tab: list playlists, per-row controls (sync, toggles, interval edit, delete), expand/collapse items panel.
- Add a lightweight sync-events SSE channel so the UI can show spinners without polling and without corrupting the Dashboard's job list.
- Add `GET /playlists/{id}/items` API + `siphon playlist-items <name>` CLI.
- Add a reusable `ConfirmButton.vue` for inline two-phase destructive actions.
- Use `vue-virtual-scroller` for smooth rendering of large item lists.

**Non-Goals:**
- Real-time per-track progress during Library syncs (the Dashboard already covers this for first-time downloads; Library only needs start/done signals).
- Pagination of items (virtual scroll handles all list sizes client-side).
- Modal infrastructure (the split-confirm button is sufficient for delete; modals can be introduced in a future change if needed).
- Modifying the SQLite schema.

## Decisions

### D1 — Silent sync via in-memory state + dedicated SSE channel

**Decision:** Maintain a `_syncing_playlists: set[str]` and `_sync_event_queues: List[asyncio.Queue]` on the daemon. `POST /playlists/{id}/sync` adds `playlist_id` to the set, spawns `_sync_parallel`, and broadcasts a `sync_started` event. When `_sync_parallel` finishes it removes the id and broadcasts `sync_done`. A new `GET /playlists/sync-events` SSE endpoint lets the Library subscribe to this single channel for all playlists.

**Why over Option B (full jobs for sync):** Sync operations are not user-initiated downloads — they are scheduled maintenance. Surfacing them in the Download queue would pollute the Dashboard with noise. The Library only needs a boolean is-syncing state per playlist, not per-track progress. The cost of Option B (job type filtering, job store threading, SSE per job) is unjustified for this signal.

**Why over polling:** Polling at 2s adds unnecessary load, is laggy on slow syncs, and keeps a timer alive. A single SSE pipe is event-driven, zero overhead when idle, and already compatible with the existing async/thread bridge pattern used by the job store.

**Reconnect on mount:** `GET /playlists` response is extended with `is_syncing: bool` per entry (derived from `_syncing_playlists` in memory). If the Library mounts while a sync is in progress, the initial load shows the spinner immediately; the SSE connection then captures the terminal event.

**Thread safety:** `_syncing_playlists` is a plain Python `set`. Mutations happen only on background sync threads. Since CPython's GIL serialises dict/set operations, no lock is needed for add/remove. Iterating it for `_playlist_to_dict` is safe under the GIL. An `asyncio.Queue` per subscriber (same bridge as `JobStore._queues`) handles the thread→event-loop bridge.

### D2 — Items fetched on expand, cached in `Library.vue`, never paginated

**Decision:** `GET /playlists/{id}/items` returns all items in a single JSON array. The Library caches responses in a `ref({})` map keyed by `playlist_id`. Virtual scroll (`RecycleScroller` from `vue-virtual-scroller`) renders only visible rows. On collapse the cache is retained; on Library unmount Vue GC frees it.

**Why not paginated API:** Pagination adds offset/limit params, server complexity, and client-side page management. With virtual scroll, rendering 1000 items is trivially smooth — the bottleneck is DOM nodes, not JS array size. Virtual scroll eliminates that bottleneck. A single DB `SELECT` of 1000 rows is microseconds in SQLite.

**Why retain cache on collapse:** The most common interaction pattern is opening/closing different playlists within the same session. Re-fetching from the DB on every expand would feel sluggish and is unnecessary given the data is static (items only change after a sync, at which point the cache can be invalidated on `sync_done`).

**Cache invalidation:** When the Library receives a `sync_done` event for a `playlist_id`, it deletes `itemCache[playlist_id]`. Next expand re-fetches. This keeps items fresh after every sync automatically.

### D3 — Interval display/edit: DD:HH:MM:SS ↔ seconds entirely in the UI

**Decision:** `check_interval_secs` stays as raw seconds in the DB and on the wire. The UI converts for display (e.g. `86400 → "every 24h"`, `3600 → "every 1h"`, `600 → "every 10m"`, `45 → "every 45s"`) and parses `DD:HH:MM:SS` input to seconds before `PATCH /playlists/{id}`.

**Why not change the backend format:** The scheduler does pure arithmetic on raw seconds. Changing the stored format would require migrating existing rows, updating all scheduler math, and modifying every caller of `set_playlist_interval`. The UI is the only consumer that needs a human-readable format, so the conversion belongs there.

**Inline editing UX:** The interval is displayed as a clickable text. Clicking opens an `<input>` pre-populated with the current value in `DD:HH:MM:SS`. Enter or blur triggers `PATCH`; Escape reverts. A subtle underline or muted border signals editability without cluttering the row.

### D4 — ConfirmButton.vue as a reusable slot-less component

**Decision:** A self-contained `ConfirmButton.vue` accepts `label` (string) and `dangerLabel` (string, default "Confirm") props. Internal `confirming` ref drives the two-phase render. Emits `confirm` when the user clicks the confirm phase. Emits nothing on cancel. Guards: auto-reverts to initial state after 5s of inaction to prevent accidental stale confirms.

**Why not a modal:** The information needed for confirming a playlist delete is already visible on the row (the name). A modal adds a context switch and modal infrastructure (focus trap, overlay, portal) that doesn't exist yet. The split-button is sufficient and is self-contained.

### D5 — Component decomposition

```
Library.vue               ← page container; holds playlists[], itemCache, expandedId
  PlaylistRow.vue         ← one per playlist; all row state (edit mode, confirming delete)
    ConfirmButton.vue     ← reusable split-confirm button
  PlaylistItemsPanel.vue  ← mounted inside PlaylistRow when expanded=true; uses RecycleScroller
```

`expandedId` lives in `Library.vue` (single ref, accordion logic). `PlaylistRow` emits `expand` / `collapse` and `deleted`. `PlaylistItemsPanel` receives `items[]` and a `loading` bool passed down by `Library.vue`; it does not fetch — Library fetches and passes down.

## Risks / Trade-offs

**[Risk] SSE connection dropped mid-sync** → `sync_done` event never received, spinner stuck. Mitigation: the SSE client reconnects automatically (browsers rebuild `EventSource` on close). On reconnect, `GET /playlists` is re-fetched to resync `is_syncing` truth from the daemon's in-memory state.

**[Risk] Daemon restart during sync** → `_syncing_playlists` resets to empty; `sync_done` is never broadcast; spinner would be stuck on a reconnect. Mitigation: after daemon restart `GET /playlists` returns `is_syncing: false` for all playlists; the Library client sees this on reconnect and clears all spinners. The sync itself did not complete, so `last_synced_at` will not have been updated — the user can trigger a manual sync.

**[Risk] Stale item cache after manual sync from CLI** → the Library cache is in browser memory only; a sync triggered via `siphon sync` outside the UI won't invalidate it. Mitigation: acceptable for this scope; the user can navigate away and back to Library to reload.

**[Trade-off] vue-virtual-scroller dependency** → adds ~12KB gzip and a third-party dep. Benefit: smooth 60fps for 1000-item lists without any custom scroll logic. The library is MIT-licensed, actively maintained, and compatible with Vue 3.

## Migration Plan

No schema migrations. No breaking API changes. The new endpoints are additive. Frontend changes are isolated to the Library tab and new components. `ConfirmButton` only activates where explicitly used.

Deployment: normal `docker build` / `npm run build` cycle.

## Open Questions

None — all decisions are resolved in this design.
