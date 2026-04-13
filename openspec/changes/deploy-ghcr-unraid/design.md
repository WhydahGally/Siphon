## Context

Siphon is a container-first YouTube playlist watcher running as a daemon (`siphon watch`) behind a FastAPI server on port 8000. The existing Dockerfile is a multi-stage build (Node UI build → Python runtime) that works locally. There is no CI/CD, no image registry, and no Unraid integration. The GitHub repo is public under `WhydahGally/Siphon`.

## Goals / Non-Goals

**Goals:**
- One-click Unraid installation via Community Apps with proper PUID/PGID file ownership.
- Automated image builds on GHCR triggered by branch pushes and version tags.
- A manual workflow to keep yt-dlp up to date via PR.

**Non-Goals:**
- Docker Hub publishing (future consideration).
- Multi-arch builds (x86_64 only; users can build ARM themselves).
- Auto-merging yt-dlp bumps (manual merge via PR).
- Exposing application config as Docker env vars (config is managed through the UI).

## Decisions

### 1. GHCR over Docker Hub
GHCR is free for public repos, has no pull rate limits, and integrates natively with GitHub Actions (no extra credentials to manage). Unraid CA bypasses registry search — the template points directly to the image URL — so Docker Hub discoverability doesn't matter.

### 2. PUID/PGID via gosu
Standard Unraid convention. The entrypoint script creates a `siphon` user with the supplied UID/GID, chowns the data and download directories, then uses `gosu` to drop privileges. `gosu` is preferred over `su-exec` in Debian-based images and is the same tool used by LinuxServer.io containers.

Default PUID/PGID: `99`/`100` (Unraid's `nobody`/`users`).

### 3. Tagging strategy
| Trigger | Tags |
|---|---|
| Push to `main` | `:latest` |
| Push to `develop` | `:develop` |
| Git tag `v*` | `:x.y.z` + `:latest` |

The `:develop` tag is not exposed in the Unraid template — it's for the maintainer's testing only. The template shows only `:latest`.

### 4. yt-dlp bump workflow
A manually-dispatched workflow that:
1. Queries PyPI for the latest yt-dlp version.
2. Compares with the pinned version in `requirements.txt`.
3. If newer, updates `requirements.txt` and opens a PR.

Uses `peter-evans/create-pull-request` for PR creation. No auto-merge — the maintainer reviews and merges, which triggers the build workflow.

### 5. Unraid template in same repo
The template lives at `dist/unraid/siphon.xml` in the main repo. No separate template repository needed. The Community Apps submission points to this path.

### 6. PNG icon
Generate a PNG from `src/ui/public/favicon.svg` and place it alongside as `favicon.png`. The Unraid template references the raw GitHub URL for the PNG. Older Unraid versions handle PNG more reliably than SVG.

## Risks / Trade-offs

- **gosu adds ~1MB to image** → Negligible. Standard practice for container privilege management.
- **GHCR token scope** → GitHub Actions get automatic `GITHUB_TOKEN` with write access to packages for public repos. No extra secrets needed.
- **yt-dlp bump PR may conflict** → Unlikely since it only touches one line in `requirements.txt`. If it conflicts, regenerate manually.
- **No multi-arch** → Unraid is x86_64, so this covers the target platform. ARM users can fork and build.
