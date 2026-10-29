"""Small building blocks shared by several pages."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from shopguard.ui import icons, theme


def repolish(widget: QWidget) -> None:
    """Re-apply the style sheet after changing a property that QSS selectors use."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def label(text: str = "", style: str | None = None, wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if style:
        widget.setObjectName(style)
    widget.setWordWrap(wrap)
    return widget


def button(
    text: str = "",
    icon_name: str | None = None,
    variant: str | None = None,
    tooltip: str = "",
) -> QPushButton:
    widget = QPushButton(f" {text}" if text and icon_name else text)  # gap between icon and text
    if variant:
        widget.setProperty("variant", variant)
    if icon_name:
        color = "#FFFFFF" if variant == "primary" else theme.TEXT
        widget.setIcon(icons.icon(icon_name, color))
        widget.setIconSize(QSize(16, 16))
    if tooltip:
        widget.setToolTip(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def icon_label(name: str, color: str = theme.MUTED, size: int = 18) -> QLabel:
    widget = QLabel()
    widget.setPixmap(icons.pixmap(name, color, size))
    widget.setFixedSize(size, size)
    return widget


def bgr_to_pixmap(frame: np.ndarray) -> QPixmap:
    """Convert an OpenCV (BGR) image to a QPixmap."""
    height, width = frame.shape[:2]
    image = QImage(frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888)
    return QPixmap.fromImage(image.copy())  # copy: the NumPy buffer may be freed later


def rounded(pixmap: QPixmap, size: QSize, radius: float = 8) -> QPixmap:
    """Scale-and-crop a pixmap to fill `size`, with rounded corners."""
    scaled = pixmap.scaled(size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
    x = (scaled.width() - size.width()) // 2
    y = (scaled.height() - size.height()) // 2
    result = QPixmap(size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(-x, -y, scaled)
    painter.end()
    return result


class Card(QFrame):
    """Rounded panel with a vertical layout."""

    def __init__(self, padding: int = 20, spacing: int = 12, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(padding, padding, padding, padding)
        self.layout_.setSpacing(spacing)


class StatCard(Card):
    """Small card showing one number, e.g. 'Suspected incidents: 3'."""

    def __init__(self, title: str, icon_name: str, parent: QWidget | None = None) -> None:
        super().__init__(padding=16, spacing=6, parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(icon_label(icon_name, theme.MUTED, 16))
        header.addWidget(label(title, "Muted"))
        header.addStretch()
        self.value = label("–", "StatValue")
        self.layout_.addLayout(header)
        self.layout_.addWidget(self.value)

    def set_value(self, text: str, color: str | None = None) -> None:
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color};" if color else "")


class SegmentedControl(QFrame):
    """A row of mutually exclusive options, like iOS segmented buttons."""

    changed = Signal(str)

    def __init__(self, options: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentGroup")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._buttons: dict[str, QPushButton] = {}
        for option in options:
            segment = QPushButton(option)
            segment.setObjectName("Segment")
            segment.setCheckable(True)
            segment.setCursor(Qt.CursorShape.PointingHandCursor)
            self._group.addButton(segment)
            self._buttons[option] = segment
            layout.addWidget(segment)
        self._group.buttonClicked.connect(lambda b: self.changed.emit(b.text()))

    def set_value(self, value: str) -> None:
        if value in self._buttons:
            self._buttons[value].setChecked(True)


class Toast(QLabel):
    """Short message that appears at the bottom of the window and fades away."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.hide()
        self._timer = QTimer(self, singleShot=True, timeout=self.hide)

    def show_message(self, text: str, kind: str = "info", duration_ms: int = 3500) -> None:
        self.setText(text)
        self.setProperty("kind", kind)
        repolish(self)
        self.adjustSize()
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 28)
        self.raise_()
        self.show()
        self._timer.start(duration_ms)


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {theme.BORDER}; border: none;")


def vbox(*items, spacing: int = 12, margins: tuple[int, int, int, int] = (0, 0, 0, 0)) -> QVBoxLayout:
    """Build a vertical layout from widgets, layouts, or ints (fixed spacing)."""
    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    _fill(layout, items)
    return layout


def hbox(*items, spacing: int = 12, margins: tuple[int, int, int, int] = (0, 0, 0, 0)) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    _fill(layout, items)
    return layout


STRETCH = object()  # marker: add a flexible space


def _fill(layout, items) -> None:
    for item in items:
        if item is STRETCH:
            layout.addStretch()
        elif isinstance(item, int):
            layout.addSpacing(item)
        elif isinstance(item, QWidget):
            layout.addWidget(item)
        else:
            layout.addLayout(item)
