"""Main window: sidebar navigation on the left, pages on the right.

It also coordinates the analysis flow: Upload page → Processing page → Results page.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from shopguard.config import APP_NAME, APP_VERSION, Settings, app_data_dir
from shopguard.core.analyzer import AnalysisResult, VideoAnalyzer
from shopguard.core.detector import Detector
from shopguard.core.video import VideoInfo
from shopguard.ui import icons, theme
from shopguard.ui.pages.processing_page import ProcessingPage
from shopguard.ui.pages.results_page import ResultsPage
from shopguard.ui.pages.settings_page import SettingsPage
from shopguard.ui.pages.upload_page import UploadPage
from shopguard.ui.tasks import BackgroundTask
from shopguard.ui.widgets.common import STRETCH, Toast, hbox, icon_label, label, vbox


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.icon("shield", theme.ACCENT, size=64))
        self.resize(1360, 860)
        self.setMinimumSize(1100, 720)

        self.settings = Settings.load()
        self._task: BackgroundTask | None = None

        self.upload_page = UploadPage()
        self.processing_page = ProcessingPage()
        self.results_page = ResultsPage(self.settings)
        self.settings_page = SettingsPage(self.settings)

        self.pages = QStackedWidget()
        for page in (self.upload_page, self.processing_page, self.results_page, self.settings_page):
            self.pages.addWidget(page)

        central = QWidget()
        central.setObjectName("Central")
        central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        central.setLayout(hbox(self._build_sidebar(), self.pages, spacing=0))
        self.setCentralWidget(central)
        self.toast = Toast(central)

        self.upload_page.analysisRequested.connect(self.start_analysis)
        self.processing_page.cancelRequested.connect(self.cancel_analysis)
        self.results_page.newAnalysisRequested.connect(self._new_analysis)
        self.results_page.message.connect(self.toast.show_message)

        self._show(self.upload_page)

    # ---- sidebar -----------------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        sidebar.setFixedWidth(232)

        self.nav_group = QButtonGroup(self)
        self.nav_analyze = self._nav_button("Analyze video", "upload", self.upload_page)
        self.nav_results = self._nav_button("Results", "list", self.results_page)
        self.nav_settings = self._nav_button("Settings", "sliders", self.settings_page)
        self.nav_results.setEnabled(False)  # nothing to show until an analysis has finished

        privacy = QFrame()
        privacy.setObjectName("PrivacyCard")
        privacy_layout = QVBoxLayout(privacy)
        privacy_layout.setContentsMargins(12, 12, 12, 12)
        privacy_layout.setSpacing(4)
        privacy_layout.addLayout(hbox(icon_label("lock", theme.SUCCESS, 14),
                                      label("Offline mode", "H3"), STRETCH, spacing=8))
        privacy_layout.addWidget(label("Footage and results stay on this computer.", "Small", wrap=True))

        brand = hbox(icon_label("shield", theme.ACCENT, 26),
                     vbox(label(APP_NAME, "AppTitle"), label(f"Version {APP_VERSION}", "Small"), spacing=0),
                     STRETCH, spacing=10)

        sidebar.setLayout(vbox(
            brand, 24,
            label("MENU", "Caption"),
            self.nav_analyze, self.nav_results, self.nav_settings,
            STRETCH,
            privacy,
            spacing=4,
            margins=(16, 22, 16, 18),
        ))
        return sidebar

    def _nav_button(self, text: str, icon_name: str, page: QWidget) -> QPushButton:
        nav = QPushButton(f"  {text}")
        nav.setObjectName("NavButton")
        nav.setCheckable(True)
        nav.setCursor(Qt.CursorShape.PointingHandCursor)
        nav.setIcon(icons.icon(icon_name, theme.MUTED, active_color=theme.TEXT))
        nav.setIconSize(QSize(18, 18))
        nav.clicked.connect(lambda: self._show(page))
        self.nav_group.addButton(nav)
        return nav

    def _show(self, page: QWidget) -> None:
        if page is not self.results_page:
            self.results_page.stop()
        self.pages.setCurrentWidget(page)
        nav_for_page = {
            self.upload_page: self.nav_analyze,
            self.processing_page: self.nav_analyze,
            self.results_page: self.nav_results,
            self.settings_page: self.nav_settings,
        }
        nav_for_page[page].setChecked(True)

    def _set_navigation_enabled(self, enabled: bool) -> None:
        self.nav_analyze.setEnabled(enabled)
        self.nav_settings.setEnabled(enabled)
        self.nav_results.setEnabled(enabled and self.results_page.result is not None)

    # ---- analysis flow ----------------------------------------------------------------
    def start_analysis(self, video: VideoInfo) -> None:
        if not Path(self.settings.model_path).is_file():
            QMessageBox.warning(
                self, "Model not found",
                "The detection model file could not be found.\n\n"
                f"Expected: {self.settings.model_path}\n\n"
                "Choose your trained .onnx model in Settings.",
            )
            self._show(self.settings_page)
            return

        settings = self.settings
        run_dir = app_data_dir() / "runs" / datetime.now().strftime("%Y%m%d_%H%M%S")

        def analyze(progress, is_cancelled) -> AnalysisResult:
            # Runs on the background thread.
            detector = Detector(settings.model_path)
            analyzer = VideoAnalyzer(
                detector,
                threshold=settings.threshold,
                sample_fps=settings.sample_fps,
                sensitivity=settings.sensitivity,
                skip_still_frames=settings.skip_still_frames,
            )
            return analyzer.analyze(video.path, run_dir, progress, is_cancelled)

        self._task = BackgroundTask(analyze, self)
        self._task.progress.connect(self.processing_page.update_progress)
        self._task.succeeded.connect(self._on_analysis_done)
        self._task.failed.connect(self._on_analysis_failed)
        self._task.cancelled.connect(self._on_analysis_cancelled)
        self._task.finished.connect(lambda: self._set_navigation_enabled(True))

        self.processing_page.start(video)
        self._set_navigation_enabled(False)
        self._show(self.processing_page)
        self._task.start()

    def cancel_analysis(self) -> None:
        if self._task and self._task.is_running():
            self._task.cancel()
            self.processing_page.cancel_button.setEnabled(False)

    def _on_analysis_done(self, result: AnalysisResult) -> None:
        self.results_page.show_result(result)
        self._set_navigation_enabled(True)
        self._show(self.results_page)
        count = len(result.incidents)
        if count:
            self.toast.show_message(f"Analysis complete: {count} suspected incident(s) to review.", "success")
        else:
            self.toast.show_message("Analysis complete: no suspicious activity found.", "success")

    def _on_analysis_failed(self, error: str) -> None:
        self._show(self.upload_page)
        QMessageBox.critical(self, "Analysis failed", f"The video could not be analysed.\n\n{error}")

    def _on_analysis_cancelled(self) -> None:
        self._show(self.upload_page)
        self.toast.show_message("Analysis cancelled.")

    def _new_analysis(self) -> None:
        self.upload_page.reset()
        self._show(self.upload_page)

    # ---- closing ------------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._task and self._task.is_running():
            answer = QMessageBox.question(
                self, "Analysis in progress", "An analysis is still running. Stop it and quit?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._task.cancel()
            self._task.wait(10_000)
        self.results_page.stop()
        event.accept()
