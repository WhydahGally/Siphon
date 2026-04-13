# Siphon

A self-hosted YT playlist watcher that automatically downloads new additions on a schedule. Built to solve specific shortcomings that we came across while using [YT-DLP](https://github.com/yt-dlp/yt-dlp) or wrappers like [MeTube](https://github.com/alexta69/metube).

Siphon runs as a daemon with a web UI — register your playlists, set a schedule, and forget about it. New tracks show up in your library automatically.

Siphon is primarily developed using spec-driven development through [OpenSpec](https://github.com/Fission-AI/OpenSpec/tree/main). Every feature starts as a specification before a single line of code is written. This is not vibe coding — there are actual specs, actual designs, and actual task lists. Revolutionary, we know.

## Features

- **Download** — Download entire playlists or single videos.
- **Parallel downloads** — Configurable concurrent downloads (1–10 workers).
- **Format selection** — Download as MP3, FLAC, WAV, M4A, OPUS, or video formats (MP4, MKV, WEBM) with quality options.
- **Playlist watching** — Monitors YouTube playlists and auto-downloads newly added videos.
- **Scheduled syncing** — Configurable per-playlist sync intervals (hourly, daily, whatever you want).
- **Smart renaming** — Cleans up filenames using metadata and MusicBrainz lookups.
- **Audio metadata embedding** — Automatically embeds artist, title, album, and cover art into audio files.
- **Web UI** — Manage playlists, view download history, configure settings, and monitor progress from your browser.
- **CLI** — Full command-line interface for automation, scripting and debugging.
- **Container-first** — Designed to run in Docker, built for Unraid.


## Screenshots

<img width="1728" height="1084" alt="Screenshot 2026-04-12 at 23 54 34" src="https://github.com/user-attachments/assets/692e6909-f569-4369-bd0e-9c239c293ea8" />
<img width="1728" height="1083" alt="Screenshot 2026-04-12 at 23 49 55" src="https://github.com/user-attachments/assets/2736e4c4-d189-4b24-bc2e-b6590d63f853" />
<img width="1728" height="1084" alt="Screenshot 2026-04-12 at 23 50 36" src="https://github.com/user-attachments/assets/d9c3b51b-0b63-4101-ba2c-2cfd357e274b" />
<img width="1728" height="1084" alt="Screenshot 2026-04-12 at 23 51 04" src="https://github.com/user-attachments/assets/81439fcc-e36f-4d4d-b521-a5fc9efe6a75" />


## Installation

### Unraid (recommended)

Siphon is built for Unraid. Install it from Community Apps:

1. Open the **Community Apps** plugin in your Unraid dashboard.
2. Search for **Siphon**.
3. Click **Install** and configure:
   - **Downloads path** — where your media gets saved (e.g. `/mnt/user/downloads/siphon/`)
   - **App Data path** — where the database and logs live (e.g. `/mnt/user/appdata/siphon/`)
   - **PUID/PGID** — user/group IDs for file ownership (defaults: `99`/`100`)
4. Start the container and open the web UI on port **8000**.

### Docker

```bash
docker run -d \
  --name siphon \
  -p 8000:8000 \
  -v /path/to/downloads:/app/downloads \
  -v /path/to/appdata:/app/.data \
  -e PUID=1000 \
  -e PGID=1000 \
  ghcr.io/whydahgally/siphon:latest
```

Or with `docker-compose`:

```yaml
services:
  siphon:
    image: ghcr.io/whydahgally/siphon:latest
    container_name: siphon
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - /path/to/downloads:/app/downloads
      - /path/to/appdata:/app/.data
    environment:
      - PUID=1000
      - PGID=1000
```

The web UI is available at `http://<your-ip>:8000`.

## Contributing

Contributions are welcome! AI-generated code is also welcome — but only if it follows spec-driven development through [OpenSpec](https://github.com/Fission-AI/OpenSpec/tree/main). No yolo PRs. Every change needs specs committed alongside the code.

When raising a PR:
1. Include the OpenSpec artifacts (proposal, design, specs, tasks) in the `openspec/changes/` directory.
2. Ensure specs exist for any new capabilities under `openspec/specs/`.
3. Test your changes locally following the steps below.

### Local Development

**Prerequisites:** Python 3.10+, Node.js 22+, ffmpeg

```bash
# Clone and set up
git clone https://github.com/WhydahGally/Siphon.git
cd Siphon

# Python environment
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Start the daemon
siphon watch

# In another terminal, run CLI commands
siphon list
```

For the web UI:

```bash
cd src/ui
npm install
npm run dev
```

#### CLI Commands

| Command | Description |
|---|---|
| `siphon watch` | Start the Siphon daemon (required for all other commands). |
| `siphon add <url>` | Register a YouTube playlist. Supports `--download`, `--no-watch`, `--interval`, `--format`, `--quality`, `--output-dir`, `--auto-rename`. |
| `siphon list` | Show all registered playlists. |
| `siphon sync [<name>]` | Download new items for a specific playlist or all playlists. |
| `siphon sync-failed [<name>]` | Retry failed downloads for a specific playlist or all. |
| `siphon cancel` | Cancel all active download jobs. |
| `siphon delete <name>` | Remove a playlist from the registry. |
| `siphon delete-all-playlists` | Remove all playlists and sync history from the registry. |
| `siphon factory-reset` | Wipe all playlists, history, and settings. Downloaded files are not affected. |
| `siphon config <key> [<value>]` | Get or set a global config value (`log-level`, `interval`, `max-concurrent-downloads`, `mb-user-agent`, `auto-rename`, `theme`, `browser-logs`, `title-noise-patterns`). |
| `siphon config-playlist <name> [<key> [<value>]]` | Get or set per-playlist config (`interval`, `auto-rename`, `watched`). |
| `siphon playlist-items <name>` | List all downloaded items for a playlist. |

## Submitting Issues

Siphon is a wrapper around [yt-dlp](https://github.com/yt-dlp/yt-dlp). Many issues — especially download failures, authentication errors, format extraction problems, or site-specific breakage — are caused by yt-dlp, not Siphon.

**Before opening an issue, check if it's a yt-dlp problem:**
- Try downloading the same URL directly with `yt-dlp <url>` from the command line.
- If `yt-dlp` fails too, the issue is upstream — check [yt-dlp issues](https://github.com/yt-dlp/yt-dlp/issues) or update yt-dlp.
- If `yt-dlp` works but Siphon doesn't, it's a Siphon issue and we want to hear about it.

**Common yt-dlp issues:**
- **"Video unavailable"** — the video is private, deleted, or region-locked.
- **"Sign in to confirm your age"** — requires cookie authentication, not currently supported by Siphon.
- **Format extraction errors** — usually fixed by updating yt-dlp. Siphon pins a specific yt-dlp version; check if a newer version resolves it.

### Log Levels

Siphon supports four log levels, configurable via the CLI or the Settings page in the web UI:

| Level | Description |
|---|---|
| `DEBUG` | Verbose output including yt-dlp internals. Use when diagnosing issues. |
| `INFO` | Normal operation. Shows sync activity, downloads, and renames. (default) |
| `WARNING` | Only warnings and errors. |
| `ERROR` | Only errors. |

Set the log level:
```bash
siphon config log-level DEBUG
```

### Log File

Siphon writes a rolling log file to `.data/siphon.log` (5 MB max, 1 backup). In Docker, this is inside the app data volume you mapped (e.g. `/path/to/appdata/siphon.log`).

**When submitting an issue, please include:**
1. The relevant section of `siphon.log` (set log level to `DEBUG` first to capture more detail).
2. The playlist or video URL that triggered the problem.
3. Your Siphon version and yt-dlp version (shown in the web UI footer).

## License

[MIT](LICENSE)
