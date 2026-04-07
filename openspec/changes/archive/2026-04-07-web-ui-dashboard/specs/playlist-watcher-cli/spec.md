## REMOVED Requirements

### Requirement: `siphon add` rejects single-video URLs
**Reason**: The restriction was an incorrect early guard added at the CLI/API layer. The `download()` engine has always supported both playlist and single-video URLs. The web UI requires single-video support. The guard is removed to align the API surface with the actual engine capability.
**Migration**: No migration required. Callers that were passing single-video URLs and receiving a 400 error will now receive a successful response. No existing valid behaviour changes.
