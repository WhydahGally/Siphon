## Context

Siphon has 5 direct Python dependencies declared in both `requirements.txt` and `pyproject.toml`. Only `yt-dlp` is pinned to an exact version; the rest use `>=` floors. The Docker image builds from `requirements.txt`, so unpinned deps resolve to whatever is latest on PyPI at build time. An automated GitHub Actions workflow (`ytdlp-bump.yml`) updates the yt-dlp version via `sed` on `requirements.txt`.

## Goals / Non-Goals

**Goals:**
- Pin all direct and transitive dependencies to exact versions with hash verification
- Prevent supply chain attacks (malicious new versions and artifact tampering)
- Keep the yt-dlp auto-bump workflow functional with the new lockfile approach
- Provide a simple update workflow for developers

**Non-Goals:**
- Pinning `pyproject.toml` dependencies (stays loose — it's the abstract project spec)
- Adding pip-tools as a runtime dependency (it's a dev/CI-only tool)
- Automating updates for non-yt-dlp dependencies (manual for now)

## Decisions

### 1. pip-tools for lockfile generation

**Choice**: Use `pip-compile --generate-hashes` from pip-tools to generate the lockfile.

**Alternatives considered**:
- **Manual `==` pins**: Only covers direct deps, not transitives. No hash verification.
- **Poetry / pdm**: Full project manager — overkill for 5 deps and adds migration complexity.
- **pip freeze**: Captures versions but no hashes. Doesn't track input constraints.

**Rationale**: pip-tools is lightweight, well-established, and produces a standard `requirements.txt` that needs no special tooling to install. The `requirements.in` → `requirements.txt` split mirrors the `package.json` → `package-lock.json` pattern.

### 2. File layout: requirements.in + requirements.txt

```
requirements.in          ← human-edited, loose constraints (like package.json)
requirements.txt         ← generated lockfile with hashes (like package-lock.json)
pyproject.toml           ← keeps loose deps, unchanged
```

The Dockerfile continues to `pip install -r requirements.txt` — just now with `--require-hashes`.

### 3. yt-dlp bump workflow adaptation

The workflow currently does:
```
sed -i "s/yt-dlp==OLD/yt-dlp==NEW/" requirements.txt
```

It will change to:
```
sed -i "s/yt-dlp==OLD/yt-dlp==NEW/" requirements.in
pip-compile --generate-hashes requirements.in -o requirements.txt
```

pip-tools needs to be installed in the CI runner. The workflow will `pip install pip-tools` before the compile step. The sed target changes from `requirements.txt` to `requirements.in`, and both files are committed.

### 4. Dockerfile uses --require-hashes

The `pip install` line adds `--require-hashes` so pip refuses to install any artifact whose hash doesn't match the lockfile. This is the actual supply chain defense — version pins alone don't prevent artifact tampering.

## Risks / Trade-offs

- **Merge conflicts in lockfile** → Lockfile is fully regenerated from `.in` file, so conflicts are resolved by re-running `pip-compile`. Not a concern for a single-developer project.
- **pip-compile needs network access** → Only needed at dev time or in CI when updating deps, not at Docker build time. Docker build uses the pre-compiled lockfile.
- **Platform-specific hashes** → pip-compile generates hashes for all available platforms by default. The Docker image is linux/amd64 but the lockfile will include all platform wheels, which is fine — pip just picks the matching one.
