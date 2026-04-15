## ADDED Requirements

### Requirement: siphon playlist-items CLI command
The `siphon playlist-items <name>` subcommand SHALL retrieve and print all downloaded items for the named playlist via `GET /playlists/{id}/items` through the daemon. Each item SHALL be printed on its own line. If `renamed_to` is set, the line SHALL read `<yt_title> → <renamed_to>`. Otherwise it SHALL read the `yt_title` alone. A header line SHALL show the playlist name and total item count before the list.

#### Scenario: Playlist exists with items
- **WHEN** `siphon playlist-items "My Playlist"` is called and the playlist has items
- **THEN** the command SHALL print a header line with the playlist name and count, followed by one line per item

#### Scenario: Playlist exists with no items
- **WHEN** `siphon playlist-items "My Playlist"` is called and the playlist has no items
- **THEN** the command SHALL print a message such as "No items downloaded yet for 'My Playlist'."

#### Scenario: Playlist not found
- **WHEN** `siphon playlist-items "Unknown"` is called and no playlist with that name is registered
- **THEN** the command SHALL print an error message and exit with code 1

#### Scenario: Daemon not running
- **WHEN** `siphon playlist-items <name>` is called but the daemon is not running
- **THEN** the command SHALL print an error indicating the daemon is not reachable and exit with code 1
