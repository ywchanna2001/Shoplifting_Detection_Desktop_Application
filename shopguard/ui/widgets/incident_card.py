"""One incident in the results list: snapshot, times, confidence and review actions."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from shopguard.core.incidents import (
    STATUS_CONFIRMED,
    STATUS_FALSE_ALARM,
    STATUS_UNREVIEWED,
    Incident,
)
from shopguard.core.video import format_duration, format_timestamp
from shopguard.ui import theme
from shopguard.ui.widgets.common import STRETCH, button, hbox, icon_label, label, repolish, rounded

THUMB_SIZE = QSize(136, 76)


class IncidentCard(QFrame):
    selected = Signal(int)
    playRequested = Signal(int)
    saveRequested = Signal(int)
    statusChanged = Signal(int, str)

    def __init__(self, incident: Incident, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident = incident
        self.setObjectName("IncidentCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        thumbnail = QLabel()
        thumbnail.setFixedSize(THUMB_SIZE)
        source = QPixmap(incident.snapshot_path) if incident.snapshot_path else QPixmap()
        if not source.isNull():
            thumbnail.setPixmap(rounded(source, THUMB_SIZE))
        else:
            thumbnail.setStyleSheet(f"background: {theme.SURFACE_3}; border-radius: 8px;")

        badge = label(incident.severity.upper(), "Badge")
        badge.setProperty("severity", incident.severity)
        title = label(f"Incident #{incident.id}", "H3")
        self.status_label = label("", "Status")

        times = label(
            f"{format_timestamp(incident.start)} → {format_timestamp(incident.end)}"
            f"  ·  {format_duration(incident.duration)}",
            "Muted",
        )
        confidence = label(
            f"Peak confidence {incident.peak_confidence:.0%}  ·  average {incident.mean_confidence:.0%}",
            "Small",
        )

        play = button("Play", "play", "ghost", "Play this incident")
        save = button("Save clip", "download", "ghost", "Save this incident as a video clip")
        self.confirm = button("Confirm", "check", "ghost", "Mark as real shoplifting")
        self.dismiss = button("Dismiss", "x", "ghost", "Mark as a false alarm")
        for toggle in (self.confirm, self.dismiss):
            toggle.setCheckable(True)

        play.clicked.connect(lambda: self.playRequested.emit(incident.id))
        save.clicked.connect(lambda: self.saveRequested.emit(incident.id))
        self.confirm.clicked.connect(lambda: self._toggle_status(STATUS_CONFIRMED))
        self.dismiss.clicked.connect(lambda: self._toggle_status(STATUS_FALSE_ALARM))

        details = QVBoxLayout()
        details.setSpacing(5)
        details.addLayout(hbox(title, badge, STRETCH, spacing=8))
        details.addLayout(hbox(icon_label("clock", theme.MUTED, 14), times, STRETCH, spacing=6))
        details.addWidget(confidence)
        details.addWidget(self.status_label)
        details.addStretch()

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(thumbnail, alignment=Qt.AlignmentFlag.AlignTop)
        top.addLayout(details, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addLayout(hbox(play, save, STRETCH, self.confirm, self.dismiss, spacing=2))

        self._refresh_status()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        repolish(self)

    def _toggle_status(self, status: str) -> None:
        # Clicking the active button again returns the incident to "Unreviewed".
        new_status = STATUS_UNREVIEWED if self.incident.status == status else status
        self.incident.status = new_status
        self._refresh_status()
        self.statusChanged.emit(self.incident.id, new_status)

    def _refresh_status(self) -> None:
        status = self.incident.status
        self.confirm.setChecked(status == STATUS_CONFIRMED)
        self.dismiss.setChecked(status == STATUS_FALSE_ALARM)
        self.status_label.setText(f"Review: {status}")
        self.status_label.setProperty("status", status)
        repolish(self.status_label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.incident.id)
        super().mousePressEvent(event)
