# SponsorBlock — Download Path Gaps

## Context

SponsorBlock integration wires `sponsorblock_categories` into `DownloadOptions`, which
`_build_ydl_opts` passes to yt-dlp as `sponsorblock_remove`. The setting is therefore only
applied if every call site that builds `DownloadOptions` and calls into the downloader
correctly resolves and threads through the category list.

As of the sponsorblock-integration change, two download paths were fully wired:
- `POST /jobs` (Dashboard single-video + new playlist) → `run_download_job`
- Scheduler `sync_parallel` → `download_parallel` (via `get_sponsorblock_categories` on the row)

## Known Gaps

### 1. `api_retry_failed_job` — Dashboard "Retry Failed" button

**File:** `src/siphon/api.py`, `api_retry_failed_job`

This endpoint resets failed job items and re-dispatches them through `run_download_job`. It
reads format/quality/output_dir/auto_rename from the playlist row but **never resolves
`sponsorblock_categories`**. The `run_download_job` call omits the `sponsorblock_categories`
kwarg entirely.

**Impact:** Clicking "Retry Failed" in the Dashboard silently downloads without SponsorBlock
even if SponsorBlock is enabled globally or per-playlist.

**Fix:** Same pattern as `api_create_job` — resolve categories from the playlist row (or
fall back to global) and pass to `run_download_job`:

```python
sb_cats = registry.get_sponsorblock_categories(row) if row else list(registry._DEFAULT_SB_CATEGORIES)
# then in the kwargs dict:
sponsorblock_categories=sb_cats,
```

### 2. `run_sync_failed_for_playlist` — CLI `siphon sync-failed` / `/playlists/{id}/sync-failed`

**File:** `src/siphon/downloader.py`, `run_sync_failed_for_playlist`

This function fetches failure records and calls `download_parallel` directly. It builds
`DownloadOptions` from the row's format/quality but never sets
`options.sponsorblock_categories`.

**Impact:** `siphon sync-failed` and the `/playlists/{id}/sync-failed` API endpoint both
download without SponsorBlock regardless of settings.

**Fix:** After building `options`, resolve categories from the row and apply them:

```python
sb_cats = registry.get_sponsorblock_categories(row)
if sb_cats:
    options.sponsorblock_categories = sb_cats
```

## Architecture Note

The root cause of both gaps is that SponsorBlock was added as an **opt-in threading of a
field through call stacks** rather than being resolved inside `download_worker` or
`_build_ydl_opts` from a shared source of truth. Every call site that builds `DownloadOptions`
is a new opportunity to forget the field.

A more robust architecture would have `_build_ydl_opts` (or `download_worker`) resolve global
settings itself as a fallback when `options.sponsorblock_categories` is `None`, so only
explicit per-playlist overrides need to be threaded through. This would make omissions
safe-by-default rather than silently wrong.

## Priority

- Gap 1 (`api_retry_failed_job`): **High** — user-visible action in the Dashboard.
- Gap 2 (`run_sync_failed_for_playlist`): **Medium** — CLI/API path, less common.
- Architecture refactor: **Low** — nice-to-have, not urgent while the call sites are few.
