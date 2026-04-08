## Why

The Library tab is currently a stub ("Coming soon."). Users have no way to view, manage, or interact with their registered playlists from the UI. All playlist management today requires the CLI, which is intended only as a setup/debug tool. The Library tab is one of the two primary pages in the nav and needs to be fully functional.

## What Changes

- The Library tab renders a live list of all registered playlists, each showing name, item count, registration date, last-synced time, and current sync state.
- Each playlist row exposes inline controls: Sync Now button, Auto Rename toggle, Auto Sync toggle, and an editable sync interval field.
- A reusable split-confirm button component handles destructive delete with inline confirmation (no modal required).
- Clicking a playlist's expand button reveals a scrollable, cached list of all downloaded items in that playlist; only one playlist can be expanded at a time (accordion).
- Sync operations triggered from the Library are silent — they do not appear in the Dashboard's Downloads queue.
- A lightweight SSE endpoint (`GET /playlists/sync-events`) broadcasts `sync_started` and `sync_done` events per playlist, enabling real-time spinner state in the UI without polling, and allowing correct spinner display when the Library is opened mid-sync.
- A new `GET /playlists/{playlist_id}/items` API endpoint returns the full list of downloaded items for a playlist.
- A new `siphon playlist-items <name>` CLI command retrieves and displays items for a playlist via the daemon API.
- `vue-virtual-scroller` is added as a UI dependency for smooth rendering of large item lists (up to ~1000 items).

## Capabilities

### New Capabilities

- `library-ui-playlist-list`: The Library page renders all registered playlists with per-row controls (sync, toggles, interval edit, delete).
- `library-ui-items-panel`: An expandable, accordion-style panel per playlist displaying downloaded items using virtual scrolling; items are fetched once and cached in memory per session.
- `library-ui-sync-events`: A new SSE endpoint and in-memory sync state set on the daemon that broadcasts sync lifecycle events (`sync_started`, `sync_done`) per playlist without creating jobs in the job store.
- `playlist-items-api`: A new `GET /playlists/{playlist_id}/items` endpoint and `list_items_for_playlist()` registry function.
- `playlist-items-cli`: A new `siphon playlist-items <name>` CLI command that prints all downloaded items for a named playlist.
- `confirm-button`: A reusable `ConfirmButton.vue` component that renders a single action button which splits into Confirm / Cancel on first click.

### Modified Capabilities

- `playlist-registry`: `list_playlists()` response shape gains `is_syncing: bool` derived from daemon in-memory state; `_playlist_to_dict` is extended to include this field.
- `web-ui`: Library page is implemented (previously a stub); sync interval input updated to use DD:HH:MM:SS format in display with seconds stored in DB.

## Impact

- **Backend** (`watcher.py`): New `_syncing_playlists` set and `_sync_event_queues` list on daemon; `POST /playlists/{id}/sync` updated to publish SSE events; `GET /playlists/sync-events` SSE endpoint added; `GET /playlists/{id}/items` endpoint added; `_playlist_to_dict` extended; `siphon playlist-items` subcommand added.
- **Backend** (`registry.py`): New `list_items_for_playlist(playlist_id)` function.
- **Frontend** (`src/ui/`): `Library.vue` fully implemented; new components `PlaylistRow.vue`, `PlaylistItemsPanel.vue`, `ConfirmButton.vue`; `vue-virtual-scroller` added to `package.json`.
- **No schema changes**: All data is already present in the `items` table; `is_syncing` is daemon-memory-only.
- **No breaking changes** to existing API contracts.
