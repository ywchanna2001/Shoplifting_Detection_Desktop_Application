"""Turns per-frame detection scores into incidents (time periods worth reviewing).

A single suspicious frame is often noise, so an incident needs several suspicious
frames close together. This "temporal smoothing" is the main defence against false alarms.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shopguard.core.video import format_duration, format_timestamp

STATUS_UNREVIEWED = "Unreviewed"
STATUS_CONFIRMED = "Confirmed"
STATUS_FALSE_ALARM = "False alarm"


@dataclass
class Sample:
    """The model's result for one analysed frame."""

    time: float
    score: float  # highest 'shoplifting' confidence in the frame, 0 if none
    box: tuple[float, float, float, float] | None = None


@dataclass
class Incident:
    id: int
    start: float
    end: float
    peak_time: float
    peak_confidence: float
    mean_confidence: float
    hits: int
    peak_box: tuple[float, float, float, float] | None = None
    snapshot_path: str = ""
    status: str = field(default=STATUS_UNREVIEWED)

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def severity(self) -> str:
        if self.peak_confidence >= 0.75:
            return "High"
        if self.peak_confidence >= 0.5:
            return "Medium"
        return "Low"

    @property
    def label(self) -> str:
        return "Suspected shoplifting"

    @property
    def description(self) -> str:
        return (
            f"Suspicious behaviour detected between {format_timestamp(self.start)} and "
            f"{format_timestamp(self.end)} ({format_duration(self.duration)}). "
            f"Seen in {self.hits} analysed frames, with peak confidence "
            f"{self.peak_confidence:.0%} at {format_timestamp(self.peak_time)}."
        )


def group_incidents(
    samples: list[Sample],
    threshold: float,
    *,
    max_gap: float = 2.0,
    min_hits: int = 3,
    padding: float = 1.5,
    video_duration: float | None = None,
) -> list[Incident]:
    """Group suspicious samples into incidents.

    Args:
        samples: per-frame results, in time order.
        threshold: minimum score for a frame to count as suspicious.
        max_gap: suspicious frames closer than this (seconds) belong to the same incident.
        min_hits: an incident needs at least this many suspicious frames.
        padding: seconds added before and after, so clips show context.
        video_duration: used to keep padded times inside the video.
    """
    positives = [s for s in samples if s.score >= threshold]
    clusters: list[list[Sample]] = []
    for sample in positives:
        if clusters and sample.time - clusters[-1][-1].time <= max_gap:
            clusters[-1].append(sample)
        else:
            clusters.append([sample])

    end_limit = video_duration if video_duration is not None else float("inf")
    incidents = []
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        peak = max(cluster, key=lambda s: s.score)
        incidents.append(
            Incident(
                id=len(incidents) + 1,
                start=max(0.0, cluster[0].time - padding),
                end=min(end_limit, cluster[-1].time + padding),
                peak_time=peak.time,
                peak_confidence=peak.score,
                mean_confidence=sum(s.score for s in cluster) / len(cluster),
                hits=len(cluster),
                peak_box=peak.box,
            )
        )
    return incidents
