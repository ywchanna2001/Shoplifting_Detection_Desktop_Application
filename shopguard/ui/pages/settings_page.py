"""Detection settings, model file and output folder. Changes are saved immediately."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QLineEdit, QScrollArea, QWidget

from shopguard.config import SAMPLE_FPS_OPTIONS, SENSITIVITY_HELP, SENSITIVITY_THRESHOLDS, Settings
from shopguard.core.detector import Detector
from shopguard.ui import theme
from shopguard.ui.widgets.common import (
    STRETCH,
    Card,
    SegmentedControl,
    Separator,
    button,
    hbox,
    label,
    vbox,
)


class SettingsPage(QWidget):
    settingsChanged = Signal()

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.settings = settings

        content = QWidget()
        content.setMaximumWidth(820)
        content.setLayout(vbox(
            label("Settings", "H1"),
            label("Changes are saved automatically and used for the next analysis.", "Muted"),
            8,
            self._detection_card(),
            self._model_card(),
            self._output_card(),
            STRETCH,
            spacing=14,
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        wrapper = QWidget()
        wrapper.setLayout(hbox(STRETCH, content, STRETCH, margins=(40, 36, 40, 36)))
        scroll.setWidget(wrapper)
        self.setLayout(vbox(scroll))
        self._check_model()

    # ---- cards -------------------------------------------------------------------------
    def _detection_card(self) -> Card:
        card = Card(padding=22, spacing=14)
        card.layout_.addWidget(label("Detection", "H2"))

        self.sensitivity = SegmentedControl(list(SENSITIVITY_THRESHOLDS))
        self.sensitivity.set_value(self.settings.sensitivity)
        self.sensitivity_help = label(SENSITIVITY_HELP[self.settings.sensitivity], "Small")
        self.sensitivity.changed.connect(self._on_sensitivity)
        card.layout_.addLayout(self._row(
            "Sensitivity", "How confident the model must be before flagging a moment.",
            vbox(self.sensitivity, self.sensitivity_help, spacing=6),
        ))
        card.layout_.addWidget(Separator())

        self.speed = QComboBox()
        for fps, name in SAMPLE_FPS_OPTIONS.items():
            self.speed.addItem(f"{name}  ({fps:g} frames per second)", fps)
        self.speed.setCurrentIndex(max(0, self.speed.findData(self.settings.sample_fps)))
        self.speed.currentIndexChanged.connect(self._on_speed)
        card.layout_.addLayout(self._row(
            "Analysis detail", "More frames per second is more thorough but slower.", self.speed
        ))
        card.layout_.addWidget(Separator())

        self.skip_still = QCheckBox("Skip empty, unchanged scenes")
        self.skip_still.setChecked(self.settings.skip_still_frames)
        self.skip_still.toggled.connect(self._on_skip_still)
        card.layout_.addLayout(self._row(
            "Speed up", "Saves time on footage where nobody is in view.", self.skip_still
        ))
        return card

    def _model_card(self) -> Card:
        card = Card(padding=22, spacing=12)
        card.layout_.addWidget(label("Detection model", "H2"))
        self.model_path = QLineEdit(self.settings.model_path)
        self.model_path.setReadOnly(True)
        browse = button("Browse", "folder")
        browse.clicked.connect(self._browse_model)
        self.model_status = label("", "Small", wrap=True)
        card.layout_.addLayout(hbox(self.model_path, browse, spacing=8))
        card.layout_.addWidget(self.model_status)
        return card

    def _output_card(self) -> Card:
        card = Card(padding=22, spacing=12)
        card.layout_.addWidget(label("Saved clips and reports", "H2"))
        self.output_dir = QLineEdit(str(self.settings.resolved_output_dir))
        self.output_dir.setReadOnly(True)
        browse = button("Change", "folder")
        browse.clicked.connect(self._browse_output)
        card.layout_.addLayout(hbox(self.output_dir, browse, spacing=8))
        card.layout_.addWidget(label("Each video gets its own sub-folder here.", "Small"))
        return card

    @staticmethod
    def _row(title: str, help_text: str, control):
        row = hbox(spacing=24)
        row.addLayout(vbox(label(title, "H3"), label(help_text, "Small", wrap=True), spacing=3), 1)
        if isinstance(control, QWidget):
            row.addWidget(control)
        else:
            row.addLayout(control)
        return row

    # ---- handlers ----------------------------------------------------------------------
    def _save(self) -> None:
        self.settings.save()
        self.settingsChanged.emit()

    def _on_sensitivity(self, value: str) -> None:
        self.settings.sensitivity = value
        self.sensitivity_help.setText(SENSITIVITY_HELP[value])
        self._save()

    def _on_speed(self, _index: int) -> None:
        self.settings.sample_fps = float(self.speed.currentData())
        self._save()

    def _on_skip_still(self, checked: bool) -> None:
        self.settings.skip_still_frames = checked
        self._save()

    def _browse_model(self) -> None:
        start = str(Path(self.settings.model_path).parent)
        path, _ = QFileDialog.getOpenFileName(self, "Choose ONNX model", start, "ONNX model (*.onnx)")
        if path:
            self.settings.model_path = path
            self.model_path.setText(path)
            self._save()
            self._check_model()

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose folder", self.output_dir.text())
        if folder:
            self.settings.output_dir = folder
            self.output_dir.setText(folder)
            self._save()

    def _check_model(self) -> None:
        """Try loading the model so problems show up here, not halfway through an analysis."""
        try:
            detector = Detector(self.settings.model_path)
        except Exception as exc:  # any load error is shown to the user
            self.model_status.setText(f"✕  {exc}")
            self.model_status.setStyleSheet(f"color: {theme.DANGER};")
            return
        names = ", ".join(detector.class_names.values())
        width, height = detector.input_size
        self.model_status.setText(f"✓  Model ready · classes: {names} · input {width}×{height}")
        self.model_status.setStyleSheet(f"color: {theme.SUCCESS};")
