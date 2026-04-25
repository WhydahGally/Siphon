## Context

The Siphon UI is a Vue 3 SPA with no CSS framework — all styling is hand-written with CSS variables and scoped component styles. The desktop layout was designed for a `960px` max-width container. Five components require changes: `NavBar`, `DownloadForm`, `PlaylistRow`, `Settings`, and `App.vue`.

The existing layout patterns are:
- `NavBar`: 3-column CSS grid (`1fr auto 1fr`), fixed 56px height
- `DownloadForm`: flex column card with a URL row (`input + button`) and controls row
- `PlaylistRow`: 4-column CSS grid (`52px 250px 1fr 76px`) — the primary overflow offender on mobile
- `Settings`: flex rows (`setting-row`) with `space-between`, generally responsive except the About grid
- `App.vue`: `max-width: 960px; padding: 0 24px` content wrapper

## Goals / Non-Goals

**Goals:**
- All UI is usable (no overflow, no off-canvas elements) at ≥375px viewport width
- Desktop layout (≥641px) is pixel-identical to current state, except the checkmark button replacement which improves both breakpoints
- NavBar gets a functional hamburger sidebar on mobile
- `PlaylistRow` gets a fully restructured mobile layout preserving all functionality
- Interval Save buttons replaced with a checkmark SVG at all breakpoints for consistency

**Non-Goals:**
- Full mobile-first redesign or visual overhaul
- New npm dependencies (no UI library, no CSS framework)
- Touch gesture support beyond standard tap/click
- Changes to the backend or API

## Decisions

**D1: Single breakpoint at 640px**
All responsive overrides use `@media (max-width: 640px)`. This maps to landscape phones and small portrait tablets as "mobile". Avoids complexity of multiple breakpoints for a tool that's primarily used on desktop.

**D2: CSS-only responsive for all components except NavBar**
`DownloadForm`, `PlaylistRow`, `Settings`, and `App` are fixed purely with CSS media queries inside each component's `<style scoped>` block. No Vue logic changes needed for these.

**D3: NavBar sidebar requires Vue reactive state**
The hamburger/sidebar requires `open` ref state in `NavBar.vue`. The sidebar is a `<div>` appended to the navbar template with `position: fixed; right: 0; top: 0; height: 100vh; width: 240px` that translates in/out with a CSS transition. A semi-transparent backdrop sits behind it. State is local to `NavBar` — `App.vue` doesn't need changes for this.

**D4: PlaylistRow mobile layout — restructure with media query, not a separate component**
The 4-column grid is overridden at ≤640px to `display: block` on `.row-body`, with child elements repositioned using flexbox. The expand strip moves to a full-width `<div>` placed after `.row-body` via CSS `order` or template reorder. Since the expand strip is a `<button>` and the delete strip is inside `.row-body`, the simplest approach is to let the template render both always and use `display: none` to show/hide each per breakpoint: the sidebar expand strip is hidden on mobile, a new bottom expand bar (already in template) is shown; the inline delete strip is hidden, an inline delete icon in the title row is shown.

**D5: Checkmark button replaces "Save" text everywhere**
A single thin white checkmark SVG (`<path d="M5 13l4 4L19 7">`) replaces the "Save" label in: `DownloadForm` interval, `PlaylistRow` interval, `Settings` interval, `Settings` MusicBrainz, `Settings` Noise Patterns. The Cancel buttons in Noise Patterns get an ✕ SVG. Button size/padding is kept small (`padding: 4px 7px`) to stay inline. This is applied at all breakpoints — it's a global cosmetic improvement.

**D6: About grid overflow — `min-width: 0` + `overflow-wrap`**
The `about-grid` uses `grid-template-columns: 110px 1fr`. The `1fr` column already has room, but `justify-items: end` right-aligns values. On mobile (375px viewport, 16px padding each side = 343px content, minus 20px card padding each side = 303px card width), `1fr` resolves to 303 - 110 - 16 (gap) = 177px — enough for version numbers but not the GitHub URL. Fix: add `overflow-wrap: anywhere; min-width: 0` to `.about-val` / `.about-link` so text wraps inside the column instead of overflowing. No layout change needed at all; this is a 2-line CSS addition.

## Risks / Trade-offs

- **PlaylistRow dual-render cost**: Rendering both mobile and desktop delete/expand elements always, using `display: none` to toggle, means slightly more DOM nodes. Negligible given the number of playlist rows in practice.
- **Marquee title on mobile**: `PlaylistRow` has a JS-computed marquee for overflowing playlist names that runs `onMounted`. On mobile, the title container width will be different. The marquee computation will still run correctly since it reads `scrollWidth vs clientWidth` at mount time — but it runs once. If the user resizes the viewport, the marquee won't recalculate. Acceptable given the tool's use case.
- **Sidebar z-index conflicts**: The sidebar uses `z-index: 100`, NavBar uses `z-index: 10`. Toast container uses a high z-index. Need to verify ToastContainer z-index doesn't sit below sidebar.

## Migration Plan

Pure frontend CSS/template changes. No deployment steps or rollback complexity beyond reverting the commit. The existing `feat/resp-ui` branch is already created.
