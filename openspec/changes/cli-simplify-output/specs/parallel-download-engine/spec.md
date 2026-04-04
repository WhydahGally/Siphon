## MODIFIED Requirements

### Requirement: Overall sync progress reporting
The engine SHALL report progress by printing per-item result blocks as items complete. There is no live rewriting display. All output lines for a single item SHALL be flushed atomically via a shared `threading.Lock` so that concurrent threads do not interleave their output.

#### Scenario: Progress count during sync
- **WHEN** a worker completes an item (success or failure)
- **THEN** the CLI SHALL print a result block for that item; no in-place line rewriting SHALL occur

#### Scenario: Concurrent completions
- **WHEN** two workers finish at nearly the same time
- **THEN** each individual log line is atomic; consecutive lines from the same item (e.g. the `✓` line and the `renamed:` line) may interleave with output from another item in rare cases of near-simultaneous completion — this is acceptable and by design

#### Scenario: Progress at start
- **WHEN** dispatch begins with N items to download
- **THEN** a numbered planned-items list SHALL already have been printed (by the caller) before the first worker starts; the engine itself does not print the planned list
