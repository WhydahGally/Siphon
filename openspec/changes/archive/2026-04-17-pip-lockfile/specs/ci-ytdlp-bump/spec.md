## MODIFIED Requirements

### Requirement: Check latest yt-dlp version from PyPI
The workflow SHALL query the PyPI JSON API for the latest yt-dlp release version and compare it with the version pinned in `requirements.in`.

#### Scenario: Newer version available
- **WHEN** PyPI has a newer yt-dlp version than the one in `requirements.in`
- **THEN** the workflow proceeds to create a bump PR

#### Scenario: Already up to date
- **WHEN** the pinned version matches the latest on PyPI
- **THEN** the workflow exits successfully without creating a PR

### Requirement: Open PR with version bump
The workflow SHALL update the yt-dlp version in `requirements.in`, regenerate `requirements.txt` using `pip-compile --generate-hashes`, and open a pull request titled `chore: bump yt-dlp to <version>`.

#### Scenario: PR created
- **WHEN** a newer version is detected
- **THEN** the workflow installs pip-tools, updates the version in `requirements.in`, runs `pip-compile --generate-hashes requirements.in -o requirements.txt`, and opens a PR against `main` with both `requirements.in` and `requirements.txt` updated
