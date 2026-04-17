## ADDED Requirements

### Requirement: Hash-pinned lockfile
The project SHALL maintain a `requirements.in` file with loose dependency constraints and a generated `requirements.txt` lockfile containing exact versions and SHA-256 hashes for all direct and transitive dependencies.

#### Scenario: Lockfile generated from inputs
- **WHEN** a developer runs `pip-compile --generate-hashes requirements.in -o requirements.txt`
- **THEN** the output `requirements.txt` contains every direct and transitive dependency pinned to an exact version with `--hash=sha256:...` entries

#### Scenario: Lockfile prevents tampered artifacts
- **WHEN** `pip install --require-hashes -r requirements.txt` is run and a downloaded artifact does not match its recorded hash
- **THEN** pip SHALL refuse to install and exit with an error

### Requirement: Docker build uses hash verification
The Dockerfile SHALL install Python dependencies using `pip install --no-cache-dir --require-hashes -r requirements.txt`.

#### Scenario: Docker build with valid lockfile
- **WHEN** the Docker image is built and all artifacts match their hashes
- **THEN** the build succeeds and all dependencies are installed at their pinned versions

#### Scenario: Docker build with tampered artifact
- **WHEN** the Docker image is built and any artifact hash does not match
- **THEN** the build fails

### Requirement: pyproject.toml keeps loose constraints
The `pyproject.toml` `[project.dependencies]` section SHALL continue to use `>=` floor constraints. It is the abstract project spec, not the deployment lock.

#### Scenario: Local editable install
- **WHEN** a developer runs `pip install -e .`
- **THEN** pip resolves dependencies using pyproject.toml constraints (not the lockfile)
