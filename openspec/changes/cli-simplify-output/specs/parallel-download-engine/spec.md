## MODIFIED Requirements

### Requirement: Overall sync progress reporting
The engine SHALL report progress by logging per-item result blocks as items complete. There is no live rewriting display. Within a single item, the `✓`/`✗` line is always emitted before the rename line (guaranteed by the thread-local buffer — see design D1). Across concurrent items, output ordering is best-effort: lines from one item may appear between lines of another item in cases of near-simultaneous completion.

#### Scenario: Progress count during sync
- **WHEN** a worker completes an item (success or failure)
- **THEN** the worker SHALL log a result block for that item via `logger.info`/`logger.warning`; no in-place line rewriting SHALL occur

#### Scenario: Intra-item ordering
- **WHEN** a worker completes an item that was auto-renamed
- **THEN** the `✓ <filename>  [<size> · <elapsed>s]` line SHALL always appear before the `Renamed: "<original>" → "<final>"  [<tier>]` line for the same item

#### Scenario: Concurrent completions (best-effort)
- **WHEN** two workers finish at nearly the same time
- **THEN** lines from the two items may interleave in the log output; this is accepted behaviour

#### Scenario: Progress at start
- **WHEN** dispatch begins with N items to download
- **THEN** a numbered planned-items list SHALL already have been logged (by the caller) before the first worker starts; the engine itself does not log the planned list
