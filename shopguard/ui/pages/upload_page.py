"""Step 1: choose a video and start the analysis."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QMessageBox, QStackedWidget, QWidget

from shopguard.core.video import (
    VideoInfo,
    format_duration,
    format_file_size,
    probe_video,
    read_frame_at,
)
from shopguard.ui import theme
from shopguard.ui.widgets.common import (
    STRETCH,
    Card,
    bgr_to_pixmap,
    button,
    hbox,
    icon_label,
    label,
    rounded,
    vbox,
)
from shopguard.ui.widgets.drop_zone import DropZone

PREVIEW_SIZE = QSize(320, 180)


class UploadPage(QWidget):
    analysisRequested = Signal(object)  # VideoInfo

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self._video: VideoInfo | None = None

        self.drop_zone = DropZone()
        self.drop_zone.fileSelected.connect(self.load_video)
        self.drop_zone.invalidFile.connect(lambda msg: QMessageBox.warning(self, "Unsupported file", msg))

        # The content area switches between the drop zone and the selected video's details.
        self.content = QStackedWidget()
        self.content.addWidget(self.drop_zone)
        self.content.addWidget(self._build_video_card())

        privacy = hbox(
            STRETCH,
            icon_label("lock", theme.SUCCESS, 14),
            label("Runs 100% offline. Your footage never leaves this computer.", "Small"),
            STRETCH,
            spacing=8,
        )

        column = vbox(
            label("Analyze CCTV footage", "H1"),
            label(
                "Upload a recording and ShopGuard will find moments that look like shoplifting, "
                "so you only need to watch the parts that matter.",
                "Muted",
                wrap=True,
            ),
            12,
            self.content,
            privacy,
            STRETCH,
            spacing=10,
        )
        container = QWidget()
        container.setMinimumWidth(720)
        container.setMaximumWidth(860)
        container.setLayout(column)
        self.setLayout(hbox(STRETCH, container, STRETCH, margins=(40, 40, 40, 32)))

    def _build_video_card(self) -> Card:
        card = Card(padding=22, spacing=16)
        self.preview = QLabel()
        self.preview.setFixedSize(PREVIEW_SIZE)
        self.preview.setStyleSheet(f"background: {theme.SURFACE_3}; border-radius: 10px;")

        self.name_label = label("", "H2", wrap=True)
        self.detail_labels: dict[str, QLabel] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(8)
        for row, key in enumerate(("Length", "Resolution", "Frame rate", "File size")):
            grid.addWidget(label(key, "Muted"), row, 0)
            self.detail_labels[key] = label("")
            grid.addWidget(self.detail_labels[key], row, 1)
        grid.setColumnStretch(2, 1)

        details = vbox(icon_label("film", theme.ACCENT, 22), self.name_label, grid, STRETCH, spacing=10)
        card.layout_.addLayout(hbox(self.preview, details, spacing=22))

        change = button("Choose another video", "folder", "ghost")
        change.clicked.connect(lambda: self.content.setCurrentIndex(0))
        start = button("Start analysis", "activity", "primary")
        start.setMinimumHeight(40)
        start.clicked.connect(lambda: self._video and self.analysisRequested.emit(self._video))
        card.layout_.addLayout(hbox(change, STRETCH, start))
        return card

    def load_video(self, path: Path) -> None:
        try:
            video = probe_video(path)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "Can't open video", str(exc))
            return

        self._video = video
        self.name_label.setText(video.name)
        self.detail_labels["Length"].setText(format_duration(video.duration))
        self.detail_labels["Resolution"].setText(video.resolution)
        self.detail_labels["Frame rate"].setText(f"{video.fps:.1f} fps")
        self.detail_labels["File size"].setText(format_file_size(video.file_size))

        frame = read_frame_at(video.path, min(video.duration * 0.1, 10.0))
        if frame is not None:
            self.preview.setPixmap(rounded(bgr_to_pixmap(frame), PREVIEW_SIZE, 10))
        else:
            self.preview.clear()
        self.content.setCurrentIndex(1)

    def reset(self) -> None:
        self._video = None
        self.content.setCurrentIndex(0)
