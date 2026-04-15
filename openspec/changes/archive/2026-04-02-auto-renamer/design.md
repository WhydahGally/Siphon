## Context

Currently `renamer.py` is a no-op stub — `rename_file(filepath)` returns the path unchanged. The downloader calls it from a yt-dlp `progress_hooks` handler on `status == "finished"`, which fires after a stream completes but *before* postprocessors (e.g. ffmpeg MP3 transcoding) run. This means the file path at call time may be a temporary stream file, not the final output.

The goal is to produce `Artist - Track.ext` filenames for every downloaded file by chaining three resolution strategies in order of confidence.

## Goals / Non-Goals

**Goals:**
- Rename files to `Artist - Track.ext` after every completed download
- Chain: YT metadata → MusicBrainz → YT title fallback
- MusicBrainz tier is conditional on `--mb-user-agent` being supplied
- Rate-limit MB calls to ≤ 1 req/sec using a global threading lock
- Keep progress hooks untouched — rename hook is independent via `post_hooks`

**Non-Goals:**
- Async/parallel rename execution (sequential per yt-dlp session; parallelism is a future concern)
- Config file or env var support for MB User-Agent (deferred to dockerization step)
- ID3/embedded tag rewriting
- Handling the multi-container IP rate limit case

## Decisions

### Decision 1: Use a `PostProcessor` subclass instead of `post_hooks` for renaming

yt-dlp's `progress_hooks` fires per download chunk and once more when the stream finishes — but before postprocessors (ffmpeg) run. The `post_hooks` list was the initial design, but it was discovered during implementation that `post_hooks` receives only a **filename string**, not the full `info_dict` required by the rename chain. This caused a runtime `'str' object has no attribute 'get'` error.

**Chosen:** Register a `_RenamePostProcessor(PostProcessor)` subclass via `ydl.add_post_processor(..., when="after_move")`. This fires once per video after all postprocessors have completed and the file has been moved to its final path, providing the complete `info_dict` including `info_dict["filepath"]`. Progress hooks are untouched — the two mechanisms are independent.

**Alternative considered:** `post_hooks` list. Rejected because it passes only a filename string, not the metadata needed for tier 1 and tier 2 of the rename chain.

**Alternative considered:** Combined hook that merges progress and rename. Rejected — progress hooks are already wired and needed for future UI work. Mixing concerns would couple them.

### Decision 2: Pass `info_dict` to `rename_file` instead of just a filepath

The rename chain needs title, artist, track, and featured artist credits — all in `info_dict`. Passing only a filepath would require re-reading the file or re-querying yt-dlp.

**Chosen:** Change signature to `rename_file(info_dict: dict) -> None`. The filepath is available as `info_dict["filepath"]`. This is a breaking change to the public hook point, acceptable now while there are no external callers.

**Alternative considered:** Keep `rename_file(filepath)` and add a second `rename_file_with_meta(filepath, meta)`. Rejected — unnecessary dual API with no benefit.

### Decision 3: Four-tier resolution chain

```
Tier 1 — YT metadata
  Condition: info_dict has both `artist` AND `track` fields (non-empty)
  Output:    "Artist - Track"  (after primary-artist resolution; see Decision 7)
  No network call.

Tier 1.5 — Title separator parsing  (see Decision 6)
  Condition: Tier 1 failed AND YT title contains a recognised separator
  Output:    "left-side - right-side" (sanitized)
  No network call.

Tier 2 — MusicBrainz recording search
  Condition: Tier 1 and 1.5 failed AND mb_user_agent is configured (non-None/non-empty)
  Query:     GET /ws/2/recording?query=<YT title>&limit=5&fmt=json
  Scoring:   Accept top result only if score ≥ 85 AND directional token containment
             check passes for both the MB artist and MB track independently against
             the YT title (each requiring ≥ 0.4 fraction; see Decision 3a below)
  Output:    "Artist - Track" (with feat. credits from artist-credit list if > 1 entry)
  Rate-limited via global threading.Lock + last_request_time tracking.

Tier 3 — YT title fallback
  Condition: All above failed or skipped
  Output:    Sanitized YT title (strip filesystem-unsafe characters: / \ : * ? " < > |)
```

**Decision 3a: Directional token containment instead of symmetric Jaccard**

The original design specified symmetric Jaccard similarity over the joined `"artist track"` string. During implementation this caused a false positive: the MB recording "Space Song (Beach House)" by Miles McLaughlin scored 100 for the query "BEACH HOUSE // Space Song" because "Beach House" tokens appeared in the track title of the cover recording.

**Chosen:** Two independent directional checks — `_tokens_in_text(mb_artist, yt_title)` AND `_tokens_in_text(mb_track, yt_title)`. Each checks that at least 40% of the needle's tokens appear in the haystack. Directional (not symmetric) so a short artist name like "Drake" is not diluted by a long title string. Independent so an artist name embedded in a track title does not satisfy the artist check.

**Alternative considered:** Symmetric Jaccard on joined string. Rejected — caused false positives for cover recordings.

**Why score ≥ 85:** MB's own documentation treats 100 as perfect match. 85 filters clearly wrong results while accepting minor punctuation differences.

