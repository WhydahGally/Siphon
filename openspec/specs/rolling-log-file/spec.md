### Requirement: Rolling log file handler
The daemon SHALL add a `RotatingFileHandler` to the `siphon` logger during startup. The handler SHALL write to `.data/siphon.log` (same directory as the SQLite database). The handler SHALL rotate when the file reaches 5 MB (`maxBytes=5242880`). The handler SHALL keep at most 1 backup file (`backupCount=1`). The handler SHALL use the same text format as the stderr handler: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`.

#### Scenario: Log file created on daemon start
- **WHEN** `siphon watch` starts and `.data/siphon.log` does not exist
- **THEN** the file SHALL be created and log records SHALL be written to it

#### Scenario: Log file rotates at 5 MB
- **WHEN** `.data/siphon.log` reaches 5 MB
- **THEN** it SHALL be renamed to `.data/siphon.log.1` and a new `.data/siphon.log` SHALL be created

#### Scenario: Only one backup kept
- **WHEN** rotation occurs and `.data/siphon.log.1` already exists
- **THEN** the existing `.data/siphon.log.1` SHALL be overwritten (no `.log.2` created)

#### Scenario: Log level respected
- **WHEN** the `siphon` logger level is set to WARNING
- **THEN** only WARNING, ERROR, and CRITICAL records SHALL appear in the log file
