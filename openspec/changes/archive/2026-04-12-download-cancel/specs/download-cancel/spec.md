## ADDED Requirements

### Requirement: Cancel all active download jobs
The daemon SHALL expose `POST /jobs/cancel-all` which immediately marks all `pending` items across every non-terminal playlist job as `cancelled` and broadcasts the state change to SSE subscribers. Items whose state is already `downloading` SHALL NOT be interrupted; they SHALL continue to completion. Single-video jobs (`playlist_id` is None) SHALL NOT be affected by this endpoint. The endpoint SHALL return 200 with `{ "cancelled": <count of items transitioned to cancelled> }`.

#### Scenario: Pending items cancelled
- **WHEN** `POST /jobs/cancel-all` is called while one or more playlist jobs have items in `pending` state
- **THEN** all `pending` items in non-terminal playlist jobs SHALL transition to `cancelled` state
- **AND** SSE events SHALL be emitted for each transitioned item with `state: "cancelled"`

#### Scenario: In-flight items not interrupted
- **WHEN** `POST /jobs/cancel-all` is called while items are in `downloading` state
- **THEN** those items SHALL continue downloading to completion uninterrupted
- **AND** they SHALL resolve to `done` or `failed` as normal

#### Scenario: No active jobs
- **WHEN** `POST /jobs/cancel-all` is called and there are no non-terminal playlist jobs
- **THEN** the endpoint SHALL return 200 with `{ "cancelled": 0 }`

#### Scenario: Single-video jobs unaffected
- **WHEN** `POST /jobs/cancel-all` is called while a single-video job is active
- **THEN** the single-video job items SHALL NOT be transitioned to `cancelled`

#### Scenario: Job reaches terminal state after cancel
- **WHEN** all items in a job are in `done | failed | cancelled` state
- **THEN** the job SHALL be considered terminal and the SSE `done` event SHALL fire

### Requirement: CLI cancel command
The CLI SHALL expose a `siphon cancel` subcommand that posts to `POST /jobs/cancel-all` on the running daemon and prints a summary of how many items were cancelled. If no daemon is running, it SHALL print an error and exit with code 1. If no active downloads are running, it SHALL print "No active downloads to cancel." and exit with code 0.

#### Scenario: Cancel with active jobs
- **WHEN** `siphon cancel` is run and the daemon has active playlist download jobs
- **THEN** the daemon cancels all pending items and the CLI prints the count of cancelled items

#### Scenario: Cancel with no active jobs
- **WHEN** `siphon cancel` is run and no active jobs exist
- **THEN** the CLI SHALL print "No active downloads to cancel." and exit 0

#### Scenario: Daemon not running
- **WHEN** `siphon cancel` is run and the daemon is not reachable
- **THEN** the CLI SHALL print an error message and exit 1
