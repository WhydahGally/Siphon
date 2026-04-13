## 1. Container Entrypoint

- [ ] 1.1 Create `entrypoint.sh` with PUID/PGID user creation, directory chown, and gosu exec
- [ ] 1.2 Update `Dockerfile` to install gosu, copy entrypoint, set ENTRYPOINT

## 2. Icon

- [ ] 2.1 Generate PNG icon from `src/ui/public/favicon.svg` and save as `src/ui/public/favicon.png`

## 3. CI — Image Publish

- [ ] 3.1 Create `.github/workflows/docker-publish.yml` with build+push on main (latest), develop (develop), and version tags (semver + latest)

## 4. CI — yt-dlp Bump

- [ ] 4.1 Create `.github/workflows/ytdlp-bump.yml` with manual dispatch, PyPI version check, and PR creation

## 5. Unraid Template

- [ ] 5.1 Create `dist/unraid/siphon.xml` with port 8000, volume mappings, PUID/PGID, icon URL, and Downloaders category

## 6. Verify

- [ ] 6.1 Build Docker image locally and verify entrypoint works with custom PUID/PGID
- [ ] 6.2 Validate Unraid template XML structure
