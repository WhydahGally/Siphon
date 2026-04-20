"""
siphon.scheduler — PlaylistScheduler: one timer per watched playlist.

Lifecycle: fire → sync → rearm (sequential; no concurrent syncs per playlist).
Interval is re-read from the DB at each rearm, so config changes take effect
on the next cycle without any restart.
"""
import logging
import threading
from typing import Any, Callable, Dict

from siphon import registry

logger = logging.getLogger(__name__)

_DEFAULT_INTERVAL = 86400  # 24 hours


class PlaylistScheduler:
    """
    Manages one threading.Timer per watched playlist.

    Thread-safety: all mutations to _timers and _active_threads are protected
    by _lock.

    Parameters
    ----------
    sync_fn : callable
        ``sync_fn(row)`` is called when a playlist timer fires.
        The daemon wires this to sync_parallel with the right callbacks.
    """

    def __init__(self, sync_fn: Callable) -> None:
        self._sync_fn = sync_fn
        self._timers: Dict[str, threading.Timer] = {}
        self._active_threads: Dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Arm timers for all currently watched playlists."""
        playlists = registry.get_watched_playlists()
        for row in playlists:
            self._arm(row["id"], self._resolve_interval(row))
        logger.info("PlaylistScheduler started — %d playlist(s) scheduled.", len(playlists))

    def stop(self) -> None:
        """Cancel all pending timers and wait for any in-progress syncs to complete."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            threads_to_join = list(self._active_threads.values())

        for t in threads_to_join:
            t.join()
        logger.info("PlaylistScheduler stopped.")

    def add_playlist(self, playlist_id: str) -> None:
        """Arm a new timer for a newly registered playlist (no-op if watched=0)."""
        row = registry.get_playlist_by_id(playlist_id)
        if row is None or not row["watched"]:
            return
        interval = self._resolve_interval(row)
        self._arm(playlist_id, interval)
        logger.info(
            "PlaylistScheduler: watching '%s' — next sync in %s.",
            row["name"], self._fmt_interval(interval),
        )

    def remove_playlist(self, playlist_id: str) -> None:
        """Cancel the timer for a playlist being deleted (no-op if not present)."""
        with self._lock:
            timer = self._timers.pop(playlist_id, None)
        if timer is not None:
            timer.cancel()
            logger.debug("PlaylistScheduler: cancelled timer for deleted playlist %s.", playlist_id)

    def reschedule_playlist(self, playlist_id: str) -> None:
        """
        Cancel existing timer and re-arm with the current DB interval.
        If watched=0, cancel only (no re-arm).
        """
        with self._lock:
            old = self._timers.pop(playlist_id, None)
        if old is not None:
            old.cancel()

        row = registry.get_playlist_by_id(playlist_id)
        if row is None or not row["watched"]:
            logger.debug("PlaylistScheduler: playlist %s is unwatched — timer cancelled.", playlist_id)
            return

        interval = self._resolve_interval(row)
        self._arm(playlist_id, interval)
        logger.info(
            "PlaylistScheduler: '%s' rescheduled — next sync in %s.",
            row["name"], self._fmt_interval(interval),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_interval(seconds: int) -> str:
        """Return a human-readable interval string (e.g. '24h', '90m', '45s')."""
        if seconds >= 3600:
            hours = seconds / 3600
            return f"{hours:.4g}h"
        if seconds >= 60:
            minutes = seconds / 60
            return f"{minutes:.4g}m"
        return f"{seconds}s"

    def _resolve_interval(self, row: Any) -> int:
        """Return the effective check interval for a playlist row."""
        if row["check_interval_secs"] is not None:
            return int(row["check_interval_secs"])
        global_val = registry.get_setting("check_interval")
        if global_val is not None:
            try:
                return int(global_val)
            except ValueError:
                pass
        return _DEFAULT_INTERVAL

    def _arm(self, playlist_id: str, interval: int) -> None:
        """Create and start a one-shot timer for playlist_id."""
        timer = threading.Timer(interval, self._fire, args=(playlist_id,))
        timer.daemon = True
        timer.start()
        with self._lock:
            self._timers[playlist_id] = timer

    def _fire(self, playlist_id: str) -> None:
        """Called when a playlist's timer fires. Runs sync then rearms."""
        row = registry.get_playlist_by_id(playlist_id)
        if row is None:
            logger.warning("PlaylistScheduler._fire: playlist %s not found in DB, skipping.", playlist_id)
            return

        # Track active thread so stop() can join it.
        current = threading.current_thread()
        with self._lock:
            self._active_threads[playlist_id] = current

        try:
            logger.info("PlaylistScheduler: firing sync for '%s'.", row["name"])
            self._sync_fn(row)
        except Exception as exc:
            logger.error("PlaylistScheduler: sync failed for '%s': %s", row["name"], exc)
        finally:
            with self._lock:
                self._active_threads.pop(playlist_id, None)

        self._rearm(playlist_id)

    def _rearm(self, playlist_id: str) -> None:
        """Re-read interval from DB and arm a new timer."""
        row = registry.get_playlist_by_id(playlist_id)
        if row is None or not row["watched"]:
            return
        interval = self._resolve_interval(row)
        self._arm(playlist_id, interval)
        logger.debug("PlaylistScheduler: rearmed '%s' — next sync in %ds.", row["name"], interval)
