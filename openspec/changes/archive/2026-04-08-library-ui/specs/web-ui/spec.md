## ADDED Requirements

### Requirement: Library page — fully implemented
The Library page SHALL display all registered playlists fetched from `GET /playlists`. It SHALL not be a stub. It SHALL be rendered when the user navigates to the Library tab.

#### Scenario: Library tab selected
- **WHEN** the user clicks the Library nav button
- **THEN** the Library page content SHALL be shown and the nav button SHALL be in its active state

---

### Requirement: Download queue excludes sync jobs
The Dashboard download queue (`GET /jobs` and the queue display) SHALL NOT include sync operations triggered via `POST /playlists/{id}/sync`. Sync operations SHALL only be visible in the Library tab via the `is_syncing` flag and sync-events SSE channel.

#### Scenario: Library sync does not appear in Dashboard queue
- **WHEN** the user triggers a sync from the Library tab
- **THEN** no new item SHALL appear in the Dashboard's download queue
