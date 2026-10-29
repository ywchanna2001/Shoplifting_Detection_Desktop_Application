"""Saving incident video clips."""

from __future__ import annotations

from pathlib import Path

import cv2

from shopguard.core.common import (
    CancelCheck,
    OperationCancelled,
    ProgressCallback,
    ignore_progress,
    never_cancelled,
)
from shopguard.core.incidents import Incident
from shopguard.core.video import probe_video


def clip_filename(video_path: str | Path, incident: Incident) -> str:
    """e.g. 'cam1_incident02_00-12-03.mp4'."""
    seconds = int(incident.start)
    stamp = f"{seconds // 3600:02d}-{seconds % 3600 // 60:02d}-{seconds % 60:02d}"
    return f"{Path(video_path).stem}_incident{incident.id:02d}_{stamp}.mp4"


def export_clip(
    video_path: str | Path,
    start: float,
    end: float,
    output_path: str | Path,
    is_cancelled: CancelCheck = never_cancelled,
) -> Path:
    """Copy the section [start, end] (seconds) of a video into a new MP4 file.

    Frames are copied unchanged so the clip stays faithful to the original recording.
    """
    video = probe_video(video_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video.path))
    writer = cv2.VideoWriter(
        str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), video.fps, (video.width, video.height)
    )
    try:
        if not writer.isOpened():
            raise RuntimeError(f"Could not create the clip file: {output_path}")
        first_frame = int(start * video.fps)
        last_frame = int(end * video.fps)
        capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame)
        for _ in range(first_frame, last_frame + 1):
            if is_cancelled():
                raise OperationCancelled
            ok, frame = capture.read()
            if not ok:
                break
            writer.write(frame)
    except OperationCancelled:
        writer.release()
        output_path.unlink(missing_ok=True)  # don't leave half-written clips behind
        raise
    finally:
        capture.release()
        writer.release()
    return output_path


def export_clips(
    video_path: str | Path,
    incidents: list[Incident],
    output_dir: str | Path,
    on_progress: ProgressCallback = ignore_progress,
    is_cancelled: CancelCheck = never_cancelled,
) -> list[Path]:
    """Save one clip per incident. Reports progress as a fraction from 0 to 1."""
    saved = []
    for index, incident in enumerate(incidents):
        path = Path(output_dir) / clip_filename(video_path, incident)
        saved.append(export_clip(video_path, incident.start, incident.end, path, is_cancelled))
        on_progress((index + 1) / len(incidents))
    return saved
