## 1. Global: Checkmark/✕ icon buttons

- [x] 1.1 Replace interval "Save" button in `DownloadForm.vue` with checkmark SVG icon button
- [x] 1.2 Replace interval "Save" button in `PlaylistRow.vue` with checkmark SVG icon button
- [x] 1.3 Replace interval "Save" button in `Settings.vue` with checkmark SVG icon button
- [x] 1.4 Replace MusicBrainz "Save" text button in `Settings.vue` with checkmark SVG icon button
- [x] 1.5 Replace Noise Patterns "Save" with checkmark and "Cancel" with ✕ SVG icon buttons in `Settings.vue`

## 2. App.vue: Mobile padding

- [x] 2.1 Add `@media (max-width: 640px)` to `.main-content` reducing padding from `0 24px` to `0 16px`

## 3. DownloadForm: Mobile layout fixes

- [x] 3.1 Add `@media (max-width: 640px)` to reduce card padding to `16px`
- [x] 3.2 Remove forced `min-width` from `.btn-primary` at mobile breakpoint so button doesn't overflow
- [x] 3.3 Add `justify-content: space-between` to `.controls-row` so format/quality selectors spread to fill width
- [x] 3.4 Change `.toggles-row` to `flex-direction: column; align-items: flex-start` at mobile breakpoint
- [x] 3.5 Move interval editor inline inside auto-sync toggle label (fixes line-break issue on mobile)

## 4. PlaylistRow: Mobile layout restructure

- [x] 4.1 Add mobile-only title row (playlist name left, sync icon + delete icon right) visible only at ≤640px
- [x] 4.2 Add mobile-only full-width expand bar at bottom of card, visible only at ≤640px
- [x] 4.3 Hide desktop expand strip (left column) and desktop delete strip (right column) at ≤640px
- [x] 4.4 Hide desktop sync button and desktop title/meta columns at ≤640px; show mobile meta text row
- [x] 4.5 Stack auto-rename and auto-sync toggles vertically (column) at ≤640px
- [x] 4.6 Add CSS for mobile title row, mobile expand bar, and mobile meta layout

## 5. NavBar: Hamburger sidebar

- [x] 5.1 Add `sidebarOpen` ref and toggle/close logic to `NavBar.vue` script
- [x] 5.2 Add hamburger button (3-line SVG) to navbar template, visible only at ≤640px; settings icon hidden on mobile (moved to sidebar)
- [x] 5.3 Hamburger transforms to ✕ SVG when `sidebarOpen` is true
- [x] 5.4 Add sidebar overlay template: right-side fixed panel with nav buttons (Dashboard, Library, Settings)
- [x] 5.5 Add semi-transparent backdrop behind sidebar; clicking it closes sidebar
- [x] 5.6 Clicking a sidebar nav item navigates and closes sidebar
- [x] 5.7 Hide `.nav-center` inline buttons at ≤640px
- [x] 5.8 Add CSS for sidebar slide-in transition, backdrop, and mobile navbar layout

## 6. Settings: About section overflow fix

- [x] 6.1 Add `overflow-wrap: anywhere; min-width: 0` to `.about-val` and `.about-link`
- [x] 6.2 Add `@media (max-width: 640px)` to reduce `about-grid` key column from `110px` to `80px`
