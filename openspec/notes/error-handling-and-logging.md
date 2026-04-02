# Error Handling & Logging — Exploration Notes

_Explored: 2026-04-02_

---

## Two Philosophies in Play

The codebase deliberately separates **hard failures** (propagate up) from **soft failures** (log and continue). The guiding intent: don't abort a 50-track playlist because one video is region-blocked.

### Hard failures (propagate)
- `DownloadOptions.__post_init__` → `ValueError` for invalid mode/quality/format
- ffmpeg guard in `download()` → `RuntimeError` if ffmpeg not found
- CLI `__main__` catches both and exits with `sys.exit(1)`

### Soft failures (swallow)
- Individual video download fails → `ignoreerrors=True` in yt-dlp opts
- OS rename error → `logger.warning`, continue
- MusicBrainz request fails (any `RequestException`) → `logger.warning`, return `None`
- MusicBrainz score below threshold → `logger.debug`, fall through to next tier
- Progress callback raises → `logger.warning`, continue
- `_RenamePostProcessor.run` raises → `logger.warning`, continue

---

## What's Working Well

- `_YtdlpLogger` routes yt-dlp's internal messages through Python's logging hierarchy — no stdout leakage from the library layer.
- `logger = logging.getLogger(__name__)` in every module — polite library behaviour, hierarchical, configurable by callers.
- Soft-failure boundaries are explicit and consistently logged at `WARNING`.
- `_mb_search` catches `requests.RequestException` at the right level — not too narrow, not a bare `except`.

---

## Gaps and Open Questions

### 1. No summary after a run

`download()` returns `None`. After a 50-track playlist there's no structured answer to: how many downloaded? how many skipped? how many renames failed? All that information is scattered across log lines. The `ProgressEvent` has `status: "error"` but there's no counter, no final event, no aggregation.

### 2. CLI log level is hardcoded DEBUG

```python
logging.basicConfig(level=logging.DEBUG, ...)
```

No `--verbose` / `--quiet` flag. Fine for hand-testing, but a real user gets full yt-dlp trace output.

### 3. Renamer resolution tier is invisible to callers

The renamer always "succeeds" (tier 3 is always the fallback). But the caller can't know which tier fired. If MusicBrainz was returning garbage for an entire session, the only signal is reading `DEBUG` logs.

### 4. `ignoreerrors=True` silences individual video failures at the library level

yt-dlp routes errors through `_YtdlpLogger.error()` → `logger.error()`, so they're emitted as log events. But there's no structured way for a library consumer to count or react to them without parsing log output.

### 5. MusicBrainz failure modes are all treated equally

A timeout, a DNS failure, and a 429 rate-limit all follow the same path: `logger.warning`, return `None`, fall through to the next rename tier. There's no back-off, and no "MB is unavailable — skip remaining lookups for this session" short-circuit. This could result in a full playlist of MB requests each timing out individually.

### 6. The `status: "error"` in ProgressEvent is underspecified

With `ignoreerrors=True`, yt-dlp can emit an error progress hook for a failed video and then continue. The sequence looks like:

```
status=downloading  filename=track1.mp3
status=finished     filename=track1.mp3
status=error        filename=track2.mp3   ← region-blocked, but download continues
status=downloading  filename=track3.mp3
```

The CLI prints `[error] filename` but `download()` still returns `None` — no indication to library callers that any errors occurred.

---

## The Most User-Visible Risk

The MusicBrainz silent fallthrough is probably the highest-impact issue in practice. If MB is unavailable or rate-limiting, every track silently falls through to the title-based rename (tier 3) with no indication that the "better" rename didn't happen. A user running a 50-track playlist would see all tracks renamed, with no hint that none of them went through MB.
