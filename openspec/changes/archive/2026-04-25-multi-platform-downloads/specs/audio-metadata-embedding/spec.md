## MODIFIED Requirements

### Requirement: Audio downloads embed metadata tags
When an audio file is downloaded (mp3 or opus), the system SHALL embed all available metadata fields (title, artist, track, uploader, album, etc.) as native tags in the output file. For mp3, tags SHALL be written as ID3v2 frames. For opus, tags SHALL be written as Vorbis comment headers. This applies to any yt-dlp-supported platform, not only YouTube.

#### Scenario: mp3 download contains title tag
- **WHEN** a video is downloaded in mp3 format
- **THEN** the resulting mp3 file SHALL have its `title` ID3 tag set to the video title

#### Scenario: mp3 music video contains artist and track tags
- **WHEN** a music video with embedded `artist` and `track` metadata is downloaded in mp3 format
- **THEN** the resulting mp3 file SHALL have its `artist` ID3 tag set to the artist name and its `title` ID3 tag set to the track name

#### Scenario: opus download contains title tag
- **WHEN** a video is downloaded in opus format
- **THEN** the resulting opus file SHALL have its `TITLE` Vorbis comment set to the video title

---

### Requirement: Audio downloads embed thumbnail as cover art
When an audio file is downloaded (mp3 or opus), the system SHALL embed the video thumbnail as cover art in the output file. For mp3, the cover SHALL be stored as an ID3 `APIC` frame. For opus, the cover SHALL be stored as a `METADATA_BLOCK_PICTURE` Vorbis comment. This applies to any yt-dlp-supported platform.

#### Scenario: mp3 download has embedded cover art
- **WHEN** a video is downloaded in mp3 format and a thumbnail is available
- **THEN** the resulting mp3 file SHALL contain an embedded cover image readable by standard audio players

#### Scenario: opus download has embedded cover art
- **WHEN** a video is downloaded in opus format and a thumbnail is available
- **THEN** the resulting opus file SHALL contain an embedded cover image readable by standard audio players

#### Scenario: no thumbnail available
- **WHEN** a video has no available thumbnail at download time
- **THEN** the download SHALL complete successfully without cover art and SHALL NOT produce an error
