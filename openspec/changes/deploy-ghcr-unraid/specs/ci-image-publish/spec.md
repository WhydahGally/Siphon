## ADDED Requirements

### Requirement: Build and push on main branch
The workflow SHALL build the Docker image and push it to `ghcr.io/whydahgally/siphon:latest` when commits are pushed to the `main` branch.

#### Scenario: Push to main
- **WHEN** a commit is pushed to the `main` branch
- **THEN** the workflow builds the image and pushes it with the `:latest` tag to GHCR

### Requirement: Build and push on develop branch
The workflow SHALL build and push the image with the `:develop` tag when commits are pushed to the `develop` branch.

#### Scenario: Push to develop
- **WHEN** a commit is pushed to the `develop` branch
- **THEN** the workflow builds the image and pushes it with the `:develop` tag to GHCR

### Requirement: Build and push on version tag
The workflow SHALL build and push the image with both the semver tag and `:latest` when a version tag matching `v*` is pushed.

#### Scenario: Version tag pushed
- **WHEN** a tag matching `v*` (e.g. `v0.1.0`) is pushed
- **THEN** the workflow builds the image and pushes it with both `:0.1.0` and `:latest` tags to GHCR

### Requirement: Authenticate with GHCR using GITHUB_TOKEN
The workflow SHALL authenticate with GHCR using the built-in `GITHUB_TOKEN` secret. No additional secrets SHALL be required.

#### Scenario: Authentication
- **WHEN** the workflow runs
- **THEN** it logs into GHCR using `GITHUB_TOKEN` with `packages: write` permission
