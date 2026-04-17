## Context

Siphon's auto-renamer runs a three-tier chain (yt_metadata → musicbrainz → yt_title) at download time. The result is written to the `items` table (`renamed_to`, `rename_tier`) and the file on disk is renamed accordingly. After that point, both the DB record and the filename are immutable through Siphon's interfaces.

The manual rename feature adds a post-download mutation path: users can override the resolved name via CLI or web UI. The rename updates the DB, renames the file on disk, and sets `rename_tier='manual'`. For single-video downloads (not tracked in DB), the rename updates the in-memory JobStore and the file on disk.

## Goals / Non-Goals

**Goals:**
- Allow renaming any downloaded playlist item via CLI and web UI
- Keep DB, filesystem, and UI display consistent after rename
- Support renaming items regardless of whether auto-rename was enabled
- Support renaming single-video downloads in the download queue (in-memory only)

**Non-Goals:**
- Batch rename (multiple items at once)
- Undo/revert to previous name
- Cross-playlist propagation (renaming in one playlist does not affect others)
- Renaming items while download is in progress (only `done` state)

## Decisions

### 1. File extension resolution — extract from known formats set

The system needs to know the file extension to construct the new path after rename. Three options were considered:

| Option | Approach | Verdict |
|--------|----------|---------|
| Store extension in DB | New column `file_ext` | Over-engineered; schema change for data the filesystem already knows |
| Glob the download directory | `glob.glob(f"{stem}.*")` | Fragile if names collide; unnecessary filesystem scan |
| **Extract from known extensions** | Match tail of filename against `VALID_AUDIO_FORMATS ∪ VALID_VIDEO_FORMATS` | Reuses existing constants; pure string operation; no I/O |

**Decision**: Extract the extension by matching the file's suffix against the known set `{"mp3", "opus", "mp4", "mkv", "webm"}` from `formats.py`. Fallback to `os.path.splitext()` for unexpected extensions.

### 2. Resolving the current filename on disk

When `renamed_to` is set, the file on disk is `<renamed_to>.<ext>`. When `renamed_to` is NULL (auto-rename was off), the file is `<yt_title>.<ext>` (the yt-dlp default output template). The rename function resolves the old stem as `renamed_to or yt_title`, then scans the playlist's download directory for a file matching `<stem>.<known_ext>`.

### 3. CLI syntax — three positional arguments

`siphon rename-item <playlist> <current-name> <new-name>`

Playlist is always required (scoped rename). This avoids ambiguity when the same `renamed_to` value exists across playlists. The command calls `PUT /playlists/{id}/items/{video_id}/rename` through the daemon.

Item lookup: the daemon resolves `current-name` to a `video_id` by matching against `renamed_to` (or `yt_title` if `renamed_to` is NULL) within the specified playlist. If no match or multiple matches, return an error.

### 4. Single-video rename — in-memory only

Single-video downloads have `playlist_id=None` and are not written to the `items` table. Rename for singles updates `JobItem.renamed_to` in the daemon's `JobStore` (in-memory) and renames the file on disk. No DB write. The renamed value persists across page refreshes (JobStore lives for the daemon session) but is lost on daemon restart — acceptable since the file on disk retains the new name.

The rename endpoint for singles is separate: `PUT /jobs/{job_id}/items/{video_id}/rename` since there's no `playlist_id` to route through.

### 5. UI inline edit — reuse Settings.vue pattern

The inline edit UX mirrors the interval input in Settings.vue: click-to-edit, text input with Save button, click-outside-to-cancel, Escape-to-cancel, Enter-to-save. The pencil icon appears on hover over the renamed portion of the item row. For items without a rename (`renamed_to` is NULL), clicking the pencil inserts the arrow and text input inline, prefilled with `yt_title`.

Edit is available:
- `PlaylistItemsPanel.vue`: all items (always rendered after download)
- `QueueItem.vue`: only items with `state === 'done'` (avoids race with auto-renamer)

### 6. API endpoint design

**Playlist items**: `PUT /playlists/{playlist_id}/items/{video_id}/rename`
- Body: `{ "new_name": "string" }`
- Resolves current file path, renames on disk, updates DB
- Returns 200 with updated item record

**Single-video items**: `PUT /jobs/{job_id}/items/{video_id}/rename`
- Body: `{ "new_name": "string" }`
- Resolves current file path from JobStore, renames on disk, updates JobItem in memory
- Returns 200 with updated item record

Both endpoints sanitize `new_name` using the existing `sanitize()` function from `renamer.py` to strip filesystem-unsafe characters.

### 7. Always-rename — run a rename pass even when auto-rename is OFF

Previously, when `auto_rename=False`, no post-processor was registered and files kept yt-dlp's default names. This caused a mismatch: the DB stored the raw `yt_title` (e.g. `BEACH HOUSE // Space Song` with ASCII `/`), but yt-dlp's filename sanitiser replaced unsafe characters with Unicode lookalikes (e.g. `⧸`). Manual rename couldn't find the file because `resolve_file_path` searched for the DB stem, not the actual filename on disk.

