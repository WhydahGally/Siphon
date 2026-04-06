## ADDED Requirements

### Requirement: PlaylistScheduler instantiation
A `PlaylistScheduler` class SHALL be instantiated by the daemon at startup. It
SHALL read all playlists with `watched=1` from the DB and arm one
`threading.Timer` per playlist. The class SHALL live in its own clearly labelled
section of `watcher.py`.

#### Scenario: Startup with watched playlists
- **WHEN** `PlaylistScheduler` is instantiated and at least one playlist has
  `watched=1`
- **THEN** one `threading.Timer` SHALL be armed per watched playlist, set to fire
  after the playlist's effective interval (see interval resolution requirement)

#### Scenario: Startup with no watched playlists
- **WHEN** `PlaylistScheduler` is instantiated and no playlists have `watched=1`
- **THEN** no timers SHALL be armed; the scheduler SHALL start idle with no error

---

### Requirement: Interval resolution
Each playlist's effective check interval SHALL be determined by the following
precedence chain:

1. `playlists.check_interval_secs` (per-playlist override, if NOT NULL)
2. `settings["check-interval"]` (global default, if set)
3. Hardcoded fallback: `86400` seconds (24 hours)

#### Scenario: Per-playlist interval set
- **WHEN** a playlist has `check_interval_secs = 3600`
- **THEN** its timer SHALL fire every 3600 seconds regardless of the global
  `check-interval` setting

#### Scenario: Per-playlist interval NULL, global set
- **WHEN** a playlist has `check_interval_secs = NULL` and `settings["check-interval"] = "7200"`
- **THEN** its timer SHALL use 7200 seconds

#### Scenario: Neither per-playlist nor global set
- **WHEN** a playlist has `check_interval_secs = NULL` and no `check-interval` setting exists
- **THEN** its timer SHALL use the hardcoded fallback of 86400 seconds

---

### Requirement: Fire-sync-rearm lifecycle
Each timer SHALL follow a fire-sync-rearm lifecycle. The timer is one-shot: it
fires, runs one sync for its playlist, then arms a new timer for the next cycle.
Concurrent syncs for the same playlist SHALL NOT occur.

#### Scenario: Timer fires — sync runs
- **WHEN** a playlist's timer fires
- **THEN** `_sync_parallel` SHALL be called for that playlist synchronously within
  the timer's thread; the timer thread SHALL not return until the sync completes

#### Scenario: Rearm after successful sync
- **WHEN** a sync completes (success or partial failure)
- **THEN** a new `threading.Timer` SHALL be armed immediately with the playlist's
  effective interval (re-read from DB at rearm time)

#### Scenario: Rearm after failed sync
- **WHEN** `_sync_parallel` raises an unhandled exception
- **THEN** the error SHALL be logged, and a new timer SHALL still be armed so the
  playlist is retried at the next interval

#### Scenario: Interval changed between fire and rearm
- **WHEN** `check_interval_secs` or the global `check-interval` is updated in the
  DB while a sync is in progress
- **THEN** the new interval SHALL be picked up at rearm time (DB is re-read per
  rearm); no restart or notification is needed for this case

---

### Requirement: add_playlist method
`PlaylistScheduler.add_playlist(playlist_id)` SHALL arm a new timer for a newly
registered playlist without restarting the scheduler.

#### Scenario: New playlist added while daemon running
- **WHEN** `add_playlist(playlist_id)` is called on the running scheduler
- **THEN** a new timer SHALL be armed for that playlist using its effective
  interval; the existing timers for other playlists SHALL be unaffected

#### Scenario: add_playlist called for playlist with watched=0
- **WHEN** `add_playlist(playlist_id)` is called for a playlist that has
  `watched=0` in the DB
- **THEN** no timer SHALL be armed and the call SHALL be a no-op

---

### Requirement: remove_playlist method
`PlaylistScheduler.remove_playlist(playlist_id)` SHALL cancel the timer for a
playlist being deleted.

#### Scenario: Remove an actively watched playlist
- **WHEN** `remove_playlist(playlist_id)` is called for a playlist with an active timer
- **THEN** the timer SHALL be cancelled; if a sync is currently in progress for
  that playlist it SHALL be allowed to complete

#### Scenario: Remove a playlist not in the scheduler
- **WHEN** `remove_playlist(playlist_id)` is called for a playlist with no active
  timer (e.g. `watched=0`)
- **THEN** the call SHALL be a no-op with no error

---

### Requirement: reschedule_playlist method
`PlaylistScheduler.reschedule_playlist(playlist_id)` SHALL cancel any existing
timer for the playlist and arm a new one with the current effective interval.
Used when `PATCH /playlists/{id}` updates the interval or watched flag.

#### Scenario: Reschedule with new interval
- **WHEN** `reschedule_playlist(playlist_id)` is called after the DB has been
  updated with a new `check_interval_secs`
- **THEN** the old timer SHALL be cancelled and a new timer SHALL be armed with
  the updated interval

#### Scenario: Reschedule to watched=0
- **WHEN** `reschedule_playlist(playlist_id)` is called and the playlist now has
  `watched=0` in the DB
- **THEN** the existing timer SHALL be cancelled and no new timer SHALL be armed

---

### Requirement: stop method
`PlaylistScheduler.stop()` SHALL cancel all pending timers and wait for any
in-progress sync threads to complete before returning. Called by the daemon's
shutdown lifecycle.

#### Scenario: Stop with no active syncs
- **WHEN** `stop()` is called and no sync is currently running
- **THEN** all pending timers SHALL be cancelled and `stop()` SHALL return
  immediately

#### Scenario: Stop during active sync
- **WHEN** `stop()` is called while a sync is running in a timer thread
- **THEN** `stop()` SHALL block until the sync thread completes, then return
