## ADDED Requirements

### Requirement: Manual trigger only
The workflow SHALL be triggered only via `workflow_dispatch` (manual). No scheduled triggers.

#### Scenario: Manual dispatch
- **WHEN** the maintainer triggers the workflow manually from GitHub Actions
- **THEN** the workflow runs and checks for a newer yt-dlp version

### Requirement: Check latest yt-dlp version from PyPI
The workflow SHALL query the PyPI JSON API for the latest yt-dlp release version and compare it with the version pinned in `requirements.txt`.

#### Scenario: Newer version available
- **WHEN** PyPI has a newer yt-dlp version than the one in `requirements.txt`
- **THEN** the workflow proceeds to create a bump PR

#### Scenario: Already up to date
- **WHEN** the pinned version matches the latest on PyPI
- **THEN** the workflow exits successfully without creating a PR

### Requirement: Open PR with version bump
The workflow SHALL update the yt-dlp version in `requirements.txt` and open a pull request titled `chore: bump yt-dlp to <version>`.

#### Scenario: PR created
- **WHEN** a newer version is detected
- **THEN** a PR is opened against `main` with the updated `requirements.txt` and a descriptive title
