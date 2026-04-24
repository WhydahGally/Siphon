# E2E Test Gaps

Known gaps in the e2e test suite that require additional infrastructure or test playlists to implement.

## Private/unavailable video handling

**Endpoints:** `POST /playlists/{id}/sync`, `POST /jobs`

A playlist containing a mix of public and private/unavailable videos should be synced. The test should verify:

- The job reaches terminal state (does not hang or crash).
- Unavailable items land in `state: "failed"` with a descriptive error message.
- Other items in the same job still reach `state: "done"`.
- The playlist item count reflects both failed and done items.

**Blocker:** Requires a dedicated test playlist that permanently contains at least one private or unavailable video. This playlist URL would need to be added as a new secret (`E2E_MIXED_PLAYLIST_URL`).

## Retry failed items (job-level)

**Endpoint:** `POST /jobs/{job_id}/retry-failed`

After a job completes with some items in `state: "failed"`, calling retry-failed should reset those items to `pending` and re-download them. The test should verify:

- Failed items are reset to `pending`.
- The download is retried and items reach `done` (if the failure was transient) or `failed` again.
- Already-done items are not affected.

**How it differs from sync-failed:** `retry-failed` operates on a specific job in the job store (in-memory) and resets individual failed items within that job. `sync-failed` (`POST /playlists/{id}/sync-failed`) operates on a playlist in the registry (persistent DB) and re-downloads all items that have `state: "failed"` in the playlist's item history, creating a new job.

**Blocker:** Same as above — requires a reliable way to produce failed items (private/unavailable video in a test playlist).

## Sync-failed (playlist-level)

**Endpoint:** `POST /playlists/{id}/sync-failed`

After a playlist sync leaves some items failed in the registry, calling sync-failed should create a new job to retry only those items. Same blocker as above.

## Format selection

**Endpoint:** `POST /jobs`

Every existing test uses `format: "mp3"`. There is no test that downloads as `opus`, `mp4`, `mkv`, or `webm` and verifies:

- The file on disk has the correct extension.
- The file is playable/readable by mutagen (audio) or has valid container headers (video).
- The format field in the job response matches what was requested.

**Blocker:** None — can be implemented with the existing single video URL. Adds download time per format tested. Consider testing one audio alternative (`opus`) and one video format (`mp4`) to keep runtime reasonable.

## Invalid URL handling

**Endpoint:** `POST /jobs`, `POST /playlists`

No test submits a completely invalid or non-YouTube URL to verify the API returns an appropriate error (400/422) rather than crashing or hanging.

**Blocker:** None.
