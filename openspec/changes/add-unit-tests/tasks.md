## 1. Dev Infrastructure

- [x] 1.1 Add `pytest`, `pytest-asyncio`, `httpx` to `pyproject.toml` as `[project.optional-dependencies] dev`
- [x] 1.2 Add `pytest`, `pytest-asyncio`, `httpx` to `requirements.in` (under a `# dev` comment) and regenerate `requirements.txt`
- [x] 1.3 Add `[tool.pytest.ini_options]` to `pyproject.toml` with `testpaths = ["tests/unit"]` and `asyncio_mode = "auto"`
- [x] 1.4 Create `tests/__init__.py` and `tests/unit/__init__.py` (empty)
- [x] 1.5 Create `tests/unit/conftest.py` with shared fixtures: in-memory registry, tmp_path-based renamer reset, API TestClient with lifespan mocked

## 2. Pure Module Tests

- [x] 2.1 Create `tests/unit/test_progress.py` — `make_progress_event()`: status mapping, total_bytes fallback to estimate, missing fields default to None
- [x] 2.2 Create `tests/unit/test_formats.py` — `DownloadOptions` validation (valid/invalid mode, quality, video_format, audio_format), `build_video_format_selector()`, `build_audio_postprocessors()`, `check_ffmpeg()` with mocked `shutil.which`
- [x] 2.3 Create `tests/unit/test_models.py` — `DownloadJob.done_count`, `failed_count`, `is_terminal()`, `original_total`; `JobItem` state transitions; Pydantic `PlaylistCreate`/`PlaylistPatch` validation

## 3. Renamer Tests

- [x] 3.1 Create `tests/unit/test_renamer.py` — `sanitize()`: unsafe chars replaced with visual equivalents, whitespace trimming
- [x] 3.2 Add `strip_noise()` tests: bracket/paren removal for all default patterns, custom patterns, no false-positives on clean titles
- [x] 3.3 Add `resolve_file_path()` and `extract_extension()` tests with real tmp files via `tmp_path`
- [x] 3.4 Add `embed_original_title()` and `update_title_metadata()` tests: write to a minimal ID3-tagged mp3 in `tmp_path`, read back and assert TXXX frame
- [x] 3.5 Add MusicBrainz tier tests: mock `requests.get` to return a valid response → assert tier is `"musicbrainz"`; mock a low-score response → assert fallback to `"yt_title"`

## 4. Registry Tests

- [x] 4.1 Create `tests/unit/test_registry.py` — fixture that calls `registry.init_db(tmp_path)` and resets `registry._local` and `registry._data_dir` after each test
- [x] 4.2 Add playlist CRUD tests: `add_playlist`, `get_playlist`, `update_playlist`, `delete_playlist`
- [x] 4.3 Add item CRUD tests: `add_item`, `get_item_ids_for_playlist`, `get_items_for_playlist`
- [x] 4.4 Add settings tests: `get_setting`, `set_setting`, default value
- [x] 4.5 Add failed downloads tests: `add_failed_download`, `get_failed_downloads`, `clear_failed_downloads`

## 5. JobStore Tests

- [x] 5.1 Create `tests/unit/test_job_store.py` — `create_job`: returns a UUID, job is retrievable
- [x] 5.2 Add duplicate active job guard test: second `create_job` for same playlist raises `ValueError("active_job_exists")`
- [x] 5.3 Add `update_item_state` tests: state transitions, `is_terminal()` after all items done/failed
- [x] 5.4 Add eviction test: create 50 terminal jobs + 1 new → oldest terminal is evicted, new job succeeds
- [x] 5.5 Add `cancel_all_jobs` test: pending items become cancelled, downloading items are unchanged

## 6. Downloader Tests

- [x] 6.1 Create `tests/unit/test_downloader.py` — `filter_entries()`: patch `registry.get_item_ids_for_playlist`, assert already-downloaded IDs are filtered out, new IDs pass through
- [x] 6.2 Add `filter_entries()` edge cases: empty entries list, all already downloaded, none already downloaded

## 7. API Tests

- [x] 7.1 Create `tests/unit/test_api.py` — `_normalise_youtube_url()`: mixed v=+list= URL → clean playlist URL, plain playlist URL unchanged, non-YouTube URL unchanged
- [x] 7.2 Add `GET /api/playlists` test via `TestClient`: returns 200 + JSON list (empty after fresh init)
- [x] 7.3 Add `POST /api/playlists` test: valid body → 200 + playlist ID returned; invalid format → 422
- [x] 7.4 Add `GET /api/jobs` test: returns 200 + empty list
- [x] 7.5 Add `GET /api/settings` test: returns 200 + default keys present

## 8. CI Workflow

- [x] 8.1 Create `.github/workflows/unit-tests.yml`: trigger on `pull_request` targeting `develop` and `push` to `develop`; steps: checkout, setup Python 3.12, `pip install -e ".[dev]"`, `pytest tests/unit/ -v`
