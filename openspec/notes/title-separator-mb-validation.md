# Title Separator — Known Limitation & Future Fix

Captured during `auto-renamer` implementation (2026-04-02).

## Current Behaviour

Tier 1.5 splits the YT title on common separators (`//`, `⧸⧸`, `–`, `—`, `-`) and
uses the split result directly as `Artist - Track` without any validation.

Example that works:
```
"BEACH HOUSE // Space Song"  →  "Beach House - Space Song"  ✓
```

## The Problem

Artist names and track titles often contain the same characters used as separators,
leading to false positives. For example:

```
"Tyler, the Creator - EARFQUAKE"    →  fine, "-" splits correctly
"Alt-J - Breezeblocks"              →  "Alt" / "J - Breezeblocks"  ✗  (hyphen in artist name)
"Suede - She's in Fashion"          →  fine
"A-ha - Take On Me"                 →  "A" / "ha - Take On Me"  ✗
"Post Malone - Rockstar - Remix"    →  "Post Malone" / "Rockstar - Remix"  (ambiguous)
```

The `-` separator is especially dangerous. `//` and `—` are safer because they are
rarer in artist names, but not immune.

## Intended Design (Not Yet Implemented)

The title separator was always meant to produce a *hint* for MB, not a final answer.
The original design intent:

```
Tier 1.5:
  Parse separator hint  →  artist_hint, track_hint
  If hint found:
    Query MB with structured search:
      recording:"<track_hint>" AND artist:"<artist_hint>"
    If MB confirms the match (score + token check):
      use MB result  ← authoritative, validated
    Else:
      fall through to MB free-text or tier 3

  MB validation eliminates false positives from artist names containing separators.
```

This way the separator is a signal that improves the MB query, not a standalone source
of truth. "Alt-J - Breezeblocks" would query MB for `recording:"J - Breezeblocks" AND artist:"Alt"`
which would return no confident result, and the renamer would fall through gracefully.

## Why Left As-Is

The current playlist is mostly channels using `//` and `–` which are safe separators.
The fix is deferred until the MB query layer is improved (likely as part of the
AcoustID fingerprinting change or a dedicated title-parsing improvement change).

## What to Implement

1. When a separator is found, use it to build a **targeted MB search query**:
   `recording:"<track_hint>" AND artist:"<artist_hint>"` instead of passing the raw title.
2. Only accept the result if it passes the existing score + token threshold.
3. Remove the early-return path so the separator never resolves without MB confirmation.
4. Consider a separator confidence ranking — `//` and `—` are high confidence,
   `-` is low confidence and should always require MB validation.

## References

- MB search query syntax: https://musicbrainz.org/doc/MusicBrainz_API/Search
- Related note: `openspec/notes/acoustid-fingerprinting.md`
