# Future UI

## Intent

A web UI is planned as a separate feature after the daemon/API layer is built.
The UI will manage playlists, view sync status, and configure schedules.

## Architecture contract

The daemon exposes a REST API (FastAPI). The UI is just another client of that API —
same endpoints used by the CLI. No special UI-specific paths needed.

FastAPI auto-generates an OpenAPI spec at `/docs`. Use this as the contract when
building the UI — no manual API documentation needed.

## Key decisions already made

- CLI commands become thin HTTP clients (wrappers around API calls)
- UI will talk to the same endpoints
- Daemon is the single writer to the DB — UI never touches the DB directly
- Daemon API runs on a configurable port (see deployment notes below)

## Deployment

Siphon is intended to run as an Unraid community app. Unraid users configure
ports at install time via the container template, not inside the app config.
The port must therefore be configurable via an environment variable (e.g.
`SIPHON_PORT=8000`) so Unraid's port mapping UI works naturally.

The UI, when built, should be served from the same daemon process (static files
via FastAPI) to keep the deployment a single container with a single port.

## Security

No built-in authentication planned. Siphon is designed for a home server LAN
environment, not public internet exposure. Users who expose the port externally
should place it behind a reverse proxy (Nginx, Caddy) with their own auth layer.
This should be documented clearly in the README.
