# AcoustID Audio Fingerprinting — Research Notes

Captured during exploration of the `auto-renamer` change (2026-04-02) as a reference
for a future change to add fingerprint-based song identification.

## Why This Matters

The current text-based rename chain (YT metadata → title separator → MusicBrainz search)
can still misidentify songs when:
- The YouTube title gives no usable signal (e.g. "relaxing mix", "best hits 2024")
- MB text search returns a high-scoring but wrong result (cover songs, remixes)
- Non-music content pollutes MB results

Audio fingerprinting solves this at the source — it identifies the actual audio content
regardless of what the title says.

## The Stack: Chromaprint + AcoustID

**Chromaprint** is the fingerprint generator (open source, C library with Python bindings
via `pyacoustid` or the `fpcalc` CLI binary).

**AcoustID** is the lookup service that maps fingerprints → MusicBrainz recording IDs.
It is the same people who maintain MusicBrainz tooling.

```
Downloaded .mp3  ──▶  fpcalc / pyacoustid  ──▶  acoustic fingerprint
                                                          │
                                                          ▼
                                              AcoustID API lookup
                                                          │
                                                          ▼
                                              MusicBrainz recording ID (MBID)
                                                          │
                                                          ▼
                                              MB lookup by MBID  ──▶  artist + track
                                              (structured, zero ambiguity)
```

## AcoustID API

- **Endpoint:** `https://api.acoustid.org/v2/lookup`
- **API key required:** Yes, free — register an application at https://acoustid.org/new-application
- **Rate limit:** 3 requests/second (more generous than MB's 1/sec)
- **Auth model:** API key in `client` query param (not a secret, embed in app)
- **No User-Agent requirement** (unlike MusicBrainz)

### Request parameters

| Param         | Required | Description                              |
|---------------|----------|------------------------------------------|
| `client`      | yes      | Application API key                      |
| `duration`    | yes      | Audio duration in seconds                |
| `fingerprint` | yes      | Chromaprint fingerprint string           |
| `meta`        | no       | What to return: `recordings`, `releases`, `releasegroups`, etc. |

### Useful `meta` values for our use case
- `recordings` — returns title + artist for each matching recording
- `releasegroups` — returns album/single info
- `compress` — gzip the response (use with large meta requests)

### Example response with `meta=recordings`
```json
{
  "status": "ok",
  "results": [{
    "score": 1.0,
    "id": "9ff43b6a-...",
    "recordings": [{
      "id": "cd2e7c47-...",
      "title": "Space Song",
      "artists": [{ "id": "...", "name": "Beach House" }]
    }]
  }]
}
```

Score of `1.0` = exact fingerprint match. Even 0.8+ is highly reliable.

## Python Integration Options

**Option A: `pyacoustid` library** (wraps `fpcalc`)
```
pip install pyacoustid
```
Requires `fpcalc` binary on PATH (from Chromaprint). Returns fingerprint + duration.

**Option B: Call `fpcalc` directly via subprocess**
```
fpcalc -json path/to/file.mp3
```
Returns `{"duration": 241.3, "fingerprint": "AQABz0qUkZ..."}`. Simple, no Python dep.

**Both require:** Chromaprint (`fpcalc`) installed — same class of dependency as ffmpeg.
Install: `brew install chromaprint` (macOS) / `apt install libchromaprint-tools` (Linux).

## How It Would Fit Into the Rename Chain

Proposed position: between the current tier 1.5 (title separator) and tier 2 (MB text search).

```
Tier 1:   YT metadata (artist + track fields)          ← no network
Tier 1.5: Title separator parsing                      ← no network
Tier 1.7: AcoustID fingerprint → MBID → MB lookup     ← 2 network calls, requires fpcalc
Tier 2:   MusicBrainz text search                      ← 1 network call
Tier 3:   YT title fallback                            ← no network
```

AcoustID sits before MB text search because its results are far more reliable —
a fingerprint match is deterministic, not a fuzzy text search.

## Configuration Needed

- `--acoustid-api-key` CLI arg (or config/env var when dockerization is done)
- Like `--mb-user-agent`, if absent → tier 1.7 is skipped
- AcoustID rate limit (3/sec) is looser than MB's — a simple `time.sleep(0.34)` suffices,
  or reuse the same lock pattern as the MB rate limiter

## Known Limitations

- Requires `fpcalc` binary (another system dependency, like ffmpeg)
- Won't identify non-music content (ambient mixes, commentary, etc.)
- Very new/obscure recordings may not be in the AcoustID database yet
- Live recordings and alternate takes may fingerprint differently from studio versions

## References

- AcoustID web service: https://acoustid.org/webservice
- Chromaprint: https://acoustid.org/chromaprint
- pyacoustid: https://pypi.org/project/pyacoustid/
- AcoustID new application: https://acoustid.org/new-application
