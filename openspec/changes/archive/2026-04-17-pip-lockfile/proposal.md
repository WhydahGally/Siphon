## Why

Dependencies in `requirements.txt` use loose version floors (`>=`), meaning any Docker build or local install can pull newer, potentially compromised versions. This is a supply chain attack vector — a malicious publish to PyPI silently enters the build. Pinning with hash verification (like npm's `package-lock.json`) prevents both malicious new versions and artifact tampering.

## What Changes

- Rename `requirements.txt` → `requirements.in` as the source-of-truth input file (loose constraints)
- Generate a hash-pinned `requirements.txt` lockfile using `pip-compile --generate-hashes` (pip-tools)
- Update `Dockerfile` to install with `--require-hashes` for hash verification
- Update the `ytdlp-bump.yml` GitHub Actions workflow to edit `requirements.in` and regenerate the lockfile instead of `sed`-replacing `requirements.txt` directly
- Keep `pyproject.toml` dependencies with loose constraints (abstract project metadata)

## Capabilities

### New Capabilities
- `pip-lockfile`: Hash-pinned dependency lockfile using pip-tools, with documented update workflow

### Modified Capabilities
- `ci-ytdlp-bump`: The bump workflow must update `requirements.in` and regenerate the lockfile instead of editing `requirements.txt` directly

## Impact

- `requirements.txt` — replaced by generated lockfile (full dependency tree with hashes)
- `requirements.in` — new file, replaces current `requirements.txt` as the input
- `Dockerfile` — `pip install` line updated to use `--require-hashes`
- `.github/workflows/ytdlp-bump.yml` — sed target changes, adds pip-compile step
- Developer workflow — updating any dependency requires `pip-compile --generate-hashes`
