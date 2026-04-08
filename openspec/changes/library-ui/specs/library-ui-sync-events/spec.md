## ADDED Requirements

### Requirement: Sync events SSE endpoint
The daemon SHALL expose a `GET /playlists/sync-events` endpoint that returns a Server-Sent Events stream. Each event SHALL be a JSON object with fields `event` (`"sync_started"` or `"sync_done"`) and `playlist_id`. The stream SHALL remain open until the client disconnects.

#### Scenario: Client subscribes
- **WHEN** a client connects to `GET /playlists/sync-events`
- **THEN** the connection SHALL be held open and the client SHALL receive events as playlists begin and complete syncing

#### Scenario: sync_started event emitted
- **WHEN** `POST /playlists/{id}/sync` is called
- **THEN** before the background sync thread starts, the daemon SHALL broadcast `{"event": "sync_started", "playlist_id": <id>}` to all connected sync-events SSE subscribers

#### Scenario: sync_done event emitted
- **WHEN** the background sync thread for a playlist completes (success or failure)
- **THEN** the daemon SHALL broadcast `{"event": "sync_done", "playlist_id": <id>}` to all connected sync-events SSE subscribers

#### Scenario: Client disconnects
- **WHEN** a client disconnects from `GET /playlists/sync-events`
- **THEN** the daemon SHALL remove that client's queue from the subscriber list

---

### Requirement: In-memory syncing state
The daemon SHALL maintain a `_syncing_playlists` set in memory containing the `playlist_id` values of all playlists currently being synced. This set SHALL be updated atomically relative to the SSE broadcast: the playlist_id SHALL be added to the set before the `sync_started` broadcast, and removed after the `sync_done` broadcast. The set SHALL reset to empty on daemon restart.

#### Scenario: Playlist added to syncing set
- **WHEN** `POST /playlists/{id}/sync` is called
- **THEN** `playlist_id` SHALL be added to `_syncing_playlists` before any SSE event is broadcast

#### Scenario: Playlist removed from syncing set
- **WHEN** the sync thread for a playlist finishes
- **THEN** `playlist_id` SHALL be removed from `_syncing_playlists` and the `sync_done` event SHALL be broadcast

---

### Requirement: is_syncing field in playlist responses
`GET /playlists` and `GET /playlists/{id}` SHALL include an `is_syncing` boolean field in each playlist object. This field SHALL be `true` if the `playlist_id` is present in `_syncing_playlists`, and `false` otherwise.

#### Scenario: Playlist actively syncing
- **WHEN** `GET /playlists` is called while a playlist is being synced
- **THEN** the response entry for that playlist SHALL include `"is_syncing": true`

#### Scenario: Playlist not syncing
- **WHEN** `GET /playlists` is called and no sync is in progress for a playlist
- **THEN** the response entry for that playlist SHALL include `"is_syncing": false`
