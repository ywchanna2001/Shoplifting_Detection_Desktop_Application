"""Start ShopGuard:  python main.py"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from PySide6.QtWidgets import QApplication

from shopguard.config import APP_NAME, ORGANIZATION, app_data_dir
from shopguard.ui.main_window import MainWindow
from shopguard.ui.theme import STYLESHEET


def setup_logging() -> None:
    """Log to a file in the user's app data folder (useful when a user reports a problem)."""
    log_file = app_data_dir() / "shopguard.log"
    handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[handler, logging.StreamHandler()],
    )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)
    app.setStyle("Fusion")  # consistent base style on every OS; our style sheet goes on top
    app.setStyleSheet(STYLESHEET)

    setup_logging()
    logging.getLogger(__name__).info("Starting %s", APP_NAME)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
