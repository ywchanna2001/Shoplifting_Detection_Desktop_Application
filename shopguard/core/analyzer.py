"""Analyses a whole video: samples frames, runs the detector and builds incidents."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from shopguard.core.common import (
    CancelCheck,
    OperationCancelled,
    ProgressCallback,
    ignore_progress,
    never_cancelled,
)
from shopguard.core.detector import Detection, Detector
from shopguard.core.incidents import STATUS_FALSE_ALARM, Incident, Sample, group_incidents
from shopguard.core.video import VideoInfo, probe_video

TARGET_LABEL = "shoplifting"
PREVIEW_WIDTH = 640
PROGRESS_INTERVAL = 0.2  # seconds between progress updates sent to the UI
# A frame counts as "nothing moved" when less than this fraction of pixels changed noticeably.
STILL_PIXEL_DELTA = 20
STILL_CHANGED_FRACTION = 0.001

COLOR_SUSPICIOUS = (80, 80, 255)  # BGR red
COLOR_NORMAL = (120, 200, 80)  # BGR green


@dataclass
class AnalysisProgress:
    fraction: float
    frames_analyzed: int
    suspicious_frames: int
    elapsed: float
    preview: np.ndarray | None = None  # BGR frame with boxes drawn, for the live preview

    @property
    def remaining(self) -> float | None:
        if self.fraction <= 0.02:
            return None  # too early for a reliable estimate
        return self.elapsed / self.fraction - self.elapsed


@dataclass
class AnalysisResult:
    video: VideoInfo
    incidents: list[Incident]
    samples: list[Sample]
    frames_analyzed: int
    processing_time: float
    sensitivity: str
    threshold: float
    sample_fps: float
    model_name: str
    run_dir: Path
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def active_incidents(self) -> list[Incident]:
        """Incidents the user has not dismissed as false alarms."""
        return [i for i in self.incidents if i.status != STATUS_FALSE_ALARM]


class VideoAnalyzer:
    def __init__(
        self,
        detector: Detector,
        *,
        threshold: float,
        sample_fps: float,
        sensitivity: str = "",
        skip_still_frames: bool = True,
    ) -> None:
        self.detector = detector
        self.threshold = threshold
        self.sample_fps = sample_fps
        self.sensitivity = sensitivity
        self.skip_still_frames = skip_still_frames

        self._target_ids = {
            class_id for class_id, name in detector.class_names.items()
            if name.lower() == TARGET_LABEL
        }
        if not self._target_ids:
            found = ", ".join(detector.class_names.values())
            raise ValueError(f"The model has no '{TARGET_LABEL}' class. Classes found: {found}.")

    def analyze(
        self,
        video_path: str | Path,
        run_dir: str | Path,
        on_progress: ProgressCallback = ignore_progress,
        is_cancelled: CancelCheck = never_cancelled,
    ) -> AnalysisResult:
        video = probe_video(video_path)
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        step = max(1, round(video.fps / self.sample_fps))  # analyse every Nth frame
        samples: list[Sample] = []
        suspicious = 0
        previous_small: np.ndarray | None = None
        detections: list[Detection] = []
        started = time.perf_counter()
        last_report = 0.0

        capture = cv2.VideoCapture(str(video.path))
        try:
            frame_index = 0
            while True:
                if is_cancelled():
                    raise OperationCancelled

                # grab() skips a frame without decoding it, which is much faster than read().
                if frame_index % step:
                    if not capture.grab():
                        break
                    frame_index += 1
                    continue

                ok, frame = capture.read()
                if not ok:
                    break
                timestamp = frame_index / video.fps

                # Skip the model only for an empty, unchanged scene. If anyone was in the
                # previous frame we always analyse, because concealment can involve little motion.
                small = cv2.cvtColor(
                    cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY
                )
                is_still = (
                    self.skip_still_frames
                    and previous_small is not None
                    and not detections
                    and (cv2.absdiff(small, previous_small) > STILL_PIXEL_DELTA).mean()
                    < STILL_CHANGED_FRACTION
                )
                previous_small = small

                detections = [] if is_still else self.detector.detect(frame)
                targets = [d for d in detections if d.class_id in self._target_ids]
                best = max(targets, key=lambda d: d.confidence, default=None)
                samples.append(
                    Sample(
                        time=timestamp,
                        score=best.confidence if best else 0.0,
                        box=best.box if best else None,
                    )
                )
                if best and best.confidence >= self.threshold:
                    suspicious += 1

                now = time.perf_counter()
                if now - last_report >= PROGRESS_INTERVAL:
                    last_report = now
                    on_progress(
                        AnalysisProgress(
                            fraction=min(1.0, frame_index / video.frame_count),
                            frames_analyzed=len(samples),
                            suspicious_frames=suspicious,
                            elapsed=now - started,
                            preview=self._make_preview(frame, detections),
                        )
                    )
                frame_index += 1
        finally:
            capture.release()

        incidents = group_incidents(
            samples,
            self.threshold,
            min_hits=max(2, round(self.sample_fps * 0.6)),
            video_duration=video.duration,
        )
        self._save_snapshots(video, incidents, run_dir / "snapshots")

        return AnalysisResult(
            video=video,
            incidents=incidents,
            samples=samples,
            frames_analyzed=len(samples),
            processing_time=time.perf_counter() - started,
            sensitivity=self.sensitivity,
            threshold=self.threshold,
            sample_fps=self.sample_fps,
            model_name=self.detector.model_path.name,
            run_dir=run_dir,
        )

    def _make_preview(self, frame: np.ndarray, detections: list[Detection]) -> np.ndarray:
        scale = PREVIEW_WIDTH / frame.shape[1]
        preview = cv2.resize(frame, (PREVIEW_WIDTH, round(frame.shape[0] * scale)))
        for det in detections:
            suspicious = det.class_id in self._target_ids and det.confidence >= self.threshold
            draw_box(preview, [v * scale for v in det.box], det.label, det.confidence,
                     COLOR_SUSPICIOUS if suspicious else COLOR_NORMAL)
        return preview

    def _save_snapshots(self, video: VideoInfo, incidents: list[Incident], folder: Path) -> None:
        """Save the frame with the highest confidence for each incident."""
        if not incidents:
            return
        folder.mkdir(parents=True, exist_ok=True)
        capture = cv2.VideoCapture(str(video.path))
        try:
            for incident in incidents:
                capture.set(cv2.CAP_PROP_POS_MSEC, incident.peak_time * 1000)
                ok, frame = capture.read()
                if not ok:
                    continue
                if incident.peak_box:
                    draw_box(frame, incident.peak_box, TARGET_LABEL,
                             incident.peak_confidence, COLOR_SUSPICIOUS)
                path = folder / f"incident_{incident.id:03d}.jpg"
                cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                incident.snapshot_path = str(path)
        finally:
            capture.release()


def draw_box(image: np.ndarray, box, label: str, confidence: float, color) -> None:
    x1, y1, x2, y2 = (int(v) for v in box)
    thickness = max(2, image.shape[1] // 400)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, thickness)
    text = f"{label} {confidence:.0%}"
    font_scale = max(0.45, image.shape[1] / 1600)
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
    top = max(0, y1 - th - baseline - 4)
    cv2.rectangle(image, (x1, top), (x1 + tw + 8, top + th + baseline + 4), color, -1)
    cv2.putText(image, text, (x1 + 4, top + th + 2), cv2.FONT_HERSHEY_SIMPLEX,
                font_scale, (255, 255, 255), 1, cv2.LINE_AA)
