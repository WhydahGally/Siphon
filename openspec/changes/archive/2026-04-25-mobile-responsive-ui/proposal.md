## Why

The Siphon web UI was built desktop-first and is unusable on mobile: key UI elements overflow the viewport, buttons are unreachable, and the navigation is awkward on touchscreens. This change makes the UI functional and comfortable on narrow screens without altering the existing desktop experience.

## What Changes

- **`DownloadForm`**: reduce card padding on mobile; spread format/quality selectors to fill width; stack auto-rename and auto-sync toggles vertically; keep interval editor inline with its toggle; replace "Save" with a checkmark button (applied on all screen sizes)
- **`PlaylistRow`**: redesign mobile layout — stacked card with title + sync icon + delete in header row, meta text below, toggles stacked, full-width expand strip at the bottom; desktop 4-column grid unchanged
- **`NavBar`**: on mobile, hide inline nav buttons and show a hamburger icon that slides out a right-side overlay sidebar; hamburger transforms to ✕ when open; tapping a nav item, the backdrop, or ✕ closes the sidebar
- **`Settings` (About section)**: fix value column overflow/clipping by adding `overflow-wrap: anywhere; min-width: 0` and removing over-generous key column width on mobile; also replace all "Save"/"Cancel" text buttons in Settings with checkmark/✕ icon buttons for consistency
- **`App.vue`**: reduce `main-content` horizontal padding from `24px` to `16px` on mobile

## Capabilities

### New Capabilities

- `mobile-responsive-ui`: Responsive layout adapting all major UI surfaces (DownloadForm, PlaylistRow, NavBar, Settings) for narrow viewports (≤640px); includes hamburger sidebar navigation and inline interval editor improvements applied globally

### Modified Capabilities

<!-- None — all changes are additive CSS media queries or cosmetic button replacements; no existing API or spec-level behavior changes -->

## Impact

- `src/ui/src/components/DownloadForm.vue` — CSS + template changes
- `src/ui/src/components/PlaylistRow.vue` — CSS + template changes
- `src/ui/src/components/NavBar.vue` — script + template + CSS changes (sidebar state added)
- `src/ui/src/components/Settings.vue` — CSS + button template changes
- `src/ui/src/App.vue` — CSS change
- No backend changes; no new dependencies
