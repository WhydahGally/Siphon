## 1. Backend — Registry

- [x] 1.1 Add `list_items_for_playlist(playlist_id: str) -> list` to `registry.py`, returning all `items` rows for the playlist ordered by `downloaded_at` ascending

## 2. Backend — Sync Events Infrastructure

- [x] 2.1 Add `_syncing_playlists: set[str]` and `_sync_event_queues: list` module-level globals to `watcher.py`
- [x] 2.2 Add `_broadcast_sync_event(event: str, playlist_id: str)` helper that uses the async/thread bridge (same pattern as `JobStore`) to push JSON to all `_sync_event_queues` subscribers
- [x] 2.3 Update `POST /playlists/{id}/sync`: add `playlist_id` to `_syncing_playlists` and broadcast `sync_started` before spawning the thread
- [x] 2.4 Update `_sync_parallel`: remove `playlist_id` from `_syncing_playlists` and broadcast `sync_done` at the end (in a try/finally to ensure it fires on error too)
- [x] 2.5 Add `GET /playlists/sync-events` SSE endpoint: registers an `asyncio.Queue`, streams JSON events to the client, removes queue on disconnect

## 3. Backend — Playlist API Extensions

- [x] 3.1 Update `_playlist_to_dict` to include `is_syncing: bool` derived from `_syncing_playlists`
- [x] 3.2 Add `GET /playlists/{playlist_id}/items` endpoint using `registry.list_items_for_playlist`; return 404 if playlist does not exist

## 4. Backend — CLI Command

- [x] 4.1 Add `playlist-items` subparser to the argparse setup in `watcher.py` with a required `name` positional argument
- [x] 4.2 Implement `cmd_playlist_items` function: resolve playlist by name via `GET /playlists`, then fetch items via `GET /playlists/{id}/items`, print header + one line per item (`yt_title` or `yt_title → renamed_to`)
- [x] 4.3 Wire `playlist-items` subcommand to `cmd_playlist_items` in the command dispatch table

## 5. Frontend — Dependencies and Utilities

- [x] 5.1 Install `vue-virtual-scroller` (`npm install vue-virtual-scroller`)
- [x] 5.2 Register `vue-virtual-scroller` globally or per-component in `main.js`
- [x] 5.3 Add `secsToHuman(secs)` utility in a shared JS helper (e.g. `src/utils/interval.js`): returns "every Xs", "every Xm", "every Xh", or "every Xd"
- [x] 5.4 Add `ddhhmmssTosecs(str)` utility in the same helper: parses `DD:HH:MM:SS` string to total seconds; returns `null` on invalid input

## 6. Frontend — ConfirmButton Component

- [x] 6.1 Create `src/ui/src/components/ConfirmButton.vue` with `label` and `dangerLabel` (default `"Confirm"`) props and `confirm` emit
- [x] 6.2 Implement internal `confirming` ref and two-phase render (single button → split Confirm/Cancel)
- [x] 6.3 Implement 5-second auto-revert timeout (cleared on Confirm or Cancel)
- [x] 6.4 Style both phases to match existing design tokens (`--error` for Confirm, `--border`/`--surface-2` for Cancel)

## 7. Frontend — PlaylistItemsPanel Component

- [x] 7.1 Create `src/ui/src/components/PlaylistItemsPanel.vue` accepting `items[]` and `loading` props
- [x] 7.2 Wire `RecycleScroller` from `vue-virtual-scroller` for the items list
- [x] 7.3 Style item rows to match `QueueItem.vue` patterns: `yt_title`, arrow, `renamed_to`, tier badge
- [x] 7.4 Apply `max-height: 70vh` + `overflow-y: auto` to the panel container

## 8. Frontend — PlaylistRow Component

- [x] 8.1 Create `src/ui/src/components/PlaylistRow.vue` accepting a `playlist` prop and emitting `deleted`, `expand`, `collapse`
- [x] 8.2 Render playlist name, item count, `added_at` (formatted), `last_synced_at` (formatted, "never synced" if null)
- [x] 8.3 Render syncing spinner (reuse `.spinner` CSS class from `QueueItem.vue`) when `playlist.is_syncing` is true or local `syncing` state is true; render "Sync now" button otherwise
- [x] 8.4 Implement "Sync now" button: POST `/playlists/{id}/sync`, set local `syncing = true`
- [x] 8.5 Implement Auto Rename toggle wired to `PATCH /playlists/{id}` with `auto_rename`
- [x] 8.6 Implement Auto Sync toggle wired to `PATCH /playlists/{id}` with `watched`
- [x] 8.7 Implement inline interval editor: display text using `secsToHuman`, click-to-edit opens `<input>` in DD:HH:MM:SS format, Enter/blur calls `PATCH /playlists/{id}` with parsed seconds, Escape reverts
- [x] 8.8 Integrate `ConfirmButton` for delete: on `confirm` emit call `DELETE /playlists/{id}`, emit `deleted` on 204
- [x] 8.9 Integrate `PlaylistItemsPanel`: render below row when `expanded` prop is true, pass `items` and `loading` from parent
- [x] 8.10 Style the row to match the Dashboard's card/section aesthetic using `--surface`, `--surface-2`, `--border`, `--radius`

## 9. Frontend — Library Page

- [x] 9.1 Implement `Library.vue`: replace stub with full component; `playlists` ref, `itemCache` ref (object), `expandedId` ref, `syncingIds` set (or rely on `playlist.is_syncing`)
- [x] 9.2 On mount: fetch `GET /playlists` and populate `playlists`; open SSE connection to `GET /playlists/sync-events`
- [x] 9.3 Handle `sync_started` SSE event: mark the matching playlist as syncing in local state
- [x] 9.4 Handle `sync_done` SSE event: clear syncing state for playlist, re-fetch that playlist via `GET /playlists/{id}` to update `last_synced_at`, invalidate `itemCache[playlist_id]`
- [x] 9.5 Implement accordion expand logic: when a row emits `expand`, set `expandedId`; if `itemCache[id]` is missing, fetch `GET /playlists/{id}/items` and cache result; when row emits `collapse`, clear `expandedId`
- [x] 9.6 Handle `deleted` event from `PlaylistRow`: remove playlist from local `playlists` array and clear `itemCache[id]`
- [x] 9.7 On unmount: close the sync-events SSE connection
- [x] 9.8 Render empty state when `playlists` is empty
- [x] 9.9 Apply `padding: 32px 0` layout matching Dashboard

## 10. Verification

- [ ] 10.1 Verify `siphon playlist-items <name>` prints correct output for a known playlist
- [ ] 10.2 Verify `GET /playlists/{id}/items` returns correct items via `curl` or browser
- [ ] 10.3 Verify `GET /playlists/sync-events` streams `sync_started` and `sync_done` events when a sync is triggered
- [ ] 10.4 Verify `GET /playlists` includes `is_syncing: true` while a sync is running
- [ ] 10.5 Verify Library tab renders all playlists and per-row controls work (toggle, interval edit, sync, delete)
- [ ] 10.6 Verify expand/collapse accordion: only one panel open at a time; re-expand uses cache (check Network tab — no second request)
- [ ] 10.7 Verify sync spinner appears immediately on Library mount if a sync is already in progress
- [ ] 10.8 Verify Dashboard queue unchanged after triggering a sync from Library
- [ ] 10.9 Verify ConfirmButton auto-reverts after 5s with no action
- [ ] 10.10 Verify virtual scroll is smooth with a large playlist (100+ items)
