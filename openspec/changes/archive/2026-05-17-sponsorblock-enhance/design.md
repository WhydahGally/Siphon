## Context

Siphon wraps yt-dlp for downloading and uses `SponsorBlockPP` + `ModifyChaptersPP` as post-processors to strip sponsor segments. Currently there is zero visibility into whether SponsorBlock processing succeeded — users only discover failures when they hear sponsor content in downloaded audio.

The downloader creates a **fresh `YoutubeDL` instance per item** (confirmed thread-safe by design). Parallel downloads use `ThreadPoolExecutor` with each thread calling `download()` independently. This means each item has its own logger, its own post-processors, and its own `info_dict` — no cross-thread state sharing.

The existing SponsorBlock spec covers category resolution, settings persistence, and UI toggles. This design extends it with health monitoring, outcome tracking, and user-facing feedback.

## Goals / Non-Goals

**Goals:**
- Detect SponsorBlock API availability before starting downloads/syncs
- Record per-item SB outcome without fragile log parsing (prefer structured hooks)
- Surface SB health issues to users with actionable choices (not silent failures)
- Provide a reusable modal component for this and future confirmation flows
- Keep all UI changes functional on mobile viewports

**Non-Goals:**
- Mid-download cancellation when SB fails (failures are recorded, not acted on live)
- Per-item retry of SB segment fetching (yt-dlp handles this internally)
- Caching SB health status (each check is fresh — SB outages are transient)
- Changing yt-dlp's internal SponsorBlock behavior or subclassing its PPs
- Category-level granularity in outcome tracking (just pass/fail per item)

## Decisions

### 1. Health Check: Direct API probe via hashed endpoint

**Choice:** `GET /health/sponsorblock` calls `sponsor.ajay.app/api/skipSegments?videoID=<test-hash>` with a 3-second timeout, 3 retries on timeout only.

**Why:** This is the same endpoint yt-dlp uses. A known video hash (e.g. `dQw4w9WgXcQ`) guarantees segments exist, so a 200 response confirms the full pipeline is working. No retry on explicit 4xx/5xx (those indicate real issues, not transient network problems).

**Alternatives considered:**
- `/api/status` endpoint — doesn't exist on SB API
- Client-side health check from the browser — CORS issues, and doesn't reflect server-side connectivity

### 2. Outcome Detection: `postprocessor_hooks` + `info_dict`

**Choice:** Register a `postprocessor_hooks` callback on the `YoutubeDL` instance. After `SponsorBlockPP` completes (`status: 'finished'`), read `info_dict['sponsorblock_chapters']`:
- Non-empty list → `success`
- Empty/absent + no SB warning in logger → `no_segments`
- Empty/absent + SB warning captured → `failed`

**Why:** `postprocessor_hooks` is a stable yt-dlp public API. Combined with the per-instance `_YtdlpLogger` (one per thread), we get structured per-item outcome without global state or log interleaving. The logger is only needed as a tiebreaker between `no_segments` and `failed` — primary signal comes from `info_dict`.

**Alternatives considered:**
- Subclassing `SponsorBlockPP` — invasive, breaks on yt-dlp updates
- Pure log parsing — works (per-instance logger isolates messages) but less structured than hooks
- Checking output file duration delta — unreliable for short segments

### 3. Warning Storage: Generic `warnings` JSON column on playlists

**Choice:** Add `warnings TEXT` (JSON array of `{type, message, timestamp}` objects) to the playlists table. SB failures append `{type: "sponsorblock", ...}`. The UI reads this column to show a ⚠ triangle.

**Why:** Generic column avoids SB-specific schema pollution. Future warnings (e.g. auth expiry, rate limits) reuse the same mechanism. Cleared on next successful sync.

**Alternatives considered:**
- Separate `sb_failures` column — not reusable
- Separate warnings table with FK — over-engineered for a JSON array

### 4. Modal Component: Slot-based `ModalDialog.vue`

**Choice:** Teleport-based modal with named slots (`header`, `body`, `actions`). Props: `maxWidth` (default 520px), `closeOnOverlay` (default true). On mobile: full-width with padding, actions stack vertically.

**Why:** The cookie upload modal already established the pattern (Teleport, overlay dismiss, centered actions). Extracting it into a reusable component DRYs up the cookie modal and serves the new SB modal.

**Alternatives considered:**
- Inline modal per use-site — duplicates overlay/teleport logic
- Third-party modal library — unnecessary dependency for a simple pattern

### 5. Split Download Button: `SplitButton.vue`

**Choice:** Primary action button with a `▾` dropdown trigger. Dropdown contains "Register" option with an ⓘ tooltip ("Add to library without downloading"). On mobile: dropdown trigger remains accessible but may wrap below the primary button.

**Why:** "Register only" is an important escape hatch when SB is down, but shouldn't clutter the main flow. A split button keeps the happy path (Download) prominent while making the alternative discoverable.

### 6. `sb_require_for_sync` Setting

**Choice:** Global boolean setting (default OFF). When ON, the scheduler checks SB health before each sync cycle. If unhealthy, the sync is skipped and a warning is appended to the playlist.

**Why:** Users who absolutely need SB processing (e.g. music playlists) should be able to prevent downloads of unprocessed files. Default OFF because most users prefer "download anyway" over missing content.

### 7. "Download anyway" Behavior

**Choice:** When user clicks "Download anyway" from the SB-unavailable modal, the system sets `sponsorblock_enabled = false` for that specific playlist/download. This is a permanent override — SB won't be retried for that playlist unless manually re-enabled.

**Why:** Avoids repeated modal prompts on every sync. The user made a deliberate choice. They can re-enable via Settings or PlaylistRow toggle.

## Risks / Trade-offs

- **[yt-dlp `postprocessor_hooks` format changes]** → Hooks are a public API; pinned yt-dlp version in requirements.txt provides stability. Test with mock hooks in unit tests.
- **[SB health check adds latency to download start]** → 3s timeout × 3 retries = 9s worst case. Acceptable for a pre-flight check. No caching means repeated checks on rapid downloads — acceptable given the transient nature of outages.
- **[Generic `warnings` column could accumulate stale data]** → Cleared on each successful sync. Manual downloads clear warnings on that playlist after success.
- **[Mobile split button usability]** → On very narrow screens (< 360px), the dropdown trigger may be tight. Mitigation: minimum touch target of 44px, and the modal itself provides the "Register" alternative.
- **[`sb_require_for_sync` blocks all items in a playlist]** → Even if only some items would have had segments. Acceptable trade-off for simplicity — it's opt-in and clearly documented.
