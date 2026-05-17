## Why

SponsorBlock integration currently has no feedback loop — users can't tell if segment removal succeeded, failed silently, or if the SponsorBlock API was unreachable. When SB is unavailable, downloads proceed without any warning, producing files with sponsor segments the user expected to be removed. This erodes trust in the download workflow.

## What Changes

- Add a pre-download SponsorBlock health check (`GET /health/sponsorblock`) that probes the SB API before starting downloads
- Surface SB unavailability to users via a modal dialog before download/sync, offering "Register only" or "Download anyway" choices
- Track per-item SponsorBlock outcome (`disabled`, `success`, `no_segments`, `failed`) using yt-dlp's `postprocessor_hooks` and `info_dict['sponsorblock_chapters']`
- Add a generic `warnings` column on playlists for surfacing a ⚠ triangle indicator in the Library UI
- Add a `sb_require_for_sync` global setting (default OFF) that blocks sync when SB is unhealthy
- Extract a reusable `ModalDialog.vue` component (slots, ✕ close, overlay dismiss, center-aligned actions)
- Add a split download button with ▾ dropdown exposing a "Register" option with ⓘ tooltip
- All UI changes must remain usable on mobile viewports (desktop-priority, mobile-usable)

## Capabilities

### New Capabilities
- `sb-health-check`: Server-side SponsorBlock API health probe with retry logic and the `/health/sponsorblock` endpoint
- `sb-outcome-tracking`: Per-item SponsorBlock outcome detection via postprocessor hooks, DB storage, and warning aggregation on playlists
- `sb-unavailable-modal`: UI modal surfacing SB unavailability before download/sync with action choices
- `modal-dialog`: Reusable ModalDialog.vue component with slots, accessibility, and mobile responsiveness
- `split-download-button`: Split action button with dropdown "Register" option and tooltip

### Modified Capabilities
- `sponsorblock`: Adding `sb_require_for_sync` setting, `warnings` column on playlists, per-item `sb_outcome` column on items

## Impact

- **Backend**: `src/siphon/api.py` (new health endpoint, settings key), `src/siphon/downloader.py` (postprocessor hooks, outcome recording), `src/siphon/registry.py` (schema migration: `warnings` on playlists, `sb_outcome` on items), `src/siphon/scheduler.py` (pre-sync health check when `sb_require_for_sync` is on)
- **Frontend**: New `ModalDialog.vue`, new `SplitButton.vue`, modifications to `DownloadForm.vue`, `PlaylistRow.vue`, `Library.vue` (warning triangle)
- **External dependency**: Network call to `sponsor.ajay.app/api/skipSegments` for health probing (existing dependency, new usage pattern)
- **Mobile**: All new UI components must be responsive; modal full-width on small screens, split button collapses gracefully
