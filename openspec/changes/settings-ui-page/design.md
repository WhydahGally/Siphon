## Context

The web UI Settings page is a stub. All global configuration today requires the CLI (`siphon config`). The backend already has `/settings` (GET all), `/settings/{key}` (GET one), and `PUT /settings/{key}` for the four existing config keys. The frontend tech stack is Vue 3 + Vite. CSS uses custom properties on `:root` for all colour tokens.

## Goals / Non-Goals

**Goals:**
- Build out `Settings.vue` as the primary UI for global configuration
- Add two missing API endpoints: `GET /version` and `POST /factory-reset` (+ `DELETE /playlists`), each with a corresponding CLI subcommand
- Add `auto-rename` and `theme` as new settable config keys (backend + CLI)
- Dark/light mode that persists in DB and loads without a flash on page refresh
- Keep the implementation minimal — prefer editing existing patterns over new abstractions

**Non-Goals:**
- Custom accent colour / theme engine (dropped)
- Per-playlist settings UI (already covered by Library page)
- Download directory config (captured in notes for a future change)

## Decisions

### 1. Light mode via `data-theme` attribute on `<html>`

**Decision:** Add a `[data-theme="light"]` block to `style.css` that overrides the surface/background/text variables. The accent colour stays the same in both modes.

**Rationale:** Minimal change — only `style.css` gains a new rule block. No new files, no CSS-in-JS, no preprocessing. The existing `:root` dark values stay untouched.

**Alternative considered:** A second CSS file imported conditionally. Rejected: more moving parts, harder to maintain in sync.

### 2. Theme init in `main.js` before Vue mount

**Decision:** In `main.js`, fetch `GET /settings/theme` before calling `createApp().mount()`. Set `document.documentElement.dataset.theme` immediately if the value is `light`.

**Rationale:** Prevents a flash of dark mode on page load for light-mode users. The fetch is a single fast DB read on localhost; the extra ~20ms before mount is acceptable. If the daemon is unreachable, we fall through to dark (the default) silently.

**Alternative considered:** Apply theme in a Vue `onBeforeMount` hook in `App.vue`. Rejected: theme is applied after the first render, causing a visible flash.

### 3. `auto-rename` global config key — same `_KNOWN_KEYS` pattern

**Decision:** Add `"auto-rename"` to `_KNOWN_KEYS` with db key `auto_rename_default`, accepted values `"true"` / `"false"`. `DownloadForm.vue` reads it on mount and uses it as the checkbox default.

**Rationale:** Reuses the existing settings API machinery with zero new code paths. The per-job checkbox still overrides freely; this only changes the initial state of the checkbox.

### 4. `/version` endpoint reads from package metadata

**Decision:** Use `importlib.metadata.version("siphon")` for the Siphon version and `yt_dlp.version.__version__` for yt-dlp. Return `{ "siphon": "...", "yt_dlp": "..." }`.

**Rationale:** `importlib.metadata` is stdlib (Python 3.8+) and always reflects the installed package version, staying in sync with `pyproject.toml` without any hardcoding.

### 5. Factory reset and delete-all-playlists as separate endpoints and CLI commands

**Decision:**
- `DELETE /playlists` / `siphon delete-all-playlists` — deletes all rows from `playlists`, `downloaded_items`, `failed_downloads`, `ignored_items`. Removes all scheduler watchers. Keeps `settings`.
- `POST /factory-reset` / `siphon factory-reset` — runs the above plus truncates `settings`.

**Rationale:** Two separate endpoints matches the two-button UX. Both reuse a helper in `registry.py` (`delete_all_playlists()`) with an optional `include_settings` parameter. Matching CLI subcommands follow the existing naming convention (`siphon delete`, `siphon sync-failed`) — words separated by hyphens, verb-first where unambiguous.

**Alternative considered:** `DELETE /playlists?full=true`. Rejected: semantically cleaner as two distinct operations; the UI intent is different enough to warrant different endpoints.

### 6. Settings page layout — sections, no tabs

**Decision:** A single scrollable page divided into labelled sections: Downloads, MusicBrainz, Appearance, About, Danger Zone.

**Rationale:** There are only ~8 controls total. Tabs would add nav overhead for no benefit. Simple vertical scroll is the most accessible and requires no new routing logic.

### 7. Save strategy per control

| Control | Save trigger |
|---|---|
| Max concurrent downloads | Auto-save on `<select>` change |
| Auto rename (global default) | Auto-save on toggle change |
| Log level | Auto-save on `<select>` change |
| Default sync interval | Inline edit (same pattern as Library) |
| MusicBrainz user-agent | Explicit Save button |
| Theme | Auto-save on toggle change |

**Rationale:** Auto-save for discrete selects/toggles (no partial state), explicit Save for free-text inputs that can be mid-edit.

## Risks / Trade-offs

- `main.js` theme fetch adds a serial network call on startup → acceptable on localhost, not on high-latency networks. Mitigation: hard-code dark as default, only fetch to override.
- `POST /factory-reset` is irreversible → guarded by two-stage `ConfirmButton` in UI; no backend guard is needed (this is a personal tool).
- `[data-theme="light"]` does not cover hardcoded `rgba(124, 106, 247, X)` values in components — those stay purple in light mode too, which is fine since the accent colour is not changing.

## Migration Plan

1. Backend changes land first (new endpoints, new settings keys) — fully additive, no breaking changes
2. Frontend changes can land in any order after that
3. No DB migration needed — new settings keys are inserted on first write via `INSERT OR REPLACE`
4. No rollback required — all changes are additive; removing them would just restore the stub Settings page
