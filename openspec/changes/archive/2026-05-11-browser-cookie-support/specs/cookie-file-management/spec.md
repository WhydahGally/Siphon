## ADDED Requirements

### Requirement: POST /settings/cookie-file — upload cookie file
The daemon SHALL expose a `POST /settings/cookie-file` endpoint that accepts a cookie file upload. The request body SHALL be the raw file contents (`Content-Type: text/plain` or `multipart/form-data`). The endpoint SHALL enforce a maximum upload size of 1 MB; requests exceeding this limit SHALL be rejected with `413 Request Entity Too Large`. The endpoint SHALL validate that the file is in Netscape HTTP Cookie File format by checking that at least one non-comment line contains exactly 7 tab-separated fields where field 2 and field 4 are `TRUE` or `FALSE` and field 5 is a non-negative integer string. If validation fails, the endpoint SHALL return `400 Bad Request` with a descriptive message. On success, the file SHALL be saved to `.data/cookies.txt` (regardless of the original filename), with permissions set to `0o600`. If a cookie file already exists it SHALL be replaced. The response on success SHALL be `204 No Content`.

#### Scenario: Valid cookie file uploaded
- **WHEN** `POST /settings/cookie-file` is called with a valid Netscape-format cookie file ≤ 1 MB
- **THEN** the file SHALL be saved to `.data/cookies.txt` with `0o600` permissions and the response SHALL be `204`

#### Scenario: Cookie file replaced
- **WHEN** `POST /settings/cookie-file` is called and `.data/cookies.txt` already exists
- **THEN** the existing file SHALL be overwritten atomically and the response SHALL be `204`

#### Scenario: File exceeds 1 MB
- **WHEN** `POST /settings/cookie-file` is called with a body larger than 1 048 576 bytes
- **THEN** the response SHALL be `413` and no file SHALL be written to disk

#### Scenario: Invalid content — not Netscape format
- **WHEN** `POST /settings/cookie-file` is called with a file that has no lines matching the 7-field tab-separated Netscape cookie structure
- **THEN** the response SHALL be `400 Bad Request` with a message indicating the file does not appear to be a valid Netscape cookie file

#### Scenario: Comment-only file rejected
- **WHEN** `POST /settings/cookie-file` is called with a file containing only `# Netscape HTTP Cookie File` and blank lines
- **THEN** the response SHALL be `400 Bad Request`

---

### Requirement: GET /settings/cookie-file — query configured state
The daemon SHALL expose a `GET /settings/cookie-file` endpoint. The response SHALL be `200 OK` with JSON body `{"set": true}` if `.data/cookies.txt` exists and is a regular file, or `{"set": false}` otherwise. The cookie file contents and its filesystem path SHALL NOT be included in the response under any circumstance.

#### Scenario: Cookie file is configured
- **WHEN** `GET /settings/cookie-file` is called and `.data/cookies.txt` exists
- **THEN** the response SHALL be `200 OK` with body `{"set": true}`

#### Scenario: Cookie file is not configured
- **WHEN** `GET /settings/cookie-file` is called and `.data/cookies.txt` does not exist
- **THEN** the response SHALL be `200 OK` with body `{"set": false}`

---

### Requirement: DELETE /settings/cookie-file — remove cookie file
The daemon SHALL expose a `DELETE /settings/cookie-file` endpoint. It SHALL call `delete_cookie_file_safe(data_dir)`. If the file does not exist the response SHALL be `404 Not Found`. On success the response SHALL be `204 No Content`.

#### Scenario: Cookie file deleted
- **WHEN** `DELETE /settings/cookie-file` is called and `.data/cookies.txt` exists
- **THEN** the file SHALL be deleted and the response SHALL be `204`

#### Scenario: No cookie file present
- **WHEN** `DELETE /settings/cookie-file` is called and no cookie file exists
- **THEN** the response SHALL be `404 Not Found`

---

### Requirement: delete_cookie_file_safe() shared utility
The registry module SHALL expose `delete_cookie_file_safe(data_dir: str) -> bool` that deletes the cookie file inside `data_dir`. Before calling `os.remove()`, the function SHALL enforce all of the following safety invariants:
1. The resolved absolute path of the target file MUST start with `os.path.abspath(data_dir) + os.sep`
2. The basename of the target file MUST match `re.fullmatch(r'cookies\.txt', basename)` exactly
3. The target path MUST exist and be a regular file

If any invariant fails, the function SHALL raise `RuntimeError`. If the file does not exist (invariant 3 fails), the function SHALL return `False`. On successful deletion it SHALL return `True`. This function SHALL be the single implementation used by both `DELETE /settings/cookie-file` and `POST /factory-reset`.

#### Scenario: Safe deletion succeeds
- **WHEN** `delete_cookie_file_safe(data_dir)` is called and `.data/cookies.txt` exists
- **THEN** the file SHALL be deleted and the function SHALL return `True`

#### Scenario: File not present returns False
- **WHEN** `delete_cookie_file_safe(data_dir)` is called and `.data/cookies.txt` does not exist
- **THEN** the function SHALL return `False` without raising

#### Scenario: Path traversal attempt raises RuntimeError
- **WHEN** `delete_cookie_file_safe(data_dir)` is called with a `data_dir` where the resolved cookie path escapes the directory (e.g., via symlink or manipulation)
- **THEN** the function SHALL raise `RuntimeError` and NOT delete any file

#### Scenario: Wrong filename raises RuntimeError
- **WHEN** the target path's basename does not match `cookies.txt` exactly
- **THEN** the function SHALL raise `RuntimeError` and NOT delete any file

---

### Requirement: Factory reset deletes cookie file
`POST /factory-reset` SHALL call `delete_cookie_file_safe(data_dir)` after the database wipe. If the cookie file does not exist, this SHALL be silently ignored (the function returns `False` without error).

#### Scenario: Factory reset with cookie file present
- **WHEN** `POST /factory-reset` is called and `.data/cookies.txt` exists
- **THEN** the DB SHALL be wiped AND `.data/cookies.txt` SHALL be deleted, and the response SHALL be `204`

#### Scenario: Factory reset without cookie file
- **WHEN** `POST /factory-reset` is called and no cookie file exists
- **THEN** the DB SHALL be wiped and no error SHALL occur, and the response SHALL be `204`

---

### Requirement: CLI cookie-file upload command
The CLI SHALL expose `siphon config cookie-file <path>` as a special-case handler within the `config` subcommand. The CLI SHALL read the file at `<path>` from the local filesystem and POST its contents to `POST /settings/cookie-file` on the daemon. On success, the CLI SHALL print a confirmation message. On failure (validation error or daemon unreachable) it SHALL print the error and exit with a non-zero code.

#### Scenario: Valid file uploaded via CLI
- **WHEN** `siphon config cookie-file /path/to/cookies.txt` is run and the daemon accepts the file
- **THEN** the CLI SHALL print a success message and exit with code 0

#### Scenario: Invalid file rejected via CLI
- **WHEN** `siphon config cookie-file /path/to/not-a-cookie.txt` is run and the daemon returns 400
- **THEN** the CLI SHALL print the error detail and exit with a non-zero code
