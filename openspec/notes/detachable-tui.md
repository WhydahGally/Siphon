# Detachable TUI

## Context

Explored during the scheduler-daemon change. The question was whether Siphon
could avoid requiring two terminals (one for `siphon watch`, one for management
commands).

## Options considered

### 1. --daemon flag (background fork)
`siphon start` forks to background, returns the shell. `siphon stop` sends a
stop signal. Used by nginx, redis-server, etc.

**Why rejected**: Requires a PID file to communicate between processes — exactly
the stale-file / crash risk we designed around in the scheduler-daemon change.
Also contradicts Docker's expected model: the container CMD must stay in the
foreground.

### 2. Integrated TUI (takes over the terminal)
`siphon watch` launches a full-screen terminal UI (using `curses` or `rich`/
`textual`) showing live playlist status, download progress, and management
controls. One terminal, everything in one place.

**Why rejected**: No terminal in a running container. Would build a parallel UI
path alongside the planned web UI, duplicating effort. Good local dev UX but
wrong fit for the container deployment target.

### 3. Detachable TUI — the preferred future approach
The daemon runs headless (as it does now). A separate `siphon tui` command
starts a terminal UI that connects to the running daemon via its HTTP API.

```
siphon watch       ← daemon, runs headless in container or background
siphon tui         ← optional, connects to API, can be launched any time
                      and exited without affecting the daemon
```

Analogous to how `lazydocker` works with Docker: Docker is always running
headlessly, the TUI just connects to the Docker socket and displays state.

**Why deferred**: The daemon API already provides the contract the TUI needs.
The web UI (planned separately) is higher priority and covers the remote
management use case better. A TUI is best suited for local development ergonomics.

## Implementation notes (for future reference)

- **Library options**: `textual` (modern, async-native, rich widgets) is the
  best fit. `rich` alone for a simpler read-only status display. `urwid` or
  `curses` are lower-level alternatives.
- **Transport**: The TUI calls the same REST endpoints as the CLI (`GET
  /playlists`, `GET /health`, etc.). No daemon changes needed — the API
  contract is already the right interface.
- **`siphon tui` exits cleanly**: `q` or `Ctrl-C` exits the TUI without
  stopping the daemon. The daemon lifecycle is fully independent.
- **Does not affect containerization**: The TUI is a local developer tool.
  In production (Docker/Unraid), users interact via the web UI or `docker exec`.
- **Does not conflict with web UI**: Both the TUI and web UI are separate
  clients of the same API. They can coexist.

## Priority

Low — implement after the web UI feature. Revisit if local dev ergonomics
become a pain point or if there is community interest post-GitHub release.
