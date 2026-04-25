## ADDED Requirements

### Requirement: Viewport does not overflow horizontally on mobile
The UI SHALL fit within a 375px viewport width without any horizontal scrollbar or off-canvas elements.

#### Scenario: Dashboard fits 375px screen
- **WHEN** the user opens the Dashboard on a 375px-wide screen
- **THEN** all form inputs, buttons, and controls are fully visible and reachable within the viewport

#### Scenario: Library fits 375px screen
- **WHEN** the user opens the Library on a 375px-wide screen
- **THEN** all playlist rows, toggles, meta text, and action buttons are fully visible and tappable

#### Scenario: Settings fits 375px screen
- **WHEN** the user opens Settings on a 375px-wide screen
- **THEN** all setting rows, the About section values, and version numbers are fully visible without horizontal clipping

### Requirement: NavBar hamburger sidebar on mobile
On viewports ≤640px wide, the NavBar SHALL replace inline navigation buttons with a hamburger menu that opens a right-side overlay sidebar.

#### Scenario: Hamburger button appears on mobile
- **WHEN** the viewport is ≤640px wide
- **THEN** the hamburger icon is visible in the NavBar and the inline Dashboard/Library buttons are hidden

#### Scenario: Sidebar opens on hamburger tap
- **WHEN** the user taps the hamburger button
- **THEN** a sidebar slides in from the right containing Dashboard, Library, and Settings navigation buttons

#### Scenario: Hamburger transforms to close button
- **WHEN** the sidebar is open
- **THEN** the hamburger icon changes to a ✕ close icon

#### Scenario: Sidebar closes on nav item tap
- **WHEN** the user taps a navigation item in the sidebar
- **THEN** the sidebar closes and the corresponding page is shown

#### Scenario: Sidebar closes on backdrop tap
- **WHEN** the sidebar is open and the user taps outside the sidebar
- **THEN** the sidebar closes

#### Scenario: Sidebar closes on close button tap
- **WHEN** the sidebar is open and the user taps the ✕ button
- **THEN** the sidebar closes

### Requirement: DownloadForm toggles stack vertically on mobile
On viewports ≤640px, auto-rename and auto-sync toggles SHALL be stacked one below the other, each occupying a full row.

#### Scenario: Toggles stacked on mobile
- **WHEN** the viewport is ≤640px wide and both auto-rename and auto-sync toggles are visible
- **THEN** auto-rename and auto-sync appear on separate rows

### Requirement: PlaylistRow stacked mobile layout
On viewports ≤640px, the playlist row SHALL display as a stacked card: title + icons in the header, meta text below, toggles stacked vertically, full-width expand button at the bottom.

#### Scenario: All playlist row controls are accessible on mobile
- **WHEN** the viewport is ≤640px wide and a playlist row is rendered
- **THEN** the playlist title, sync icon, delete button, meta text, auto-rename toggle, auto-sync toggle with interval, and expand button are all visible and tappable

#### Scenario: Expand strip is full-width at the bottom on mobile
- **WHEN** the viewport is ≤640px wide
- **THEN** the expand/collapse strip spans the full card width at the bottom of the row

### Requirement: Sync indicator does not cause layout jump on mobile
On viewports ≤640px, the playlist row meta area (item count, added date, last synced date) and the sync-in-progress indicator SHALL occupy the same reserved space so that triggering a sync does not shift surrounding elements.

#### Scenario: Sync indicator replaces meta text without height jump
- **WHEN** the user taps the sync button on a mobile playlist row
- **THEN** the "Syncing…" indicator appears in place of the meta text and the row height does not change

### Requirement: Interval Save replaced with checkmark button
All interval "Save" text buttons and per-item rename "Save" text buttons across all components (`DownloadForm`, `PlaylistRow`, `Settings`, `QueueItem`, `PlaylistItemsPanel`) SHALL be replaced with a compact checkmark icon button. All "Cancel" text buttons adjacent to a save action SHALL be replaced with a compact ✕ icon button. The item title row in `QueueItem` and `PlaylistItemsPanel` SHALL reserve a stable minimum height so layout does not shift when the rename input appears or disappears.

#### Scenario: Checkmark saves interval on click
- **WHEN** the user edits an interval and clicks the checkmark button
- **THEN** the interval is saved (same behaviour as the previous "Save" text button)

#### Scenario: Cancel closes interval edit
- **WHEN** the user clicks the ✕ button while editing an interval
- **THEN** the edit is cancelled (same behaviour as Escape key / clicking outside)

### Requirement: MusicBrainz user-agent email-only input
The MusicBrainz user-agent setting SHALL accept only an email address from the user. The UI constructs the full user-agent string (`Siphon/<version> (<email>)`) automatically using the version fetched from `/version`. Saving an empty email SHALL store an empty string (equivalent to unsetting the config). The description SHALL read "Email ID required for auto renames based on MusicBrainz metadata lookup".

#### Scenario: Full user-agent string built from email
- **WHEN** the user enters an email address and saves
- **THEN** the stored value is `Siphon/<version> (<email>)` with the version from the backend

#### Scenario: Empty email unsets the setting
- **WHEN** the user clears the email field and saves
- **THEN** an empty string is stored and the MusicBrainz rename tier is not used

### Requirement: About section values do not overflow on mobile
On viewports ≤640px, version numbers and the GitHub source URL in the About section SHALL wrap within the card instead of overflowing or being clipped.

#### Scenario: GitHub URL wraps on mobile
- **WHEN** the viewport is ≤640px wide and the Settings About section is visible
- **THEN** the GitHub source URL wraps to a new line rather than overflowing the card boundary
