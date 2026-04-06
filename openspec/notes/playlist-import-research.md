# Playlist Import Research

**Context**: Explored during the "playlist-watcher" change design. Import allows an existing local folder of downloaded files to be registered in the watcher DB so that future syncs don't re-download them.

Dev's note: I think the LLM assumed that the downloaded files were already downloaded using Siphon but I was thinking more of a local library that was downloaded manually from YT using something like meTube.

---

## The Core Problem

When a user has a folder of already-downloaded files and wants to start using the watcher, the DB is empty. Without import, the next `siphon sync` would try to re-download every item in the playlist.

The yt-dlp archive file only stores video IDs. There is no way to recover a video ID from a local file (no embedded metadata carries it by default). This means mapping local files back to YouTube videos requires matching titles — which is lossy due to renaming.

---

## The Mismatch Problem

The renamer can substantially transform the original YouTube title before writing it to disk:

```
YT title:      "Beach House - Space Song (Official Audio)"
After tier 1:  (unchanged — YT metadata)
After tier 1.5:"Beach House - Space Song.mp3"
After tier 2:  "Space Song - Beach House.mp3"  ← artist/track SWAPPED
After tier 3:  "Beach House - Space Song (Official Audio).mp3"  ← sanitized only
```

Any fuzzy-matching approach must handle this inversion and the variable suffix stripping.

---

## Three Approaches Considered

### 1. Fuzzy Title Match (Low confidence, low effort)
- Fetch full playlist metadata from YT
- Normalize YT titles and local filenames (lowercase, strip ext, strip parens, etc.)
- Attempt fuzzy match (e.g., using `difflib.SequenceMatcher`)
- **Problem**: Tier 2 (MusicBrainz) renames invert artist/track order. A match of 0.5 on "Beach House - Space Song" vs "Space Song - Beach House" is unreliable.
- **Risk**: False positives could incorrectly mark a video as downloaded when it wasn't.

### 2. User-Guided Matching (High confidence, medium effort)
- `siphon import <url> <folder>` fetches the playlist, attempts automatic matching for high-confidence pairs
- Presents an interactive diff: "Matched 44/50. These 6 couldn't be matched — please confirm or skip."
- User validates ambiguous matches before they're committed to the archive/DB
- **Best UX** for power users but requires interactive mode

### 3. Pessimistic Import (High confidence on no-redownload, low effort)
- Fetch the playlist metadata, write ALL video IDs to the archive file
- DB entries created with `status = 'imported_unverified'`, with `yt_title` populated but `renamed_to` and `rename_tier` left NULL
- Net effect: no items are re-downloaded; DB has the skeleton; rename data is missing
- Future `siphon verify` command could attempt to fill in the blanks via fuzzy match or user review
- **Simplest to implement**, good enough as a starting point

---

## Recommendation

Implement **Pessimistic Import** first (option 3) as a standalone feature. It provides the critical safety guarantee (no re-downloads) with minimal complexity. A follow-on can add the fuzzy/interactive layer to backfill `renamed_to` and `rename_tier` for imported items.

Key design points when implementing:
- Keyed by playlist ID, not name (names can change on YT)
- The DB `status` field on `items` is useful here: `downloaded`, `imported_unverified`, `skipped`
- The `siphon list` output could flag playlists with unverified imported items
- A future `siphon verify` command could compare local filenames against re-fetched YT metadata to fill in gaps

---

## Open Questions (to resolve when implementing)

1. How should `siphon import` interact with `--download`? Does importing then syncing download only new items, or re-verify all?
2. Should `imported_unverified` items be excluded from UI displays by default?
3. Can yt-dlp's `extract_info` (without downloading) be used to fetch the full playlist video ID list efficiently?
