## ADDED Requirements

### Requirement: Title noise stripping utility
The renamer module SHALL expose a `strip_noise(title, patterns)` function. This capability covers the standalone noise-stripping function as a testable, reusable utility.

#### Scenario: Strip known suffix
- **WHEN** `strip_noise("Pearl Jam - Black (Official Audio)", [...])` is called with a pattern list containing `"official audio"`
- **THEN** the return value SHALL be `"Pearl Jam - Black"`

#### Scenario: Strip suffix iteratively
- **WHEN** the title has two consecutive noise suffixes
- **THEN** both SHALL be removed in successive passes until no patterns match

#### Scenario: No suffix — unchanged
- **WHEN** the title contains no noise suffix matching any pattern
- **THEN** the title SHALL be returned unchanged

#### Scenario: Custom pattern list overrides defaults
- **WHEN** a non-empty custom pattern list is supplied
- **THEN** only those patterns SHALL be used (built-in defaults SHALL NOT apply)

#### Scenario: Empty pattern list — no stripping
- **WHEN** an empty list is supplied
- **THEN** the title SHALL be returned unchanged
