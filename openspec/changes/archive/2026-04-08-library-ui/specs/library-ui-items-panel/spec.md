## ADDED Requirements

### Requirement: Expandable items panel per playlist
Each playlist row SHALL include an expand button. Clicking it SHALL expand an items panel below that playlist row showing all downloaded items. Only one playlist SHALL have its items panel open at a time (accordion). Clicking the same expand button again SHALL collapse the panel. Clicking the expand button of a different playlist SHALL expand that playlist's panel and collapse the previously open one.

#### Scenario: User expands a playlist
- **WHEN** the user clicks the expand button on a playlist row
- **THEN** the items panel for that playlist SHALL open below the row, showing all downloaded items

#### Scenario: User collapses an open panel
- **WHEN** the user clicks the expand button on the currently expanded playlist
- **THEN** the items panel SHALL close

#### Scenario: User expands a different playlist
- **WHEN** the user clicks the expand button on playlist B while playlist A is expanded
- **THEN** playlist A's panel SHALL close and playlist B's panel SHALL open

---

### Requirement: Items panel height and scrolling
The items panel SHALL have a maximum height of 70% of the available viewport height and SHALL be independently scrollable. Content above and below the expanded row SHALL remain accessible by scrolling the page. The panel SHALL use virtual scrolling (`vue-virtual-scroller` `RecycleScroller`) so that DOM node count stays constant (~15–20) regardless of the number of items.

#### Scenario: Panel exceeds 70vh
- **WHEN** the items list contains more items than fit in 70% of the viewport height
- **THEN** the panel SHALL cap its height and show a vertical scrollbar; the remaining playlists SHALL be visible by scrolling the page

#### Scenario: Panel within 70vh
- **WHEN** the items list is short enough to fit within 70% of the viewport
- **THEN** the panel SHALL size to its content height with no scrollbar

---

### Requirement: Items panel content
Each item row in the panel SHALL display: the original YouTube title (`yt_title`), and if renamed, an arrow followed by the renamed title (`renamed_to`) and a tier badge (`rename_tier`).

#### Scenario: Item with rename
- **WHEN** an item has `renamed_to` set
- **THEN** the row SHALL display `<yt_title> → <renamed_to> [tier]`

#### Scenario: Item without rename
- **WHEN** an item has no `renamed_to` value
- **THEN** the row SHALL display only `yt_title`

---

### Requirement: Items fetched once and cached per session
The Library SHALL fetch item data for a playlist from `GET /playlists/{id}/items` only once per session (and once after each `sync_done` event for that playlist). The fetched data SHALL be stored in an in-memory cache keyed by `playlist_id`. Re-expanding a previously expanded playlist SHALL serve from cache immediately without a new network request. On `sync_done` for a specific `playlist_id`, the cache entry for that playlist SHALL be invalidated; the next expand SHALL re-fetch.

#### Scenario: First expand triggers fetch
- **WHEN** the user expands a playlist that has not been opened yet in this session
- **THEN** the Library SHALL call `GET /playlists/{playlist_id}/items` and cache the result

#### Scenario: Re-expand uses cache
- **WHEN** the user re-expands a playlist that was previously fetched in this session
- **THEN** the items SHALL be rendered from cache immediately with no network request

#### Scenario: Cache invalidated after sync
- **WHEN** a `sync_done` SSE event is received for a `playlist_id`
- **THEN** the cache entry for that `playlist_id` SHALL be cleared, causing the next expand to re-fetch
