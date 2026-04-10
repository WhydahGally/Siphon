## ADDED Requirements

### Requirement: Audio downloads embed metadata tags
When an audio file is downloaded (mp3 or opus), the system SHALL embed all available YouTube metadata fields (title, artist, track, uploader, album, etc.) as native tags in the output file. For mp3, tags SHALL be written as ID3v2 frames. For opus, tags SHALL be written as Vorbis comment headers.

#### Scenario: mp3 download contains title tag
- **WHEN** a YouTube video is downloaded in mp3 format
- **THEN** the resulting mp3 file SHALL have its `title` ID3 tag set to the video title

#### Scenario: mp3 music video contains artist and track tags
- **WHEN** a YouTube Music catalog video is downloaded in mp3 format
- **THEN** the resulting mp3 file SHALL have its `artist` ID3 tag set to the artist name and its `title` ID3 tag set to the track name

#### Scenario: opus download contains title tag
- **WHEN** a YouTube video is downloaded in opus format
- **THEN** the resulting opus file SHALL have its `TITLE` Vorbis comment set to the video title

### Requirement: Audio downloads embed thumbnail as cover art
When an audio file is downloaded (mp3 or opus), the system SHALL embed the video thumbnail as cover art in the output file. For mp3, the cover SHALL be stored as an ID3 `APIC` frame. For opus, the cover SHALL be stored as a `METADATA_BLOCK_PICTURE` Vorbis comment.

#### Scenario: mp3 download has embedded cover art
- **WHEN** a YouTube video is downloaded in mp3 format and a thumbnail is available
- **THEN** the resulting mp3 file SHALL contain an embedded cover image readable by standard audio players

#### Scenario: opus download has embedded cover art
- **WHEN** a YouTube video is downloaded in opus format and a thumbnail is available
- **THEN** the resulting opus file SHALL contain an embedded cover image readable by standard audio players

#### Scenario: no thumbnail available
- **WHEN** a YouTube video has no available thumbnail at download time
- **THEN** the download SHALL complete successfully without cover art and SHALL NOT produce an error

### Requirement: No stray thumbnail files after download
After an audio download completes, the system SHALL NOT leave any thumbnail image files (`.webp`, `.jpg`, `.jpeg`, `.png`) on disk alongside the downloaded audio file.

#### Scenario: Thumbnail cleaned up after embedding
- **WHEN** an audio download completes and a thumbnail was fetched for embedding
- **THEN** the output directory SHALL contain only the audio file and no image files from the download session

### Requirement: Metadata embedding applies to both single video and playlist downloads
The metadata and cover art embedding behaviour SHALL apply regardless of whether the source URL is a single video or a playlist.

#### Scenario: Playlist audio download has metadata
- **WHEN** a playlist is downloaded in audio mode
- **THEN** every downloaded audio file in the playlist SHALL have metadata tags and cover art embedded

#### Scenario: Single video audio download has metadata
- **WHEN** a single video URL is downloaded in audio mode
- **THEN** the downloaded audio file SHALL have metadata tags and cover art embedded

### Requirement: Video downloads are unaffected
The metadata and cover art embedding changes SHALL apply only to audio mode downloads. Video mode downloads (mp4, mkv, webm) SHALL behave exactly as before.

#### Scenario: Video download is not changed
- **WHEN** a video is downloaded in video mode (any quality or container)
- **THEN** the download behaviour, output files, and directory contents SHALL be identical to before this change
