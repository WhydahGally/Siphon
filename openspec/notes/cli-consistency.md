# CLI Consistency Notes

## Observations

### Inconsistency 1: Naming — `check-interval` vs `interval`
- `siphon config` used `check-interval` as the global key
- `siphon add` and `siphon config-playlist` both used `--interval`
- **Resolution applied**: Renamed global key to `interval` so both levels share the same name

### Inconsistency 2: `--auto-rename` dest mismatch
- `siphon add --auto-rename` had `dest="rename"` internally
- `siphon config-playlist --auto-rename` had `dest="auto_rename"`
- **Resolution applied**: Unified to `dest="auto_rename"` on `siphon add`

### Inconsistency 3: Argument style — flags vs positional key/value
- `siphon add` uses named flags: `--no-watch`, `--interval 3600`, `--auto-rename`
- `siphon config` uses positional key/value: `siphon config interval 3600`
- `siphon config-playlist` originally used flags: `--interval`, `--watch`, `--no-watch`, `--auto-rename false`
- After refactor, `siphon config-playlist` was changed to positional: `siphon config-playlist "name" interval 3600`
- This created a new inconsistency: "action" commands (`add`) use flags, "config read/write" commands use positional — but that distinction is at least logical
- However, the *values* `watched false` / `auto-rename true` feel foreign compared to `--no-watch` style flags used in `add`

### Inconsistency 4: Boolean values in `config-playlist`
- `siphon config-playlist "Listen Later" watched false` requires typing a string boolean
- `siphon add --no-watch` uses a conventional shell flag
- These two ways of expressing the same concept (`watched = false`) are inconsistent

---

## Planned Refactor

**Goal**: All commands — global config, per-playlist config, and action commands — use **dashes-style named flags** consistently.

### Target syntax

```
# Global config
siphon config --interval 86400
siphon config --log-level DEBUG
siphon config --max-concurrent-downloads 5
siphon config --mb-user-agent "Siphon/1.0 (you@example.com)"

# Read a global config value (no value = read mode)
siphon config --interval

# Per-playlist config
siphon config-playlist "Listen Later" --interval 3600
siphon config-playlist "Listen Later" --watch
siphon config-playlist "Listen Later" --no-watch
siphon config-playlist "Listen Later" --auto-rename
siphon config-playlist "Listen Later" --no-auto-rename

# Read a per-playlist value (no value = read mode)
siphon config-playlist "Listen Later" --interval
siphon config-playlist "Listen Later"           # show all (no flags = read all)

# Action commands (unchanged)
siphon add <url> --no-watch --interval 3600 --auto-rename
```

### Key decisions

- `siphon config` becomes a set of named flags, one per known key — not a generic positional `<key> [value]`
- Read mode: passing the flag alone with no value prints the current setting
- Write mode: passing the flag with a value sets it
- Per-playlist booleans use `--flag` / `--no-flag` pairs, matching `siphon add` style
- No string booleans (`true`/`false` as values) anywhere in the CLI
- `_parse_bool` helper can be removed once this is implemented

### Impact

- `cmd_config`: rewrite from positional key/value dispatch to individual `argparse` flags
- `cmd_config_playlist`: revert positional key/value approach; use flag pairs `--watch/--no-watch`, `--auto-rename/--no-auto-rename`, and `--interval SECS` (with bare `--interval` for read mode via `nargs="?"`)
- `_KNOWN_KEYS` dict stays as the source of truth for DB key mapping
- `_PLAYLIST_KNOWN_KEYS` set can be removed in favour of explicit flags
- Update module docstring and `--help` text throughout
