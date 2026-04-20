"""
siphon.job_store — Thread-safe in-memory store for download jobs.
"""
import asyncio
import threading
import time
import uuid
from typing import Dict, List, Optional

from siphon.models import DownloadJob, JobItem


class JobStore:
    """
    Thread-safe in-memory store for DownloadJob instances.

    Download worker threads mutate job state via update_item_state().
    SSE subscribers (async) receive events via asyncio.Queue per job.
    The event loop reference (set at startup) bridges the two worlds.
    """

    _MAX_JOBS = 50

    def __init__(self) -> None:
        self._jobs: Dict[str, DownloadJob] = {}
        self._queues: Dict[str, List["asyncio.Queue[Optional[dict]]"]] = {}
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def create_job(
        self,
        playlist_id: Optional[str],
        playlist_name: Optional[str],
        entries: List[dict],
        output_dir: Optional[str] = None,
        auto_rename: bool = False,
    ) -> str:
        job_id = str(uuid.uuid4())
        items = [
            JobItem(video_id=e["id"], yt_title=e["title"], url=e["url"], state="pending")
            for e in entries
        ]
        job = DownloadJob(
            job_id=job_id,
            playlist_id=playlist_id,
            playlist_name=playlist_name,
            items=items,
            created_at=time.time(),
            output_dir=output_dir,
            auto_rename=auto_rename,
        )
        with self._lock:
            # Atomic guard: reject if an active (non-terminal) job already exists
            # for this playlist. Checked under the lock so concurrent requests
            # can't both slip through before either job is created.
            if playlist_id is not None:
                for existing in self._jobs.values():
                    if existing.playlist_id == playlist_id and not existing.is_terminal():
                        raise ValueError("active_job_exists")
            self._evict_if_needed()
            self._jobs[job_id] = job
            self._queues[job_id] = []
        return job_id

    def _evict_if_needed(self) -> None:
        """Evict oldest terminal job if at capacity. Must be called under self._lock."""
        if len(self._jobs) < self._MAX_JOBS:
            return
        terminal = [(jid, j) for jid, j in self._jobs.items() if j.is_terminal()]
        if not terminal:
            return
        oldest_id = min(terminal, key=lambda t: t[1].created_at)[0]
        del self._jobs[oldest_id]
        self._queues.pop(oldest_id, None)

    def cancel_all_jobs(self) -> int:
        """Mark all pending items in non-terminal playlist jobs as cancelled.

        Items already downloading are not interrupted — they drain to completion.
        Single-video jobs (playlist_id is None) are not affected.
        Returns the count of items transitioned to cancelled.
        """
        events: List[tuple] = []
        notify_ids: List[str] = []
        with self._lock:
            for job in self._jobs.values():
                if job.is_terminal():
                    continue
                if job.playlist_id is None:
                    continue
                job.cancelled = True
                for item in job.items:
                    if item.state == "pending":
                        item.state = "cancelled"
                        events.append((job.job_id, {
                            "job_id": job.job_id,
                            "video_id": item.video_id,
                            "state": "cancelled",
                            "yt_title": item.yt_title,
                            "renamed_to": item.renamed_to,
                            "rename_tier": item.rename_tier,
                            "error": item.error,
                        }))
                if job.is_terminal():
                    notify_ids.append(job.job_id)
        for job_id, event in events:
            self._notify(job_id, event)
        for job_id in notify_ids:
            self.notify_terminal(job_id)
        return len(events)

    def clear_done_items(self, job_id: str, clear_all: bool = False) -> int:
        """Remove terminal items from a job's items list.

        When clear_all is False, only 'done' items are removed (failed/cancelled
        are kept so the user can retry them). When clear_all is True, all terminal
        items (done, failed, cancelled) are removed.

        If the job becomes empty, it is deleted from the store and any
        lingering SSE connections are closed via notify_terminal.
        Returns the count of items removed.
        """
        terminal_states = {"done", "failed", "cancelled"} if clear_all else {"done"}
        delete_job = False
        removed = 0
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return 0
            before = len(job.items)
            job.items = [i for i in job.items if i.state not in terminal_states]
            removed = before - len(job.items)
            if removed and not job.items:
                delete_job = True
        if delete_job:
            self.notify_terminal(job_id)  # close any lingering SSE connections
            with self._lock:
                self._jobs.pop(job_id, None)
                self._queues.pop(job_id, None)
        return removed

    def get_job(self, job_id: str) -> Optional[DownloadJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[DownloadJob]:
        with self._lock:
            return sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)

    def delete_job(self, job_id: str) -> bool:
        """Remove job. Raises ValueError if job has in-progress items."""
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if not job.is_terminal():
                raise ValueError("Job has in-progress items")
            del self._jobs[job_id]
            self._queues.pop(job_id, None)
            return True

    def update_item_state(
        self,
        job_id: str,
        video_id: str,
        state: str,
        *,
        renamed_to: Optional[str] = None,
        rename_tier: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        event: Optional[dict] = None
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            for item in job.items:
                if item.video_id == video_id:
                    item.state = state
                    if state == "downloading":
                        item.started_at = time.time()
                    elif state in ("done", "failed"):
                        item.finished_at = time.time()
                    if renamed_to is not None:
                        item.renamed_to = renamed_to
                    if rename_tier is not None:
                        item.rename_tier = rename_tier
                    if error is not None:
                        item.error = error
                    event = {
                        "job_id": job_id,
                        "video_id": video_id,
                        "state": state,
                        "yt_title": item.yt_title,
                        "renamed_to": item.renamed_to,
                        "rename_tier": item.rename_tier,
                        "error": item.error,
                    }
                    break
        if event is not None:
            self._notify(job_id, event)

    def notify_terminal(self, job_id: str) -> None:
        """Push sentinel None to signal all SSE subscribers that the job is done."""
        self._notify(job_id, None)

    def subscribe(self, job_id: str) -> "asyncio.Queue[Optional[dict]]":
        q: asyncio.Queue = asyncio.Queue()
        with self._lock:
            if job_id in self._queues:
                self._queues[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: "asyncio.Queue") -> None:
        with self._lock:
            if job_id in self._queues:
                try:
                    self._queues[job_id].remove(q)
                except ValueError:
                    pass

    def reset_failed_items(self, job_id: str) -> List[dict]:
        """Reset all failed and cancelled items to pending. Returns entries list for re-dispatch."""
        entries: List[dict] = []
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return entries
            for item in job.items:
                if item.state in ("failed", "cancelled"):
                    item.state = "pending"
                    item.error = None
                    item.started_at = None
                    item.finished_at = None
                    entries.append({"id": item.video_id, "url": item.url, "title": item.yt_title})
            if entries:
                job.cancelled = False
        return entries

    def publish_progress(self, job_id: str, data: dict) -> None:
        """Broadcast an ephemeral progress event to SSE subscribers (no state mutation)."""
        self._notify(job_id, {"_type": "progress", **data})

    def _notify(self, job_id: str, event: Optional[dict]) -> None:
        if self._loop is None:
            return
        with self._lock:
            queues = list(self._queues.get(job_id, []))
        for q in queues:
            asyncio.run_coroutine_threadsafe(q.put(event), self._loop)
