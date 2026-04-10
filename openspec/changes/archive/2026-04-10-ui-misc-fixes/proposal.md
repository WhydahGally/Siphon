## Why

After shipping the main UI feature (dashboard, library, settings), a set of small visual and behavioural issues were discovered during testing. These don't warrant individual changes but are real regressions or rough edges that need to be cleaned up before the UI is considered polished.

## What Changes

- Remove the dynamic centering behaviour from the Dashboard — the download form should always sit at the top, not animate to center when no jobs exist
- Additional UI fixes to be discovered and added as testing continues (spec will be updated iteratively before verify)

## Capabilities

### New Capabilities
- `ui-misc-fixes`: Tracks all discovered miscellaneous UI fixes applied to the web dashboard. Acts as a living list of fixes, updated as issues are found during testing.

### Modified Capabilities

## Impact

- `src/ui/src/components/Dashboard.vue` — first known fix already applied (stashed, ready to commit)
- Other UI component files TBD as fixes are discovered
