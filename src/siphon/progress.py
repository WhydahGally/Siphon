from typing import Optional, TypedDict


class ProgressEvent(TypedDict):
    """
    Normalised progress event emitted to callers during a download.

    All fields are always present. Optional fields are None when unavailable.
    """

    status: str  # "downloading" | "finished" | "error"
    filename: str  # local file path being written
    downloaded_bytes: Optional[int]  # bytes downloaded so far
    total_bytes: Optional[int]  # total expected bytes (None if unknown)
    speed: Optional[float]  # bytes/sec (None if unknown)
    eta: Optional[int]  # estimated seconds remaining (None if unknown)


def make_progress_event(d: dict) -> ProgressEvent:
    """
    Map a raw yt-dlp progress hook dict to a normalised ProgressEvent.

    yt-dlp passes a dict with keys like 'status', 'filename', 'downloaded_bytes',
    'total_bytes', 'total_bytes_estimate', 'speed', 'eta'. Fields may be absent
    or None depending on the download stage and stream type.
    """
    status = d.get("status", "downloading")

    # yt-dlp may provide either total_bytes or total_bytes_estimate.
    total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")

    return ProgressEvent(
        status=status,
        filename=d.get("filename", ""),
        downloaded_bytes=d.get("downloaded_bytes"),
        total_bytes=total_bytes,
        speed=d.get("speed"),
        eta=d.get("eta"),
    )
