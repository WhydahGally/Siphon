## ADDED Requirements

### Requirement: Template exposes web UI port
The Unraid template SHALL configure port 8000 as a TCP port mapping with the WebUI directive pointing to it.

#### Scenario: Port configuration
- **WHEN** a user installs Siphon from Unraid CA
- **THEN** port 8000 is mapped and the Unraid dashboard links to the web UI at that port

### Requirement: Template exposes volume mappings
The template SHALL expose two path mappings: one for downloads (`/app/downloads`) and one for app data (`/app/.data`).

#### Scenario: Volume configuration
- **WHEN** a user installs Siphon from Unraid CA
- **THEN** the install screen shows path fields for Downloads (default `/mnt/user/downloads/siphon/`) and App Data (default `/mnt/user/appdata/siphon/`)

### Requirement: Template exposes PUID and PGID
The template SHALL expose `PUID` and `PGID` environment variables with Unraid defaults of 99 and 100.

#### Scenario: PUID/PGID configuration
- **WHEN** a user installs Siphon from Unraid CA
- **THEN** the install screen shows PUID (default 99) and PGID (default 100) fields

### Requirement: Template exposes UMASK
The template SHALL expose a `UMASK` environment variable with a default of `022`.

#### Scenario: UMASK configuration
- **WHEN** a user installs Siphon from Unraid CA
- **THEN** the install screen shows UMASK (default 022) under advanced settings

### Requirement: Template metadata
The template SHALL include a name, description, icon URL (PNG from GitHub raw), repository URL, category (`Downloaders:`), and network mode (`bridge`).

#### Scenario: Template renders in Unraid CA
- **WHEN** a user browses Siphon in Unraid Community Apps
- **THEN** the app shows the Siphon icon, description, and Downloaders category

### Requirement: Template location
The template file SHALL be located at `unraid/siphon.xml` in the repository.

#### Scenario: Template exists at expected path
- **WHEN** the repo is cloned
- **THEN** `unraid/siphon.xml` is a valid Unraid container template XML file
