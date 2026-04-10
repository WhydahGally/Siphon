## ADDED Requirements

### Requirement: Dashboard download section is always positioned at the top
The Dashboard SHALL render the `DownloadForm` at the top of the page at all times, regardless of whether any download jobs exist. No centering, animation, or conditional layout class SHALL be applied based on job state.

#### Scenario: Dashboard loaded with no jobs
- **WHEN** the user navigates to the Dashboard and no download jobs are present
- **THEN** the `DownloadForm` is rendered at the top of the viewport with standard padding, not vertically centered

#### Scenario: Dashboard loaded with existing jobs
- **WHEN** the user navigates to the Dashboard and download jobs are already present
- **THEN** the `DownloadForm` remains at the top with the same layout as when no jobs are present

#### Scenario: First job created in a session
- **WHEN** the user submits the download form for the first time in a session
- **THEN** the layout does not shift or animate — the `DownloadForm` stays at the top and the queue appears below it