**Why token overlap:** Prevents high-scoring but wrong matches — e.g. a common word like "love" matching an unrelated popular song. Overlap validates the MB result is actually about the same song as the YT title.

### Decision 4: Global threading.Lock for MB rate limiting

When parallel downloads are added (future), multiple workers will call tier 2 concurrently. A global `threading.Lock` in `renamer.py` serializes MB calls:

```
Lock acquired → sleep(max(0, 1.0 - elapsed_since_last_call)) → make request → record time → release
```

This guarantees ≤ 1 req/sec regardless of worker count and requires zero changes when parallelism is introduced — workers will simply queue on the lock naturally.

**Alternative considered:** `time.sleep(1)` unconditionally after each call. Simpler but wastes time: if the HTTP call took 0.9s, you'd sleep an extra full second. Rejected in favour of the elapsed-time approach.

**Alternative considered:** A dedicated MB worker thread with a request queue. Overkill for 1 req/sec and adds inter-thread communication complexity. Rejected.

### Decision 5: MB User-Agent is a CLI argument, not a config file or env var

The `--mb-user-agent` flag is passed to `download()` as an optional parameter and propagated to `_RenamePostProcessor` at construction time. Config file and env var support is deferred until the dockerization step.

If `--mb-user-agent` is absent, tier 2 is skipped silently with a DEBUG-level log emitted once per session from `_RenamePostProcessor.__init__`.

### Decision 6: Tier 1.5 — Title separator as a fast-path for well-formatted YT titles

Many YouTube channels follow the `Artist // Track` or `Artist — Track` conventions when there is no YT Music catalog entry (YouTube Music populates `artist`/`track` fields only for catalog releases). Rather than hitting MusicBrainz for these common cases, we can split the title directly.

**Chosen:** Check for separators `[' ⧸⧸ ', ' // ', ' – ', ' — ', ' - ']` in that reliability order. `⧸⧸` is yt-dlp's filesystem substitute for `//`. If a separator is found with non-empty text on both sides, treat left as artist and right as track and rename without a network call.

**Known limitation:** The `-` separator is ambiguous — it matches hyphenated artist names (Alt-J, A-ha) and produces false positives. Documented in `openspec/notes/title-separator-mb-validation.md`. The intended future fix is to use the separator result as a targeted MB query hint rather than standalone truth. Deferred.

**Alternative considered:** Regex for title separators only at word boundaries. Rejected — the reliable separators (`//`, `—`) do not need it, and adding boundary logic for `-` would still not solve the hyphenated-artist problem.

### Decision 7: `_resolve_primary_artist` for comma-separated multi-artist fields

YouTube Music sometimes populates `info_dict['artist']` with a comma-separated list of all credited artists (e.g. "Porcupine Tree, Steven Wilson, Richard Barbieri, Colin Edwin Balch, Gavin Harrison"). Using this verbatim as the artist name produces unusable filenames.

**Chosen:** `_resolve_primary_artist(artist_field, info_dict)` — splits on comma, then checks each candidate against the `uploader`/`channel` field (lowercased). The channel owner is reliably the primary/credited artist on official channels. Falls back to the first entry if no match found.

**Alternative considered:** Always use first comma-separated entry. Rejected — on compilation or tribute albums the first entry may not be the primary artist; channel match is more precise when available.

### Decision 8: `--auto-rename` flag — opt-in, off by default

Prior to this decision, every download automatically had the rename chain registered. This is a behaviour change for existing users who have not opted in.

**Chosen:** `auto_rename=False` default on `download()`. `_RenamePostProcessor` is only registered when `auto_rename=True`. The `__main__` entry point exposes `--auto-rename` as an optional flag. This preserves backward compatibility and makes the feature explicit.

## Risks / Trade-offs

- **MB returns wrong match despite thresholds** → Both score and independent token overlap required; fallback to YT title is safe. Users can always rename manually.
- **YT `artist`/`track` fields absent for non-music content** → Expected; tier 1.5 often handles it, tier 3 fallback covers the rest.
- **MB service unavailable / network timeout** → Catch `requests.RequestException`, log a WARNING, fall through to tier 3. No abort.
- **Tier 1.5 `-` separator false positive for hyphenated artists** → Known; documented in `openspec/notes/title-separator-mb-validation.md`. Deferred fix: use as MB query hint rather than standalone answer.
- **Rate limit lock becomes a bottleneck in high-parallelism future** → Acceptable: MB is tier 2 (skipped for most YT Music tracks, and for tier 1.5 hits) and lock hold time is ~1s. At 10 parallel workers, worst-case queue is 10s — still reasonable.

## Migration Plan

1. Update `renamer.py` — implement chain; existing callers of `rename_file(filepath)` will break (none exist externally today).
2. Update `downloader.py` — add `_RenamePostProcessor`; remove renamer call from `_make_hook`; add `--mb-user-agent` and `--auto-rename` CLI args.
3. Manual smoke test: single video download with and without `--mb-user-agent` and `--auto-rename`.
4. No database or infrastructure changes. Rollback = revert both files.

## Open Questions

- None. All decisions are resolved for the current sequential implementation scope.
