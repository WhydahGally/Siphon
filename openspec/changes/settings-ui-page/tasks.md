## 1. Backend — Registry helpers

- [x] 1.1 Add `delete_all_playlists()` to `registry.py`: deletes rows from `playlists`, `downloaded_items`, `failed_downloads`, `ignored_items`
- [x] 1.2 Add `factory_reset()` to `registry.py`: calls `delete_all_playlists()` then also deletes all rows from `settings`

## 2. Backend — New config keys

- [x] 2.1 Add `"auto-rename"` to `_KNOWN_KEYS` in `watcher.py` with db key `auto_rename_default`; add validation: accepted values `"true"` / `"false"` only, returning `400` on anything else
- [x] 2.2 Add `"theme"` to `_KNOWN_KEYS` with db key `theme`; add validation: accepted values `"dark"` / `"light"` only, returning `400` on anything else
- [x] 2.3 Add value validation to `api_put_setting` for keys that have an allowed-values constraint

## 3. Backend — New API endpoints and CLI commands

- [x] 3.1 Add `GET /version` endpoint using `importlib.metadata.version("siphon")` and `yt_dlp.version.__version__`
- [x] 3.2 Add `DELETE /playlists` endpoint: calls `registry.delete_all_playlists()`, removes all scheduler watchers, returns `204`
- [x] 3.3 Add `POST /factory-reset` endpoint: calls `registry.factory_reset()`, removes all scheduler watchers, returns `204`
- [x] 3.4 Add `siphon delete-all-playlists` CLI subcommand: calls `DELETE /playlists` on the daemon and prints a confirmation message
- [x] 3.5 Add `siphon factory-reset` CLI subcommand: calls `POST /factory-reset` on the daemon and prints a confirmation message

## 4. Frontend — Theme infrastructure

- [x] 4.1 Add `[data-theme="light"]` CSS block to `style.css` overriding surface/background/text variables
- [x] 4.2 Update `main.js` to fetch `GET /settings/theme` before `app.mount()`; set `document.documentElement.dataset.theme = "light"` if value is `"light"`

## 5. Frontend — DownloadForm auto-rename default

- [x] 5.1 In `DownloadForm.vue` `onMounted`, fetch `GET /settings/auto-rename` and set `autoRename.value` to `false` only if the returned value is `"false"`

## 6. Frontend — Settings page

- [x] 6.1 Implement Settings page scaffold: section layout with headings (Downloads, MusicBrainz, Appearance, About, Danger Zone) and base styles matching the rest of the UI
- [x] 6.2 Downloads section: max concurrent downloads select (1–10, default 5), auto-save on change
- [x] 6.3 Downloads section: default sync interval inline editor (DD:HH:MM:SS, reuse `ddhhmmssToSecs` / `secsToDdhhmmss` / `secsToHuman` from `utils/interval.js`), explicit Save/Cancel
- [x] 6.4 Downloads section: global auto-rename toggle, auto-save on change
- [x] 6.5 MusicBrainz section: user-agent text input with placeholder and description, explicit Save button; description mentions the Dashboard warning
- [x] 6.6 Appearance section: dark/light mode toggle; on change update `document.documentElement.dataset.theme` and call `PUT /settings/theme`
- [x] 6.7 About section: display Siphon version + yt-dlp version from `GET /version`; project hyperlink; log-level dropdown with auto-save
- [x] 6.8 Danger Zone section: "Delete All Playlists" `ConfirmButton` calling `DELETE /playlists` with success toast
- [x] 6.9 Danger Zone section: "Factory Reset" `ConfirmButton` calling `POST /factory-reset` with success toast and `window.location.reload()` after 1.5s
- [x] 6.10 On mount, load all current setting values in a single `GET /settings` call and populate all controls
