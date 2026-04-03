# Parallelism & Concurrency Notes

## Current decision: ThreadPoolExecutor

Parallel downloads within a playlist use `concurrent.futures.ThreadPoolExecutor`.
Chosen for simplicity and because download work is I/O-bound (network + yt-dlp + ffmpeg subprocess).
The GIL is not a meaningful bottleneck here.

## Future migration path: ProcessPoolExecutor (or explicit multiprocessing)

Switch from threads to processes when:

- **Individual download cancellation from the UI is needed.** Killing a thread from outside is not
  safe in Python. Killing a process (SIGTERM → process group takes ffmpeg with it) is clean.
- **True crash isolation is needed.** A yt-dlp crash in a thread can corrupt shared state.
  In a process, it dies cleanly and the main process continues.

The migration is intentionally low-cost if the worker function is kept pure:
`_download_one(entry, options, ...) -> DownloadResult` must not touch shared
mutable state. If that contract holds, swapping `ThreadPoolExecutor` for
`ProcessPoolExecutor` is a one-line change.

**Note for Linux containers**: process fork cost is low on Linux (copy-on-write),
so the overhead concern that applies to macOS does not apply in production.

## meTube reference

meTube (https://github.com/alexta69/metube) uses `multiprocessing.Process` per download,
gated by `asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)`. Each process runs inside an
asyncio event loop (the server). Status updates are passed back via a
`multiprocessing.Manager().Queue()`.

Siphon's long-running server design should converge toward this pattern when the UI
layer is ready, particularly for: per-item cancellation, per-item status visible in UI,
and clean process teardown on container stop.
