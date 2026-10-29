"""Step 2: live progress while the video is analysed."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QProgressBar, QSizePolicy, QWidget

from shopguard.core.analyzer import AnalysisProgress
from shopguard.core.video import VideoInfo, format_duration
from shopguard.ui import theme
from shopguard.ui.widgets.common import (
    STRETCH,
    Card,
    StatCard,
    bgr_to_pixmap,
    button,
    hbox,
    icon_label,
    label,
    vbox,
)


class ProcessingPage(QWidget):
    cancelRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")

        self.title = label("Analyzing footage", "H1")
        self.subtitle = label("", "Muted")

        self.preview = QLabel("Preparing…")
        self.preview.setObjectName("VideoSurface")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(480, 270)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._last_preview: QPixmap | None = None

        self.percent = label("0%", "BigPercent")
        self.stage = label("Loading the detection model…", "Muted")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)

        self.elapsed = StatCard("Elapsed", "clock")
        self.remaining = StatCard("Time remaining", "activity")
        self.frames = StatCard("Frames analysed", "film")
        self.suspicious = StatCard("Suspicious frames", "alert")

        self.cancel_button = button("Cancel analysis", "x", "danger")
        self.cancel_button.clicked.connect(self.cancelRequested)

        preview_card = Card(padding=12)
        preview_card.layout_.addWidget(self.preview)
        preview_card.layout_.addLayout(
            hbox(icon_label("eye-off", theme.SUBTLE, 14),
                 label("Live preview. Red boxes are suspicious, green are normal.", "Small"),
                 STRETCH, spacing=6)
        )

        progress_card = Card(padding=22, spacing=10)
        progress_card.layout_.addLayout(hbox(self.percent, STRETCH, self.cancel_button))
        progress_card.layout_.addWidget(self.progress)
        progress_card.layout_.addWidget(self.stage)

        column = vbox(
            vbox(self.title, self.subtitle, spacing=4),
            preview_card,
            progress_card,
            hbox(self.elapsed, self.remaining, self.frames, self.suspicious, spacing=12),
            spacing=16,
        )
        self.setLayout(hbox(column, margins=(36, 32, 36, 32)))

    def start(self, video: VideoInfo) -> None:
        self.subtitle.setText(f"{video.name}  ·  {format_duration(video.duration)}")
        self.percent.setText("0%")
        self.progress.setValue(0)
        self.stage.setText("Loading the detection model…")
        self.preview.setText("Preparing…")
        self._last_preview = None
        self.cancel_button.setEnabled(True)
        for card in (self.elapsed, self.remaining, self.frames, self.suspicious):
            card.set_value("–")

    def update_progress(self, progress: AnalysisProgress) -> None:
        self.percent.setText(f"{progress.fraction:.0%}")
        self.progress.setValue(round(progress.fraction * 1000))
        self.stage.setText(
            "Finishing up: grouping incidents and saving snapshots…"
            if progress.fraction >= 0.99 else "Looking for suspicious behaviour…"
        )
        self.elapsed.set_value(format_duration(progress.elapsed))
        remaining = progress.remaining
        self.remaining.set_value(format_duration(remaining) if remaining is not None else "Estimating…")
        self.frames.set_value(f"{progress.frames_analyzed:,}")
        self.suspicious.set_value(
            f"{progress.suspicious_frames:,}",
            theme.DANGER if progress.suspicious_frames else None,
        )
        if progress.preview is not None:
            self._last_preview = bgr_to_pixmap(progress.preview)
            self._show_preview()

    def _show_preview(self) -> None:
        if self._last_preview:
            self.preview.setPixmap(self._last_preview.scaled(
                self.preview.size() - QSize(4, 4),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._show_preview()
