"""Application-wide constants and persistent user settings."""

from __future__ import annotations

import sys
from dataclasses import dataclass, fields
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

from shopguard import __version__

APP_NAME = "ShopGuard"
APP_VERSION = __version__
ORGANIZATION = "ShopGuard"

VIDEO_EXTENSIONS = (".mp4", ".avi", ".mkv", ".mov", ".m4v", ".wmv")

# Minimum model confidence for a sampled frame to count as suspicious.
SENSITIVITY_THRESHOLDS = {"Low": 0.60, "Balanced": 0.45, "High": 0.30}
SENSITIVITY_HELP = {
    "Low": "Fewer alerts. Only very clear incidents are reported.",
    "Balanced": "Recommended for most shops.",
    "High": "Catches more incidents, but expect more false alarms to review.",
}

# How many frames per second of video are analysed (higher = slower but more thorough).
SAMPLE_FPS_OPTIONS = {2.0: "Fast", 3.0: "Quick", 5.0: "Standard", 8.0: "Thorough"}


def resource_path(relative: str) -> Path:
    """Path to a bundled file, both when running from source and from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def app_data_dir() -> Path:
    """Per-user folder for logs and analysis runs (e.g. %APPDATA%/ShopGuard/ShopGuard on Windows)."""
    path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_output_dir() -> Path:
    """Where saved clips and reports go unless the user picks another folder."""
    videos = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)
    return Path(videos or Path.home()) / APP_NAME


@dataclass
class Settings:
    model_path: str = str(resource_path("models/best.onnx"))
    sensitivity: str = "Balanced"
    sample_fps: float = 5.0
    skip_still_frames: bool = True
    output_dir: str = ""

    @property
    def threshold(self) -> float:
        return SENSITIVITY_THRESHOLDS.get(self.sensitivity, SENSITIVITY_THRESHOLDS["Balanced"])

    @property
    def resolved_output_dir(self) -> Path:
        return Path(self.output_dir) if self.output_dir else default_output_dir()

    @classmethod
    def load(cls) -> Settings:
        store = QSettings(ORGANIZATION, APP_NAME)
        defaults = cls()
        values = {}
        for field in fields(cls):
            default = getattr(defaults, field.name)
            value = store.value(field.name, default)
            # QSettings may return strings, so convert back to the field's type.
            if isinstance(default, bool):
                value = value in (True, "true", "True", "1", 1)
            elif isinstance(default, float):
                value = float(value)
            else:
                value = str(value)
            values[field.name] = value
        return cls(**values)

    def save(self) -> None:
        store = QSettings(ORGANIZATION, APP_NAME)
        for field in fields(self):
            store.setValue(field.name, getattr(self, field.name))
