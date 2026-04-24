## ADDED Requirements

### Requirement: E2E tests run automatically on every PR targeting develop or main
The project SHALL have a GitHub Actions workflow (`e2e-tests.yml`) that runs the full e2e suite on every pull request targeting `develop` or `main`.

#### Scenario: Workflow triggers on pull request
- **WHEN** a pull request targeting `develop` or `main` is opened or updated
- **THEN** the `e2e-tests` CI job runs automatically

#### Scenario: Workflow triggers on manual dispatch
- **WHEN** `workflow_dispatch` is triggered manually from the Actions tab
- **THEN** the `e2e-tests` CI job runs

#### Scenario: Workflow installs ffmpeg before running tests
- **WHEN** the CI job executes
- **THEN** ffmpeg is installed via `apt-get` before `siphon start` or any pytest invocation

#### Scenario: Workflow runs the full suite with one retry
- **WHEN** the CI job executes
- **THEN** it runs `pytest tests/e2e/ --reruns 1 --reruns-delay 5`

#### Scenario: Secrets are injected as environment variables
- **WHEN** the workflow runs
- **THEN** `E2E_PLAYLIST_URL`, `E2E_SINGLE_VIDEO_URL`, and `E2E_MB_USER_AGENT` are available as environment variables from GitHub secrets

### Requirement: yt-dlp bump workflow triggers e2e on the bump branch
The `ytdlp-bump.yml` workflow SHALL trigger the e2e suite on the bump branch after creating the bump PR.

#### Scenario: e2e workflow is triggered after bump PR creation
- **WHEN** `ytdlp-bump.yml` creates a new `chore/bump-ytdlp` PR
- **THEN** it calls `gh workflow run e2e-tests.yml --ref chore/bump-ytdlp` to run e2e on that branch
