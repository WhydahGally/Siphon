## 1. Database & Registry

- [x] 1.1 Add `sponsorblock_categories TEXT` column to `playlists` table in `_SCHEMA` (registry.py); add `ALTER TABLE playlists ADD COLUMN IF NOT EXISTS sponsorblock_categories TEXT` migration in `init_db()`
- [x] 1.2 Update `upsert_playlist` and `patch_playlist` in registry.py to read/write `sponsorblock_categories`
- [x] 1.3 Update `get_playlist` / playlist dict serialisation to include `sponsorblock_categories` and `sponsorblock_enabled` fields in returned dicts

## 2. Models & Formats

- [x] 2.1 Add `sponsorblock_categories: Optional[list[str]]` field to `DownloadOptions` dataclass in formats.py
- [x] 2.2 Update `download()` in downloader.py to add `SponsorBlockPP` and `ModifyChaptersPP` post-processors via `ydl.add_post_processor()` when `options.sponsorblock_categories` is non-empty
- [x] 2.3 Add `sponsorblock_enabled: bool` and `sponsorblock_categories: Optional[list[str]]` to `PlaylistCreate` Pydantic model in models.py
- [x] 2.4 Add `sponsorblock_enabled: Optional[bool]` and `sponsorblock_categories: Optional[list[str]]` to `PlaylistPatch` model in models.py

## 3. API

- [x] 3.1 Update job creation endpoint in api.py to read global `sponsorblock-enabled` / `sponsorblock-categories` settings when resolving effective categories, then pass to `DownloadOptions`
- [x] 3.2 Update playlist creation handler to store `sponsorblock_enabled` and `sponsorblock_categories` from `PlaylistCreate` payload
- [x] 3.3 Update playlist PATCH handler to accept and write `sponsorblock_enabled` and `sponsorblock_categories` from `PlaylistPatch` payload
- [x] 3.4 Register `sb-enabled` and `sb-cats` as valid setting keys in the settings endpoint allow-list

## 4. Scheduler

- [x] 4.1 Update scheduled sync in scheduler.py to resolve the effective SponsorBlock category list (per-playlist override → global → default `["music_offtopic"]`) and pass to `DownloadOptions` before calling `download()`

## 5. CLI

- [x] 5.1 Add `sb-enabled` and `sb-cats` to `_KNOWN_KEYS` in cli.py with descriptions
- [x] 5.2 Add validation for `sponsorblock-categories` value in `cmd_config` (parse comma-separated list, reject unknown category keys, reject bare whitespace)
- [x] 5.3 Add `sponsorblock` and `sb-cats` to `_PLAYLIST_KNOWN_KEYS`
- [x] 5.4 Add read/write handling for `sponsorblock` and `sb-cats` in `cmd_config_playlist` (include in all-keys read output, handle write with category validation for `sb-cats`)

## 6. UI — Settings.vue

- [x] 6.1 Add `sponsorBlockEnabled` and `sponsorBlockCategories` refs; load both from `/settings/sponsorblock-enabled` and `/settings/sponsorblock-categories` on mount
- [x] 6.2 Add "SponsorBlock" `settings-section` with enable toggle row (description includes hyperlink to `https://sponsor.ajay.app`)
- [x] 6.3 Add collapsible categories row using the `noise-disclosure` pattern; chevron disabled/greyed when toggle is off
- [x] 6.4 Implement chip toggles for the 9 removable categories (`sponsor`, `interaction`, `selfpromo`, `intro`, `outro`, `preview`, `hook`, `filler`, `music_offtopic`) with display labels
- [x] 6.5 Implement auto-disable logic: deselecting last chip flips toggle off, closes chevron, saves `sponsorblock-enabled = false`
- [x] 6.6 Implement re-enable restore logic: enabling toggle with empty categories restores `["music_offtopic"]` selection
- [x] 6.7 Wire save actions: toggle change saves `sponsorblock-enabled`; chip change saves `sponsorblock-categories` as JSON array

## 7. UI — DownloadForm.vue

- [x] 7.1 Add `sponsorBlock` ref seeded from global `sponsorblock-enabled` on settings load (parallel to `autoRename`)
- [x] 7.2 Add "Sponsor Block" toggle chip between "Auto rename" and "Auto sync" in the toggles row
- [x] 7.3 Include `sponsorblock_enabled: sponsorBlock.value` in the job POST body

## 8. UI — PlaylistRow.vue

- [x] 8.1 Add `sponsorBlock` local ref initialised from `props.playlist.sponsorblock_enabled`
- [x] 8.2 Add `toggleSponsorBlock()` function that flips the ref and sends immediate PATCH, reverting on error
- [x] 8.3 Add "Sponsor Block" toggle between "Auto rename" and "Auto sync" in both desktop and mobile layouts

## 9. README

- [x] 9.1 Add "SponsorBlock integration" bullet to Features list with link to `https://sponsor.ajay.app`
- [x] 9.2 Update `siphon config` key list to include `sponsorblock-enabled`, `sponsorblock-categories`
- [x] 9.3 Update `siphon config-playlist` key list to include `sponsorblock`, `sb-cats`
- [x] 9.4 Update `siphon add` flag list to include `--sponsorblock`
