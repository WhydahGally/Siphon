## ADDED Requirements

### Requirement: FastAPI daemon startup
`siphon watch` SHALL start a FastAPI application served by uvicorn, bound to
`0.0.0.0:8000`. The daemon SHALL initialise the DB, instantiate the
`PlaylistScheduler`, start the scheduler, then hand control to uvicorn. The
daemon SHALL be the sole long-running process in the container and the
prerequisite for all other `siphon` subcommands.

#### Scenario: Daemon starts successfully
- **WHEN** `siphon watch` is run and port 8000 is available
- **THEN** the daemon SHALL bind to `0.0.0.0:8000`, log a startup message
  including the bound address, start the `PlaylistScheduler`, and begin serving
  requests

#### Scenario: Port already in use
- **WHEN** `siphon watch` is run and port 8000 is already bound
- **THEN** uvicorn SHALL raise an error and the process SHALL exit non-zero with a
  message indicating the port conflict

---

### Requirement: Graceful shutdown on SIGTERM
On receipt of SIGTERM (e.g. `docker stop`), the daemon SHALL stop accepting new
requests, call `PlaylistScheduler.stop()` (which waits for any in-progress sync
to complete), then exit cleanly.

#### Scenario: SIGTERM during idle
- **WHEN** SIGTERM is received and no sync is in progress
- **THEN** the daemon SHALL shut down within 5 seconds

#### Scenario: SIGTERM during active sync
- **WHEN** SIGTERM is received while a playlist sync is running
- **THEN** the daemon SHALL wait for the sync to finish before exiting; the sync
  SHALL complete and its results SHALL be persisted to the DB

---

### Requirement: REST API — playlist endpoints
The daemon SHALL expose the following REST endpoints for playlist management:

- `POST /playlists` — register a new playlist (equivalent to `siphon add`)
- `GET /playlists` — list all registered playlists
- `GET /playlists/{playlist_id}` — get a single playlist record
- `DELETE /playlists/{playlist_id}` — delete a playlist (equivalent to `siphon delete`)
- `PATCH /playlists/{playlist_id}` — update playlist properties (interval, watched flag)
- `POST /playlists/{playlist_id}/sync` — trigger an immediate sync for one playlist
- `POST /playlists/{playlist_id}/sync-failed` — retry failed downloads for one playlist

#### Scenario: POST /playlists — new playlist
- **WHEN** a valid `POST /playlists` request is received with a YouTube playlist URL
- **THEN** the daemon SHALL register the playlist in the DB, add it to the
  scheduler if `watched=true`, and return HTTP 201 with the created playlist record

#### Scenario: POST /playlists — duplicate
- **WHEN** a `POST /playlists` request is received for a playlist already in the DB
- **THEN** the daemon SHALL return HTTP 409 Conflict

#### Scenario: GET /playlists
- **WHEN** `GET /playlists` is called
- **THEN** the daemon SHALL return HTTP 200 with a JSON array of all playlist records

#### Scenario: DELETE /playlists/{playlist_id}
- **WHEN** `DELETE /playlists/{playlist_id}` is called for an existing playlist
- **THEN** the daemon SHALL remove the playlist and its items/failures from the DB,
  cancel its scheduler timer if active, and return HTTP 204

#### Scenario: DELETE /playlists/{playlist_id} — not found
- **WHEN** `DELETE /playlists/{playlist_id}` is called for an unknown ID
- **THEN** the daemon SHALL return HTTP 404

#### Scenario: PATCH /playlists/{playlist_id} — update interval
- **WHEN** `PATCH /playlists/{playlist_id}` is called with a new `check_interval_secs`
- **THEN** the daemon SHALL update the DB record and reschedule the playlist's timer
  in the `PlaylistScheduler` with the new interval, returning HTTP 200

#### Scenario: POST /playlists/{playlist_id}/sync — triggers sync
- **WHEN** `POST /playlists/{playlist_id}/sync` is called
- **THEN** the daemon SHALL trigger `_sync_parallel` for that playlist in a
  background thread and return HTTP 202 Accepted immediately

---

### Requirement: REST API — settings endpoints
The daemon SHALL expose endpoints for reading and writing global settings:

- `GET /settings` — list all stored settings key-value pairs
- `GET /settings/{key}` — read a single setting
- `PUT /settings/{key}` — write a setting value

#### Scenario: PUT /settings/{key} — known key
- **WHEN** `PUT /settings/check-interval` is called with a valid integer value
- **THEN** the daemon SHALL persist the value in the DB settings table and return
  HTTP 200

#### Scenario: PUT /settings/{key} — unknown key
- **WHEN** `PUT /settings/unknown-key` is called
- **THEN** the daemon SHALL return HTTP 400 with a message listing valid keys

#### Scenario: GET /settings/{key} — not set
- **WHEN** `GET /settings/check-interval` is called and no value is stored
- **THEN** the daemon SHALL return HTTP 200 with `{"key": "check-interval", "value": null}`

---

### Requirement: Health endpoint
The daemon SHALL expose `GET /health` that returns daemon status and scheduler
state. This endpoint SHALL be usable as a Docker/Unraid container health check.

#### Scenario: Daemon is healthy
- **WHEN** `GET /health` is called and the daemon is running normally
- **THEN** the endpoint SHALL return HTTP 200 with a JSON body containing at
  minimum: `{"status": "ok", "watched_playlists": <count>}`

---

### Requirement: OpenAPI documentation
The daemon SHALL serve auto-generated OpenAPI documentation at `/docs` (Swagger UI)
and `/openapi.json`. This serves as the machine-readable API contract for future
UI development.

#### Scenario: Docs accessible
- **WHEN** a browser navigates to `http://localhost:8000/docs`
- **THEN** the Swagger UI SHALL render with all endpoints listed and their request/
  response schemas visible