**Decision**: Always register a rename post-processor, regardless of `auto_rename`. When OFF, it runs a lightweight "passthrough" tier: replace filesystem-unsafe characters with their visual-equivalent Unicode lookalikes (the same map yt-dlp uses), skip noise stripping, skip MusicBrainz, skip metadata tiers. The result is stored in `renamed_to` with `tier="yt_title"`. This guarantees DB and disk always agree.

### 8. Visual-equivalent character map for unsafe filesystem characters

Instead of stripping unsafe characters (leaving gaps) or using generic replacements, maintain a map of unsafe ASCII characters to their Unicode visual-equivalent:

| Unsafe char | Replacement | Unicode name |
|-------------|-------------|-------------|
| `/` U+002F | `⧸` U+29F8 | BIG SOLIDUS |
| `\` U+005C | `⧹` U+29F9 | BIG REVERSE SOLIDUS |
| `:` U+003A | `꞉` U+A789 | MODIFIER LETTER COLON |
| `*` U+002A | `＊` U+FF0A | FULLWIDTH ASTERISK |
| `?` U+003F | `？` U+FF1F | FULLWIDTH QUESTION MARK |
| `"` U+0022 | `＂` U+FF02 | FULLWIDTH QUOTATION MARK |
| `<` U+003C | `＜` U+FF1C | FULLWIDTH LESS-THAN SIGN |
| `>` U+003E | `＞` U+FF1E | FULLWIDTH GREATER-THAN SIGN |
| `|` U+007C | `｜` U+FF5C | FULLWIDTH VERTICAL LINE |

This map is used in two places:
- **Auto-rename OFF**: full passthrough — replace all unsafe chars with lookalikes, preserving title appearance.
- **Auto-rename ON, tier 3, no separator found**: same replacement instead of the old `sanitize()` which left double spaces.

This matches yt-dlp's own sanitisation, so when auto-rename is OFF the rename is often a no-op on disk (file already has these chars) — but the critical gain is that `renamed_to` in the DB now matches the actual filename.

### 9. Separator-based artist–track split in tier 3 (auto-rename ON only)

When auto-rename is ON and the title falls through to tier 3 (YT title fallback), attempt to split the title on a known separator (`//`, `⧸⧸`, `–`, `—`, `-`) to produce an `Artist - Track` formatted name. This restores the old title-separator behaviour that was previously a dedicated tier.

- If a separator is found: split into artist/track, format as `Artist - Track`, apply noise stripping. This produces output consistent with tier 1/2 (e.g. `BEACH HOUSE // Space Song` → `BEACH HOUSE - Space Song`).
- If no separator is found: apply the visual-equivalent character map (Decision 8) instead of the old `sanitize()`, then apply noise stripping.

This only applies when auto-rename is ON. When OFF, separators are preserved as-is (with visual-equivalent replacement if the separator chars are unsafe).

### 10. UI display logic — auto_rename-aware arrow and tier badge

The UI previously showed the `yt_title → renamed_to` arrow format whenever `renamed_to` was truthy. With the always-rename approach (Decision 7), `renamed_to` is now always populated, causing the arrow to appear even for passthrough-renamed items where no meaningful rename occurred.

**Decision**: Thread the playlist's `auto_rename` flag through to the UI display components via props. Show the arrow format only when `autoRename` is true (actual rename happened) OR `rename_tier === 'manual'` (user explicitly renamed). Show the tier badge under the same condition.

For the Dashboard (QueueItem), `auto_rename` is stored on the `DownloadJob` dataclass and included in the `GET /jobs` response. For the Library (PlaylistItemsPanel), `auto_rename` comes from the playlist record already available in the parent `PlaylistRow` component.

This avoids checking against specific tier name strings (which would be fragile if tiers are renamed) and instead uses the semantic question "was auto-rename enabled for this download?"

## Risks / Trade-offs

**[File not found on disk]** → If the file was moved or deleted outside Siphon, `os.rename()` will fail. The endpoint returns 404 with a descriptive error. The DB is not updated (rename is atomic: both succeed or neither does).

**[Name collision on disk]** → If `<new_name>.<ext>` already exists in the download directory, `os.rename()` would silently overwrite on some platforms. Mitigation: check for existence before renaming and return 409 if a file with the target name already exists.

**[Concurrent rename of same item]** → Two UI tabs or CLI + UI could race. Low risk in practice (single user). The DB update uses the `video_id`+`playlist_id` PK so the last write wins. File rename is atomic on POSIX. Acceptable.

**[Extension not in known set]** → An older download or edge case could have an unrecognised extension. Fallback to `os.path.splitext()` handles this gracefully.
