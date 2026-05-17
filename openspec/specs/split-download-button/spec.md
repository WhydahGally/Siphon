## ADDED Requirements

### Requirement: Split download button with dropdown
The DownloadForm SHALL display a split button consisting of a primary "Download" action and a `▾` dropdown trigger. Clicking the dropdown trigger SHALL reveal a menu with a "Register" option.

#### Scenario: Primary button triggers download
- **WHEN** user clicks the primary "Download" area of the split button
- **THEN** the normal download flow SHALL be initiated (including SB health check if applicable)

#### Scenario: Dropdown reveals Register option
- **WHEN** user clicks the `▾` dropdown trigger
- **THEN** a dropdown menu SHALL appear with a "Register" option

#### Scenario: Register option adds to library without download
- **WHEN** user selects "Register" from the dropdown menu
- **THEN** the playlist/video SHALL be registered in the library without initiating a download
- **THEN** the dropdown menu SHALL close

#### Scenario: Dropdown closes on outside click
- **WHEN** the dropdown is open AND user clicks outside the dropdown
- **THEN** the dropdown SHALL close

### Requirement: Register option has info tooltip
The "Register" option in the dropdown SHALL display an ⓘ icon with a tooltip on hover reading "Add to library without downloading".

#### Scenario: Tooltip shown on hover
- **WHEN** user hovers over the ⓘ icon next to "Register"
- **THEN** a tooltip with text "Add to library without downloading" SHALL appear

### Requirement: Split button is usable on mobile
On viewports below 600px, the split button SHALL remain functional with adequate touch targets (minimum 44px height for both primary action and dropdown trigger).

#### Scenario: Mobile touch targets
- **WHEN** viewport width is < 600px
- **THEN** both the primary button and dropdown trigger SHALL have a minimum touch target height of 44px

#### Scenario: Dropdown accessible on mobile
- **WHEN** user taps the `▾` trigger on a mobile viewport
- **THEN** the dropdown menu SHALL appear and be fully visible without scrolling
