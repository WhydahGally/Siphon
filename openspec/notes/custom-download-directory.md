# Custom Download Directory

## Idea

Allow users to set a global default download directory via `siphon config`, with a per-job override at download time.

Currently `_DEFAULT_OUTPUT_DIR` in `watcher.py` is hardcoded relative to the source tree (`../../downloads`). This is fine for development but inflexible in production Docker deployments where you'd want to mount a volume to an arbitrary path (e.g. `/data`).

## Proposed design

- Add `download-dir` as a new key in `_KNOWN_KEYS` (stored as `download_dir` in the settings table).
- Resolve order: per-job body `output_dir` → `download-dir` config setting → `_DEFAULT_OUTPUT_DIR` hardcoded fallback.
- Expose a text input for it in the **Settings → Downloads** section.
- Per-playlist override (set at add-time via `--output-dir` in CLI, or `output_dir` in the POST body) is already supported — no schema changes needed.

## Backend changes

- `_KNOWN_KEYS`: add `"download-dir": ("download_dir", "...")`
- `_resolve_output_dir` (or call site in `api_create_job`): consult `registry.get_setting("download_dir")` when `body.output_dir` is falsy.

## UI changes

- Settings page: text input in the Downloads section, same Save-button-with-toast pattern as `mb-user-agent`.
- Show resolved effective path as muted hint text (fetch from `/settings/download-dir`).

## Notes

- Validate that the path is absolute and writable before saving (backend or frontend).
- In Docker, document that the path must map to a bind-mount or named volume.
- This is intentionally scoped as a **global default only** — per-playlist directory overrides are a separate concern and already work via the `add` command.
