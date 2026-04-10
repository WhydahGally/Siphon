## 1. Fix 1 — Dashboard download section positioning

- [x] 1.1 Commit the stashed change to `Dashboard.vue` that removes the `centered` class, `hasStarted` ref, and associated CSS

## 2. Download form toggles row layout

- [x] 2.1 Add `min-height: 36px` to `.toggles-row` in `DownloadForm.vue` to prevent layout shift when playlist URL is entered

## 3. Download queue scrolling

- [x] 3.1 Wrap job blocks in a `.queue-body` div with `flex: 1; min-height: 0; overflow-y: auto` in `DownloadQueue.vue`
- [x] 3.2 Cap `.dashboard` to `max-height: calc(100vh - 56px)` and make `.download-queue` flex column so the queue fills remaining space
- [x] 3.3 Hide all browser scrollbars globally via `scrollbar-width: none` and `::-webkit-scrollbar { display: none }` in `style.css`

## 4. Failed downloads sorting

- [x] 4.1 Move `failed` to position 0 in `STATE_ORDER` in `DownloadQueue.vue` so failed items sort to top

## 5. Granular relative time in library

- [x] 5.1 Add `formatSyncedDate` to `PlaylistRow.vue` with sub-day resolution (< 1 min / Xm ago / Xh ago) and use it for both added and synced timestamps

## 6. Interval input consistency

- [x] 6.1 Replace raw number input in `DownloadForm.vue` with the same DD:HH:MM:SS pen-icon edit pattern used in `Settings.vue`
- [x] 6.2 Add native `title` tooltip showing `Format: DD:HH:MM:SS` to interval inputs in both `DownloadForm.vue` and `Settings.vue`

## 7. Path logging in browser console

- [x] 7.1 Add `GET /info` endpoint to `watcher.py` returning `download_dir` and `db_dir`
- [x] 7.2 Add `/info` to Vite proxy in `vite.config.js`
- [x] 7.3 Fetch `/info` on mount in `App.vue` and log paths to browser console as `[siphon]` INFO messages

## 8. Custom favicon and navbar logo

- [x] 8.1 Replace `favicon.svg` with a clean flat funnel icon (purple, transparent background, horizontal filter stripes)
- [x] 8.2 Embed the funnel SVG inline in `NavBar.vue` to the left of the "Siphon" wordmark
- [x] 8.3 Apply `filter: drop-shadow` on hover so the funnel glows alongside the text
