## Why

Siphon is feature-ready for a first public release. The project is container-first and targets Unraid as the primary deployment platform, but currently has no automated image publishing or Unraid integration. Users must build the image themselves. Publishing to GHCR and creating an Unraid Community Apps template makes Siphon installable in a few clicks.

## What Changes

- Add PUID/PGID support via an entrypoint script so downloaded files have correct ownership on the host (standard Unraid convention).
- Update the Dockerfile to include `gosu` and the entrypoint script.
- Generate a PNG icon from the existing SVG favicon for Unraid template compatibility.
- Add a GitHub Actions workflow that builds and pushes the Docker image to GHCR (`ghcr.io/whydahgally/siphon`) on pushes to `main` (`:latest`), `develop` (`:develop`), and version tags (`:x.y.z`).
- Add a manually-triggered GitHub Actions workflow that checks for newer yt-dlp versions and opens a PR to bump it.
- Create an Unraid XML template at `/dist/unraid/siphon.xml` exposing port 8000, download/data volume mappings, and PUID/PGID variables.

## Capabilities

### New Capabilities
- `container-entrypoint`: PUID/PGID entrypoint script and Dockerfile changes for proper file ownership in container deployments.
- `ci-image-publish`: GitHub Actions workflow to build and push Docker images to GHCR on main/develop/tag events.
- `ci-ytdlp-bump`: Manually-triggered GitHub Actions workflow that checks PyPI for newer yt-dlp and opens a PR to bump the pinned version.
- `unraid-template`: Unraid Community Apps XML template with port, volume, and env var configuration.

### Modified Capabilities

None.

## Impact

- **New files**: `entrypoint.sh`, `.github/workflows/docker-publish.yml`, `.github/workflows/ytdlp-bump.yml`, `dist/unraid/siphon.xml`, PNG icon.
- **Modified files**: `Dockerfile` (add gosu, entrypoint, copy icon).
- **Dependencies**: Adds `gosu` to the Docker image. GitHub Actions workflows use standard actions (`docker/build-push-action`, `peter-evans/create-pull-request`).
- **No application code changes**.
