## 1. Database Schema

- [ ] 1.1 Add `sb_outcome TEXT` column to `items` table (migration in `registry.py`)
- [ ] 1.2 Add `warnings TEXT` column to `playlists` table (migration in `registry.py`)

## 2. SponsorBlock Health Check

- [ ] 2.1 Implement `check_sb_health()` utility function in `downloader.py` (probe SB API, 3s timeout, 3 retries on timeout)
- [ ] 2.2 Add `GET /health/sponsorblock` endpoint in `api.py` returning `{status, reason}`
- [ ] 2.3 Write unit tests for health check (mock HTTP responses: success, timeout, 5xx, 4xx)

## 3. Outcome Tracking

- [ ] 3.1 Add `postprocessor_hooks` callback to `YoutubeDL` instance in `download()` that captures SB outcome from `info_dict`
- [ ] 3.2 Extend `_YtdlpLogger` to buffer SB-related warnings per instance for failure disambiguation
- [ ] 3.3 Write `sb_outcome` to items table after each item download completes
- [ ] 3.4 After sync/batch completes, aggregate SB failures into playlist `warnings` column (append or clear)
- [ ] 3.5 Write unit tests for outcome detection logic (success, no_segments, failed, disabled)

## 4. Scheduler Integration

- [ ] 4.1 Add `sb-require-for-sync` setting key (default `"false"`)
- [ ] 4.2 In scheduler sync cycle, check SB health before downloading if setting is ON; skip sync and append warning if unhealthy
- [ ] 4.3 Write unit tests for scheduler SB health gate (healthy proceeds, unhealthy skips)

## 5. API & Settings

- [ ] 5.1 Include parsed `warnings` array in playlist GET responses (empty array if NULL)
- [ ] 5.2 Add `sb-require-for-sync` to PATCH/settings and expose in GET /settings
- [ ] 5.3 Write unit tests for warnings serialization and new setting endpoints

## 6. ModalDialog Component

- [ ] 6.1 Create `ModalDialog.vue` with Teleport, slots (header/body/actions), close-on-overlay, ✕ button, Escape key handling
- [ ] 6.2 Add responsive CSS (full-width below 600px, stacked actions on mobile)
- [ ] 6.3 Add focus trap (Tab cycles within modal)
- [ ] 6.4 Refactor existing cookie upload modal to use `ModalDialog.vue`

## 7. SB Unavailable Modal

- [ ] 7.1 Create `SBUnavailableModal.vue` using ModalDialog with "SponsorBlock Unavailable" content and two action buttons
- [ ] 7.2 Wire DownloadForm to call `/health/sponsorblock` before download when SB is enabled; show modal if unhealthy
- [ ] 7.3 Implement "Register only" action (register without download, close modal)
- [ ] 7.4 Implement "Download anyway" action (set `sponsorblock_enabled = false` on playlist, proceed, close modal)

## 8. Split Download Button

- [ ] 8.1 Create `SplitButton.vue` with primary action and ▾ dropdown trigger
- [ ] 8.2 Add "Register" option with ⓘ tooltip in dropdown menu
- [ ] 8.3 Wire Register action to register-only endpoint/logic
- [ ] 8.4 Add mobile styles (44px touch targets, dropdown visible without scroll)
- [ ] 8.5 Replace existing download button in DownloadForm with SplitButton

## 9. Library Warning Indicator

- [ ] 9.1 Add ⚠ icon to PlaylistRow when `warnings` array is non-empty
- [ ] 9.2 Add tooltip on ⚠ hover showing warning messages
- [ ] 9.3 Ensure icon does not break mobile layout (inline, no overflow)

## 10. Settings UI

- [ ] 10.1 Add "Require SponsorBlock for sync" toggle row below existing SB toggle in Settings.vue
- [ ] 10.2 Disable the new toggle when main SB toggle is off
- [ ] 10.3 Wire toggle to read/write `sb-require-for-sync` setting
