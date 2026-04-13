## ADDED Requirements

### Requirement: Entrypoint creates user with supplied UID/GID
The entrypoint script SHALL create a `siphon` user and group with the UID and GID specified by the `PUID` and `PGID` environment variables respectively.

#### Scenario: Custom PUID/PGID provided
- **WHEN** the container starts with `PUID=1001` and `PGID=1001`
- **THEN** the entrypoint creates a `siphon` group with GID 1001 and a `siphon` user with UID 1001

#### Scenario: Default PUID/PGID
- **WHEN** the container starts without `PUID` or `PGID` set
- **THEN** the entrypoint defaults to UID 99 and GID 100 (Unraid nobody/users)

### Requirement: Entrypoint sets ownership on data directories
The entrypoint SHALL chown `/app/.data` and `/app/downloads` to the `siphon` user before starting the application.

#### Scenario: Directories owned by siphon user
- **WHEN** the entrypoint runs
- **THEN** `/app/.data` and `/app/downloads` are owned by the `siphon` user and group

### Requirement: Application runs as unprivileged user
The entrypoint SHALL use `gosu` to execute the application command as the `siphon` user instead of root.

#### Scenario: Process runs as siphon user
- **WHEN** the container is running
- **THEN** the `siphon watch` process runs as the `siphon` user, not root

### Requirement: Dockerfile includes gosu
The Dockerfile SHALL install `gosu` and copy `entrypoint.sh` into the image.

#### Scenario: Image contains gosu and entrypoint
- **WHEN** the Docker image is built
- **THEN** `gosu` is available at `/usr/local/bin/gosu` and `entrypoint.sh` is the image's `ENTRYPOINT`
