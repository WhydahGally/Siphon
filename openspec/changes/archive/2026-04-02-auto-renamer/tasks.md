## 1. Dependencies

- [x] 1.1 Add `requests` to `requirements.txt` and `pyproject.toml`

## 2. Downloader Changes

- [x] 2.1 Add `--mb-user-agent` optional CLI argument to `__main__` in `downloader.py`
- [x] 2.2 Remove the `renamer.rename_file()` call from `_make_hook` in `downloader.py`
- [x] 2.3 Add `_RenamePostProcessor(PostProcessor)` registered via `ydl.add_post_processor(..., when="after_move")` — replaces original `post_hooks` design (post_hooks passes filename string, not info_dict; caused runtime error)
- [x] 2.4 Thread `mb_user_agent` from `download()` signature through to `_build_ydl_opts` and the post_hook closure

## 3. Renamer — Core Chain

- [x] 3.1 Change `rename_file` signature to `rename_file(info_dict: dict, mb_user_agent: str | None = None) -> None`
- [x] 3.2 Implement tier 1: extract `artist` and `track` from `info_dict`; return early if both present
- [x] 3.3 Implement tier 3: sanitize `info_dict["title"]` by stripping `/ \ : * ? " < > |`
- [x] 3.4 Implement the file rename with extension preservation using `os.rename()`; catch `OSError`, log WARNING, and return without raising

## 4. Renamer — MusicBrainz Tier

- [x] 4.1 Implement global `threading.Lock` and `_last_mb_request_time` tracking in `renamer.py`
- [x] 4.2 Implement `_mb_search(title, user_agent)` — sends GET to `https://musicbrainz.org/ws/2/recording?query=<title>&limit=5&fmt=json` with correct `User-Agent` header; catches `requests.RequestException` and non-200 responses; returns raw JSON or `None`
- [x] 4.3 Implement `_mb_passes_threshold(recording, yt_title)` — checks top result `score ≥ 85` AND independent directional token containment: MB primary artist tokens ≥ 0.4 present in YT title AND MB recording title tokens ≥ 0.4 present in YT title (replaces original Jaccard-on-joined-string design; fixed cover-song false positive)
- [x] 4.4 Implement `_mb_format_name(recording)` — builds `"Artist - Track"` or `"Artist - Track feat. Artist2"` from `artist-credit` list
- [x] 4.5 Wire tier 2 into `rename_file`: skip with DEBUG log if `mb_user_agent` is None; call `_mb_search`; call `_mb_score`; call `_mb_format_name` on pass; fall through to tier 3 on failure or low confidence

## 5. Verification

- [x] 5.1 Smoke test: download a YouTube Music track (official release) — verify tier 1 resolves without MB call
- [x] 5.2 Smoke test: download a non-music video without `--mb-user-agent` — verify tier 3 fallback, DEBUG log present
- [x] 5.3 Smoke test: download a non-music video with `--mb-user-agent` — verify MB is queried and result logged
- [x] 5.4 Verify progress hooks still fire correctly (no regression from removing renamer call in `_make_hook`)

## 6. Post-Implementation Fixes

- [x] 6.1 Replace `post_hooks` approach with `_RenamePostProcessor(PostProcessor)` registered via `add_post_processor(when="after_move")` — `post_hooks` passes a filename string not info_dict; caused `'str' object has no attribute 'get'` at runtime
- [x] 6.2 Replace Jaccard-on-joined-string MB scoring with independent `_tokens_in_text` containment checks for MB artist and MB track separately — fixed cover-song false positive ("Space Song (Beach House)" by Miles McLaughlin matching "BEACH HOUSE // Space Song")
- [x] 6.3 Add tier 1.5 (`_parse_title_separator`) — splits YT title on `⧸⧸ / // / – / — / -` separators; resolves common artist-channel titles without a network call
- [x] 6.4 Add `_resolve_primary_artist` — picks primary artist from comma-separated `info_dict['artist']` by matching against `uploader`/`channel`; fixed filenames like "Porcupine Tree, Steven Wilson, ..." from YT Music multi-artist credits
- [x] 6.5 Add `--auto-rename` flag and `auto_rename=False` default on `download()` — makes rename chain opt-in, preserving backward compatibility
- [x] 6.6 Move no-user-agent DEBUG log from `rename_file()` body to `_RenamePostProcessor.__init__` — fires once per session instead of once per file
