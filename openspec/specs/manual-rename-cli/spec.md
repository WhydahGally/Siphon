## ADDED Requirements

### Requirement: siphon rename-item CLI command
The CLI SHALL expose `siphon rename-item <playlist> <current-name> <new-name>` which renames a downloaded item within the specified playlist. The command SHALL resolve the playlist by name, find the item by matching `<current-name>` against `renamed_to` (or `yt_title` if `renamed_to` is NULL), and call `PUT /playlists/{playlist_id}/items/{video_id}/rename` on the daemon. On success, the command SHALL print the old and new names and exit with code 0.

#### Scenario: Successful rename
- **WHEN** `siphon rename-item "Workout" "Artist - Track" "My Custom Name"` is called and the item exists
- **THEN** the command SHALL call the daemon's rename endpoint, print `Renamed: "Artist - Track" → "My Custom Name"`, and exit with code 0

#### Scenario: Playlist not found
- **WHEN** `siphon rename-item "NonExistent" "name" "new"` is called and no playlist with that name is registered
- **THEN** the command SHALL print an error and exit with code 1

#### Scenario: Item not found in playlist
- **WHEN** `siphon rename-item "Workout" "No Such Item" "new"` is called and no item matches the current name
- **THEN** the command SHALL print an error indicating the item was not found and exit with code 1

#### Scenario: Daemon not running
- **WHEN** `siphon rename-item` is called but the daemon is not reachable
- **THEN** the command SHALL print an error indicating the daemon is not running and exit with code 1

#### Scenario: File not found on disk (daemon returns 404)
- **WHEN** the daemon returns 404 because the file is missing from disk
- **THEN** the command SHALL print the error message from the daemon and exit with code 1

#### Scenario: Name collision (daemon returns 409)
- **WHEN** the daemon returns 409 because a file with the target name already exists
- **THEN** the command SHALL print the error message from the daemon and exit with code 1
