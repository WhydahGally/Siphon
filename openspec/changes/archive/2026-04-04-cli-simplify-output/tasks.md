## 1. Delete renderer and dead helpers from watcher.py

- [x] 1.1 Delete the `ParallelProgressRenderer` class (~130 lines)
- [x] 1.2 Delete `_make_slot_callback()` helper function
- [x] 1.3 Delete `_make_cli_progress_callback()` dead-code helper function
- [x] 1.4 Remove the `threading` import since no lock or renderer remains after deletion

## 2. Update _download_worker signature and output

- [x] 2.1 Remove `slot_index: int` and `renderer: ParallelProgressRenderer` parameters; no replacement lock parameter is added
- [x] 2.2 Record `start = time.monotonic()` at the top of the function
- [x] 2.3 On success: call `logger.info("  ✓ %s  [%s · %ds]", filename, size_str, elapsed)`; if `auto_rename` is enabled and `record.rename_tier` is not None, call a second `logger.info('    Renamed: "%s" → "%s"  [%s]', yt_title, renamed_to, tier)` immediately after
- [x] 2.4 On failure (in the except block): call `logger.warning("  ✗ %s — %s", title, err)` directly
- [x] 2.5 ~~Acquire `print_lock`, print all accumulated lines, then release~~ — no lock used; each `logger.info` / `logger.warning` call is individually atomic; rare interleaving between concurrent items is acceptable
- [x] 2.6 Remove all `renderer.item_done()` and `renderer.post()` calls
- [x] 2.7 Pass `progress_callback=None` to `download()` (the parallel path does not use it)

## 3. Update download_parallel

- [x] 3.1 Remove `ParallelProgressRenderer` creation (the `num_slots`, `renderer = …` block)
- [x] 3.2 ~~Create `print_lock = threading.Lock()`~~ — no lock is used; `threading` import removed
- [x] 3.3 Remove `slot_index` and `renderer` arguments from each `executor.submit()` call; no replacement parameter is passed
- [x] 3.4 Remove `renderer.stop()` call at the end of the function

## 4. Update _sync_parallel to print planned items list

- [x] 4.1 After `to_download` is computed (post-filter), print a numbered list of all planned titles before calling `download_parallel`
- [x] 4.2 Print a header line such as `  <N> new item(s) to download:` before the list
- [x] 4.3 Ensure the existing "Already up to date" early-return path is unaffected

## 5. Add one logger.info call in renamer.py

- [x] 5.1 Rename outcomes (original → final, tier) are logged at INFO level from `_download_worker` in `watcher.py` using `ItemRecord.rename_tier` and `ItemRecord.renamed_to` — the four `logger.debug("renamer: tier X resolved…")` calls in `renamer.py` remain unchanged at DEBUG level
- [x] 5.2 Keep all other `logger.debug` calls in `renamer.py` unchanged
