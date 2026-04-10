## Context

The main UI feature (dashboard, library, settings pages) has shipped. During post-merge testing, small visual and behavioural issues are being discovered in individual Vue components. Each fix is self-contained — no shared state, no new dependencies, no API changes. This design document is intentionally thin because fixes are isolated and do not require cross-cutting architectural decisions.

## Goals / Non-Goals

**Goals:**
- Fix each discovered UI issue directly in its owning Vue component
- Keep the spec (`specs/ui-misc-fixes/spec.md`) as a living record, adding each fix as it is found and resolved
- All fixes land in a single branch (`fix/ui-patches`) and a single archived change

**Non-Goals:**
- Refactoring or restructuring Vue components beyond the minimal change needed
- New features or behaviour changes — fixes only
- Back-end or API changes

## Decisions

**One spec file, append-as-you-go**
Rather than creating a separate spec per fix (high overhead for tiny changes), a single `specs/ui-misc-fixes/spec.md` accumulates all fixes as `ADDED Requirements`. The spec is considered complete at verify time, not at proposal time.

**Fix scope: component-level only**
Each fix targets the specific component responsible for the issue. No intermediate abstractions or shared utilities are introduced unless two or more fixes share an identical root cause.

## Risks / Trade-offs

- [Spec is incomplete at proposal time] → Accepted and documented. The spec will be completed before the verify step runs. Verify will check implementation against the final spec, not the draft.
- [Scope creep — a "fix" grows into a feature] → If a fix requires more than a few lines of change to a single component, it should be promoted to its own change rather than merged here.
