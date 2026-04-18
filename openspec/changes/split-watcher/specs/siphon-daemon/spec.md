## MODIFIED Requirements

### Requirement: FastAPI daemon startup
`siphon start` SHALL start a FastAPI application served by uvicorn, bound to
`0.0.0.0:8000`. The daemon SHALL initialise the DB, instantiate the
`PlaylistScheduler`, start the scheduler, then hand control to uvicorn. The
daemon SHALL be the sole long-running process in the container and the
prerequisite for all other `siphon` subcommands.

The entry point SHALL be `siphon.app:main`. Running `python -m siphon` SHALL
invoke the same entry point.

#### Scenario: Daemon starts successfully
- **WHEN** `siphon start` is run and port 8000 is available
- **THEN** the daemon SHALL bind to `0.0.0.0:8000`, log a startup message
  including the bound address, start the `PlaylistScheduler`, and begin serving
  requests

#### Scenario: Port already in use
- **WHEN** `siphon start` is run and port 8000 is already bound
- **THEN** uvicorn SHALL raise an error and the process SHALL exit non-zero with a
  message indicating the port conflict

## RENAMED Requirements

### Requirement: FastAPI daemon startup
- **FROM:** `siphon watch`
- **TO:** `siphon start`
