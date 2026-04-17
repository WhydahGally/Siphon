## ADDED Requirements

### Requirement: Inline rename editing in PlaylistItemsPanel
Each item row in the Library's PlaylistItemsPanel SHALL display a pencil icon on hover over the renamed portion of the row. Clicking the pencil SHALL replace the `renamed_to` text (or insert an arrow + text area for non-renamed items) with an inline text input prefilled with the current `renamed_to` value (or `yt_title` if `renamed_to` is NULL). A Save button SHALL appear to the right of the text input. The pencil icon SHALL be subtle and only visible on hover.

#### Scenario: Hover reveals pencil on auto-renamed item
- **WHEN** the user hovers over an item row that has `renamed_to` set
- **THEN** a subtle pencil icon SHALL appear next to the renamed value

#### Scenario: Hover reveals pencil on non-renamed item
- **WHEN** the user hovers over an item row that has `renamed_to` as NULL
- **THEN** a subtle pencil icon SHALL appear at the end of the `yt_title`

#### Scenario: Click pencil on auto-renamed item enters edit mode
- **WHEN** the user clicks the pencil on an item with `renamed_to='Artist - Track'`
- **THEN** the `renamed_to` text SHALL be replaced with a text input prefilled with `Artist - Track`, and a Save button SHALL appear to the right

#### Scenario: Click pencil on non-renamed item enters edit mode
- **WHEN** the user clicks the pencil on an item with `renamed_to` as NULL and `yt_title='Some Title'`
- **THEN** an arrow and text input SHALL appear inline after the `yt_title`, prefilled with `Some Title`, with a Save button to the right

#### Scenario: Save triggers rename API call
- **WHEN** the user edits the text and clicks Save (or presses Enter)
- **THEN** the UI SHALL call `PUT /playlists/{playlist_id}/items/{video_id}/rename` with the new name, update the local item state on success, and exit edit mode showing the new name with tier badge `manual`

#### Scenario: Click outside cancels edit
- **WHEN** the user clicks anywhere outside the text input while in edit mode
- **THEN** the edit SHALL be cancelled and the original display SHALL be restored

#### Scenario: Escape key cancels edit
- **WHEN** the user presses Escape while the text input is focused
- **THEN** the edit SHALL be cancelled and the original display SHALL be restored

---

### Requirement: Inline rename editing in QueueItem
Each completed item in the Dashboard's download queue SHALL display a pencil icon on hover over the renamed portion. The edit interaction SHALL be identical to PlaylistItemsPanel. The pencil SHALL only appear for items in `done` state. For playlist items, the Save action SHALL call `PUT /playlists/{playlist_id}/items/{video_id}/rename`. For single-video items, the Save action SHALL call `PUT /jobs/{job_id}/items/{video_id}/rename`.

#### Scenario: Pencil appears only on done items
- **WHEN** the user hovers over a queue item in `done` state
- **THEN** a subtle pencil icon SHALL appear next to the renamed value

#### Scenario: Pencil does not appear on non-done items
- **WHEN** the user hovers over a queue item in `downloading`, `pending`, `failed`, or `cancelled` state
- **THEN** no pencil icon SHALL appear

#### Scenario: Save on playlist item calls playlist rename endpoint
- **WHEN** the user saves a rename on a queue item that has a `playlist_id`
- **THEN** the UI SHALL call `PUT /playlists/{playlist_id}/items/{video_id}/rename`

#### Scenario: Save on single-video item calls job rename endpoint
- **WHEN** the user saves a rename on a queue item that has no `playlist_id` (single-video)
- **THEN** the UI SHALL call `PUT /jobs/{job_id}/items/{video_id}/rename`

#### Scenario: Renamed value persists across page refresh
- **WHEN** the user renames a single-video item and then refreshes the page
- **THEN** the `GET /jobs` response SHALL include the updated `renamed_to` value from the JobStore

---

### Requirement: Auto-rename-aware display logic
The UI SHALL show the `yt_title → renamed_to` arrow format and tier badge only when the item was meaningfully renamed. Both `PlaylistItemsPanel` and `QueueItem` SHALL accept an `autoRename` boolean prop indicating whether auto-rename was enabled for the playlist/job.

#### Scenario: Auto-rename ON — arrow and tier badge shown
- **WHEN** `autoRename` is true and `renamed_to` is populated
- **THEN** the UI SHALL display the arrow format (`yt_title → renamed_to`) with the tier badge

#### Scenario: Auto-rename OFF — no arrow, plain title shown
- **WHEN** `autoRename` is false and `rename_tier` is not `'manual'`
- **THEN** the UI SHALL display only the plain `yt_title` without arrow or tier badge, even if `renamed_to` is populated (passthrough rename)

#### Scenario: Manual rename — arrow shown regardless of auto-rename setting
- **WHEN** `rename_tier` is `'manual'`, regardless of `autoRename` value
- **THEN** the UI SHALL display the arrow format (`yt_title → renamed_to`) with the `manual` tier badge

#### Scenario: Tier badge visibility
- **WHEN** the arrow format is shown
- **THEN** the tier badge SHALL appear if `autoRename` is true OR `rename_tier` is `'manual'`
