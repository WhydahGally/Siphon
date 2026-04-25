import shutil
from dataclasses import dataclass
from typing import Optional

# Supported video resolutions. "best" means no height constraint.
VALID_RESOLUTIONS = {"best", "2160", "1080", "720", "480", "360"}

# Supported video container formats.
VALID_VIDEO_FORMATS = {"mp4", "mkv", "webm"}

# Supported audio formats.
VALID_AUDIO_FORMATS = {"mp3", "opus"}


def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available on the system PATH."""
    return shutil.which("ffmpeg") is not None


@dataclass
class DownloadOptions:
    """
    Encapsulates all format/quality options for a download job.

    For video mode, set `quality` to one of: "best", "2160", "1080", "720", "480", "360".
    For audio mode, set `audio_format` to one of: "mp3", "opus".
    """

    mode: str  # "video" or "audio"
    quality: Optional[str] = None  # used when mode == "video"
    video_format: Optional[str] = None  # container format when mode == "video"
    audio_format: Optional[str] = None  # used when mode == "audio"
    sponsorblock_categories: Optional[list] = None  # yt-dlp sponsorblock_remove list

    def __post_init__(self):
        if self.mode == "video":
            if self.quality is None:
                self.quality = "best"
            if self.quality not in VALID_RESOLUTIONS:
                raise ValueError(
                    f"Invalid quality '{self.quality}'. "
                    f"Must be one of: {', '.join(sorted(VALID_RESOLUTIONS))}"
                )
            if self.video_format is None:
                self.video_format = "mp4"
            if self.video_format not in VALID_VIDEO_FORMATS:
                raise ValueError(
                    f"Invalid video format '{self.video_format}'. "
                    f"Must be one of: {', '.join(sorted(VALID_VIDEO_FORMATS))}"
                )
        elif self.mode == "audio":
            if self.audio_format is None:
                raise ValueError("audio_format must be set when mode is 'audio'.")
            if self.audio_format not in VALID_AUDIO_FORMATS:
                raise ValueError(
                    f"Invalid audio format '{self.audio_format}'. "
                    f"Must be one of: {', '.join(sorted(VALID_AUDIO_FORMATS))}"
                )
        else:
            raise ValueError(f"Invalid mode '{self.mode}'. Must be 'video' or 'audio'.")


def build_video_format_selector(quality: str) -> str:
    """
    Map a quality value to a yt-dlp format selector string.

    Falls back to best available if the requested height is not found.
    """
    if quality == "best":
        return "bestvideo+bestaudio/best"
    return (
        f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
        "/bestvideo+bestaudio/best"
    )


def build_audio_postprocessors(audio_format: str) -> list:
    """
    Return the yt-dlp postprocessors list for the given audio format.

    - opus:  remux to opus, no transcode.
    - mp3:   transcode with audio-quality 0 (VBR best, caps at source bitrate, no upsampling).
    """
    if audio_format == "opus":
        return [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
            },
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ]
    if audio_format == "mp3":
        return [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",  # VBR best — yt-dlp will not upsample
            },
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail"},
        ]
    # Unreachable if DownloadOptions validation is used, but guard anyway.
    raise ValueError(f"Unsupported audio format: {audio_format}")


def build_options(fmt: str, quality: str = "best") -> DownloadOptions:
    """Build a DownloadOptions from a format string and quality."""
    if fmt in VALID_AUDIO_FORMATS:
        return DownloadOptions(mode="audio", audio_format=fmt)
    return DownloadOptions(mode="video", quality=quality, video_format=fmt)
