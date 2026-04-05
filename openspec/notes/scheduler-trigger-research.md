# Scheduler Trigger Research

## Context

Siphon runs inside a Docker container. The container is always running. We need
to trigger `siphon sync` automatically without human intervention.

---

## Option Considered: YouTube PubSubHubbub (WebSub)

YouTube exposes a WebSub hub for channel uploads:

```
Subscribe URL: https://pubsubhubbub.appspot.com/
Topic:         https://www.youtube.com/feeds/videos.xml?channel_id=<CHANNEL_ID>
```

### Why it doesn't work for us

1. **Works at channel level, not playlist level.** Curated playlists (videos from
   multiple channels) are not covered. Only auto-generated upload playlists map
   1:1 to a channel feed.

2. **Requires an inbound HTTPS endpoint.** YouTube POSTs notifications to your
   server. A container with no public IP cannot receive these callbacks without a
   reverse proxy, Cloudflare Tunnel, or similar infrastructure. Not suitable for
   a self-contained Docker image.

### Verdict: Not viable for this project.

---

## Option Considered: YouTube Atom Feed Pre-check

Each public playlist has a free Atom feed:

```
https://www.youtube.com/feeds/videos.xml?playlist_id=<PLAYLIST_ID>
```

Returns the ~15 most recent videos with `<updated>` timestamps. The idea was:

1. Poll the feed every 2–5 minutes (one cheap HTTP GET).
2. If any `<entry>` has a newer timestamp than `last_synced_at`, trigger a full
   yt-dlp sync.
3. Otherwise, skip the yt-dlp call entirely.

### Why it's redundant for Siphon

Siphon already uses `yt-dlp extract_flat`, which lists all playlist video IDs
without downloading. This is already a lightweight scrape-and-diff operation.
The Atom feed would only be a pre-filter before that same operation.

For a **daily interval**, the two-hop overhead (Atom → extract_flat → download)
is pure waste and adds complexity with no benefit.

**The only scenario where Atom was genuinely useful**: sub-5-minute polling,
where you want to avoid hammering the yt-dlp scraper. At once-a-day cadence,
this optimisation is irrelevant.

### Verdict: Redundant given Siphon's existing extract_flat logic. Revisit only
if polling intervals drop below ~5 minutes.

---

## Chosen Approach: Internal scheduler daemon

See the `scheduler` change for implementation details. Summary:

- `siphon watch` starts a long-lived daemon process.
- An independent `PlaylistScheduler` module manages per-playlist timers.
- Config changes signal the daemon (SIGUSR1) to rebuild the scheduler from DB.
- No external dependencies beyond the stdlib.
