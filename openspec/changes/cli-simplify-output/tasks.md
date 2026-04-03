## 1. Delete renderer and dead helpers from watcher.py

- [x] 1.1 Delete the `ParallelProgressRenderer` class (~130 lines)
- [x] 1.2 Delete `_make_slot_callback()` helper function
- [x] 1.3 Delete `_make_cli_progress_callback()` dead-code helper function
- [x] 1.4 Remove the `threading` import if it is no longer needed after deletion (a new `threading.Lock` will be added in task 2 — keep the import)

## 2. Update _download_one worker signature and output

- [x] 2.1 Replace `slot_index: int` and `renderer: ParallelProgressRenderer` parameters with `print_lock: threading.Lock`
- [x] 2.2 Record `start = time.monotonic()` at the top of the function
- [x] 2.3 On success: accumulate output lines into a local list — `✓ <filename>  [<size> · <elapsed>s]` — then if `auto_rename` is enabled and `record.rename_tier` is not None, add a second line `  renamed: "<yt_title>" → "<renamed_to>"  [<tier>]`
- [x] 2.4 On failure (in the except block): accumulate `✗ <title> — <error>` into the local lines list
- [x] 2.5 Acquire `print_lock`, print all accumulated lines, then release (use `with print_lock:`)
- [x] 2.6 Remove all `renderer.item_done()` and `renderer.post()` calls
- [x] 2.7 Pass `progress_callback=None` to `download()` (the parallel path does not use it)

## 3. Update download_parallel

- [x] 3.1 Remove `ParallelProgressRenderer` creation (the `num_slots`, `renderer = …` block)
- [x] 3.2 Create `print_lock = threading.Lock()` before the executor block
- [x] 3.3 Pass `print_lock` instead of `slot_index` and `renderer` in each `executor.submit()` call
- [x] 3.4 Remove `renderer.stop()` call at the end of the function

## 4. Update _sync_one to print planned items list

- [x] 4.1 After `to_download` is computed (post-filter), print a numbered list of all planned titles before calling `download_parallel`
- [x] 4.2 Print a header line such as `  <N> new item(s) to download:` before the list
- [x] 4.3 Ensure the existing "Already up to date" early-return path is unaffected

## 5. Add one logger.info call in renamer.py

- [x] 5.1 In `rename_file`, after the `RenameResult` is constructed at each of the four resolution tiers, replace the `logger.debug("renamer: tier X resolved…")` call with a single `logger.info("renamed: '%s' → '%s'  [%s]", yt_title, final_name, tier_label)` — where `tier_label` is `"yt_metadata"`, `"title_separator"`, `"musicbrainz"`, or `"yt_title_fallback"` respectively
- [x] 5.2 Keep all other `logger.debug` calls in `renamer.py` unchanged
