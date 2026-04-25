"""
siphon.models — Pure data types used across the Siphon package.

Dataclasses for internal state and Pydantic models for API requests.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Internal data types
# ---------------------------------------------------------------------------

@dataclass
class FailureRecord:
    video_id: str
    title: str
    url: str
    error_message: str


@dataclass
class ItemRecord:
    video_id: str
    playlist_id: Optional[str]
    title: str
    renamed_to: Optional[str]       # final filename stem, no extension
    rename_tier: Optional[str]      # tier from RenameResult
    uploader: Optional[str]
    channel_url: Optional[str]
    duration_secs: Optional[int]


@dataclass
class JobItem:
    video_id: str
    title: str
    url: str
    state: str  # "pending" | "downloading" | "done" | "failed"
    renamed_to: Optional[str] = None
    rename_tier: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class DownloadJob:
    job_id: str
    playlist_id: Optional[str]    # None for single-video jobs
    playlist_name: Optional[str]
    items: List[JobItem]
    created_at: float
    output_dir: Optional[str] = None
    auto_rename: bool = False
    cancelled: bool = False
    original_total: int = field(default=0, init=False)

    def __post_init__(self):
        self.original_total = len(self.items)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.state == "done")

    @property
    def failed_count(self) -> int:
        return sum(1 for i in self.items if i.state == "failed")

    def is_terminal(self) -> bool:
        return bool(self.items) and all(i.state in ("done", "failed", "cancelled") for i in self.items)


# ---------------------------------------------------------------------------
# Pydantic request models (API)
# ---------------------------------------------------------------------------

class PlaylistCreate(BaseModel):
    url: str
    format: str = "mp3"
    quality: str = "best"
    output_dir: Optional[str] = None
    auto_rename: bool = False
    watched: bool = True
    check_interval_secs: Optional[int] = None
    download: bool = False


class PlaylistPatch(BaseModel):
    watched: Optional[bool] = None
    check_interval_secs: Optional[int] = None
    auto_rename: Optional[bool] = None


class SettingWrite(BaseModel):
    value: str


class JobCreate(BaseModel):
    url: str
    format: str = "mp3"
    quality: str = "best"
    output_dir: Optional[str] = None
    auto_rename: bool = False
    watched: bool = True
    check_interval_secs: Optional[int] = None


class RenameRequest(BaseModel):
    new_name: str
