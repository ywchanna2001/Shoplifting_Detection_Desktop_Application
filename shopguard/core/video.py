"""Reading video files and formatting times and sizes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

FALLBACK_FPS = 25.0  # some DVR exports report a missing or nonsensical frame rate


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    fps: float
    frame_count: int
    width: int
    height: int
    file_size: int

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def duration(self) -> float:
        return self.frame_count / self.fps if self.fps > 0 else 0.0

    @property
    def resolution(self) -> str:
        return f"{self.width} × {self.height}"


def probe_video(path: str | Path) -> VideoInfo:
    """Read basic information about a video. Raises ValueError if it can't be opened."""
    path = Path(path)
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(
                f"Could not open '{path.name}'. The file may be damaged or use an unsupported format."
            )
        fps = capture.get(cv2.CAP_PROP_FPS) or 0.0
        if not 1 <= fps <= 240:
            fps = FALLBACK_FPS
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if frame_count <= 0:
            raise ValueError(f"'{path.name}' does not contain any readable video frames.")
        return VideoInfo(
            path=path,
            fps=fps,
            frame_count=frame_count,
            width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            file_size=path.stat().st_size,
        )
    finally:
        capture.release()


def read_frame_at(path: str | Path, seconds: float) -> np.ndarray | None:
    """Return the BGR frame at the given time, or None if it can't be read."""
    capture = cv2.VideoCapture(str(path))
    try:
        capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, seconds) * 1000)
        ok, frame = capture.read()
        return frame if ok else None
    finally:
        capture.release()


def format_timestamp(seconds: float) -> str:
    """12.5 -> '00:12', 3725 -> '1:02:05'."""
    seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def format_duration(seconds: float) -> str:
    """Human-friendly length: '45 s', '3 min 20 s', '1 h 05 min'."""
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds} s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} min {secs:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def format_file_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
