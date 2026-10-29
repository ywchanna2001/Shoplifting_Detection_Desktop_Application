"""Area where the user drops a video file or clicks to browse."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QVBoxLayout, QWidget

from shopguard.config import VIDEO_EXTENSIONS
from shopguard.ui import theme
from shopguard.ui.widgets.common import button, icon_label, label, repolish

FILE_FILTER = "Videos (" + " ".join(f"*{ext}" for ext in VIDEO_EXTENSIONS) + ");;All files (*)"


class DropZone(QFrame):
    fileSelected = Signal(Path)
    invalidFile = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(260)

        browse = button("Browse files", "folder", "primary")
        browse.clicked.connect(self._browse)
        formats = ", ".join(ext.lstrip(".").upper() for ext in VIDEO_EXTENSIONS)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addStretch()
        upload_icon = icon_label("upload", theme.ACCENT, 44)
        layout.addWidget(upload_icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(6)
        layout.addWidget(label("Drag and drop a CCTV recording here", "H2"),
                         alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label("or", "Muted"), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(browse, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(4)
        layout.addWidget(label(f"Supported formats: {formats}", "Small"),
                         alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a video", "", FILE_FILTER)
        if path:
            self._accept(Path(path))

    def _accept(self, path: Path) -> None:
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            self.fileSelected.emit(path)
        else:
            self.invalidFile.emit(f"'{path.name}' is not a supported video file.")

    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        repolish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_drag_active(True)

    def dragLeaveEvent(self, event) -> None:
        self._set_drag_active(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_active(False)
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self._accept(Path(urls[0].toLocalFile()))
