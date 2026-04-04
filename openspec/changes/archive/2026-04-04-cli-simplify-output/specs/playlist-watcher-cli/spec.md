## MODIFIED Requirements

### Requirement: Live download progress display
During `siphon add --download`, `siphon sync`, and `siphon sync-failed`, the CLI SHALL print a numbered list of all items planned for download before any download begins. As each item completes, the CLI SHALL emit a result log line for that item. Consecutive lines from the same item may interleave with output from another item in rare cases of near-simultaneous completion — this is acceptable and by design. After all items complete, the CLI SHALL print a summary line.

#### Scenario: Planned items list printed before download starts
- **WHEN** `_sync_parallel` (or the `add --download` path) has filtered entries and is about to dispatch
- **THEN** the CLI SHALL print a numbered list of all to-download titles, in playlist order, before any worker thread starts

#### Scenario: Item completes successfully
- **WHEN** a worker thread completes an item without error
- **THEN** the CLI SHALL atomically print: a `✓ <filename>  [<size> · <elapsed>s]` success line; if auto_rename is enabled and a rename occurred, a second line showing `  renamed: "<original>" → "<final>"  [<tier>]`

#### Scenario: Item completes with failure
- **WHEN** a worker thread fails on an item
- **THEN** the CLI SHALL atomically print a `✗ <title> — <error message>` failure line

#### Scenario: Concurrent items complete simultaneously
- **WHEN** two or more worker threads complete at nearly the same time
- **THEN** each individual log line is atomic; consecutive lines from the same item may interleave with lines from another item in rare cases of near-simultaneous completion — this is acceptable and by design

#### Scenario: Already up to date
- **WHEN** after filtering, no new items remain to download
- **THEN** the CLI SHALL print `"<playlist>: Already up to date. (<N> total)"` and exit without downloading anything
