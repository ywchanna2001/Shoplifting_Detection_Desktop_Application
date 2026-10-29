"""Custom-painted video timeline that shows incidents as coloured regions."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QToolTip, QWidget

from shopguard.core.incidents import STATUS_FALSE_ALARM, Incident
from shopguard.core.video import format_timestamp
from shopguard.ui import theme

TRACK_HEIGHT = 10
MIN_REGION_WIDTH = 4  # keep very short incidents visible on long videos


class Timeline(QWidget):
    seekRequested = Signal(float)  # seconds
    incidentClicked = Signal(int)  # incident id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(46)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._duration = 0.0
        self._position = 0.0
        self._incidents: list[Incident] = []
        self._selected_id: int | None = None

    def set_data(self, duration: float, incidents: list[Incident]) -> None:
        self._duration = duration
        self._incidents = incidents
        self._position = 0.0
        self._selected_id = None
        self.update()

    def set_position(self, seconds: float) -> None:
        self._position = seconds
        self.update()

    def set_selected(self, incident_id: int | None) -> None:
        self._selected_id = incident_id
        self.update()

    # ---- geometry helpers -------------------------------------------------------------
    def _track_rect(self) -> QRectF:
        return QRectF(8, 8, self.width() - 16, TRACK_HEIGHT)

    def _x_for(self, seconds: float) -> float:
        track = self._track_rect()
        if self._duration <= 0:
            return track.left()
        return track.left() + track.width() * min(1.0, max(0.0, seconds / self._duration))

    def _seconds_at(self, x: float) -> float:
        track = self._track_rect()
        fraction = (x - track.left()) / max(1.0, track.width())
        return min(1.0, max(0.0, fraction)) * self._duration

    def _incident_at(self, x: float) -> Incident | None:
        for incident in self._incidents:
            left = self._x_for(incident.start)
            right = max(self._x_for(incident.end), left + MIN_REGION_WIDTH)
            if left - 2 <= x <= right + 2:
                return incident
        return None

    # ---- painting -----------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self._track_rect()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.SURFACE_3))
        painter.drawRoundedRect(track, 5, 5)

        # Played part
        played = QRectF(track.left(), track.top(), self._x_for(self._position) - track.left(), TRACK_HEIGHT)
        painter.setBrush(QColor(theme.ACCENT).darker(160))
        painter.drawRoundedRect(played, 5, 5)

        for incident in self._incidents:
            left = self._x_for(incident.start)
            width = max(self._x_for(incident.end) - left, MIN_REGION_WIDTH)
            dismissed = incident.status == STATUS_FALSE_ALARM
            color = QColor(theme.SUBTLE if dismissed else theme.SEVERITY_COLORS[incident.severity])
            painter.setBrush(color)
            region = QRectF(left, track.top() - 3, width, TRACK_HEIGHT + 6)
            painter.drawRoundedRect(region, 3, 3)
            if incident.id == self._selected_id:
                painter.setPen(QColor(theme.TEXT))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(region.adjusted(-2, -2, 2, 2), 4, 4)
                painter.setPen(Qt.PenStyle.NoPen)

        # Playhead
        x = self._x_for(self._position)
        painter.setBrush(QColor(theme.TEXT))
        painter.drawEllipse(QRectF(x - 6, track.center().y() - 6, 12, 12))

        # Start and end time labels
        font = QFont(self.font())
        font.setPointSizeF(8)
        painter.setFont(font)
        painter.setPen(QColor(theme.MUTED))
        text_rect = QRectF(track.left(), track.bottom() + 8, track.width(), 16)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft, "00:00")
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight, format_timestamp(self._duration))
        painter.end()

    # ---- interaction ---------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._duration <= 0:
            return
        incident = self._incident_at(event.position().x())
        if incident:
            self.incidentClicked.emit(incident.id)
        else:
            self.seekRequested.emit(self._seconds_at(event.position().x()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._duration <= 0:
            return
        x = event.position().x()
        incident = self._incident_at(x)
        text = format_timestamp(self._seconds_at(x))
        if incident:
            text = (f"Incident #{incident.id} · {incident.severity} · "
                    f"{format_timestamp(incident.start)}–{format_timestamp(incident.end)}")
        QToolTip.showText(event.globalPosition().toPoint(), text, self)
