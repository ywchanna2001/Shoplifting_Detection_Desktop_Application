"""Step 3: review incidents, play footage, save clips and export the report."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from shopguard.config import Settings
from shopguard.core.analyzer import AnalysisResult
from shopguard.core.clips import clip_filename, export_clip, export_clips
from shopguard.core.report import build_html_report
from shopguard.core.video import format_duration, format_timestamp
from shopguard.ui import icons, theme
from shopguard.ui.tasks import BackgroundTask
from shopguard.ui.widgets.common import (
    STRETCH,
    Card,
    StatCard,
    button,
    hbox,
    icon_label,
    label,
    vbox,
)
from shopguard.ui.widgets.incident_card import IncidentCard
from shopguard.ui.widgets.timeline import Timeline


class ResultsPage(QWidget):
    newAnalysisRequested = Signal()
    message = Signal(str, str)  # text, kind ("info" | "success" | "error")

    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.settings = settings
        self.result: AnalysisResult | None = None
        self._cards: dict[int, IncidentCard] = {}
        self._stop_at_ms: int | None = None  # pause automatically at the end of an incident
        self._task: BackgroundTask | None = None

        # ---- header -----------------------------------------------------------------
        self.subtitle = label("", "Muted")
        self.save_all_button = button("Save all clips", "download")
        self.report_button = button("Export report", "file-text", "primary")
        new_button = button("New analysis", "plus", "ghost")
        self.save_all_button.clicked.connect(self._save_all_clips)
        self.report_button.clicked.connect(self._export_report)
        new_button.clicked.connect(self.newAnalysisRequested)
        header = hbox(
            vbox(label("Results", "H1"), self.subtitle, spacing=4),
            STRETCH, new_button, self.save_all_button, self.report_button, spacing=8,
        )

        # ---- summary ----------------------------------------------------------------
        self.stat_incidents = StatCard("Suspected incidents", "alert")
        self.stat_length = StatCard("Video length", "film")
        self.stat_time = StatCard("Analysis time", "cpu")
        self.stat_peak = StatCard("Highest confidence", "activity")
        stats = hbox(self.stat_incidents, self.stat_length, self.stat_time, self.stat_peak)

        # ---- body: player (left) and incident list (right) --------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_player())
        splitter.addWidget(self._build_incident_list())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setHandleWidth(14)
        splitter.setChildrenCollapsible(False)

        self.setLayout(vbox(header, stats, splitter, spacing=16, margins=(32, 28, 32, 28)))

    # ---- building blocks --------------------------------------------------------------
    def _build_player(self) -> Card:
        card = Card(padding=14, spacing=10)
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(420, 236)
        self.video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_widget.setStyleSheet("background: #05070A;")

        # No audio output: CCTV audio is usually silent or noise, and skipping it avoids
        # problems on PCs without a working sound device.
        self.player = QMediaPlayer(self)
        self.player.setVideoOutput(self.video_widget)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.playbackStateChanged.connect(self._update_play_icon)
        self.player.errorOccurred.connect(
            lambda _error, text: self.message.emit(f"Playback problem: {text}", "error")
        )

        self.play_button = button(icon_name="play", variant="icon", tooltip="Play / pause")
        self.play_button.setFixedSize(36, 36)
        self.play_button.clicked.connect(self._toggle_play)
        self.time_label = label("00:00 / 00:00", "Muted")

        self.timeline = Timeline()
        self.timeline.seekRequested.connect(self._seek)
        self.timeline.incidentClicked.connect(self._select_incident)

        card.layout_.addWidget(self.video_widget, 1)
        card.layout_.addLayout(hbox(self.play_button, self.time_label, STRETCH, spacing=10))
        card.layout_.addWidget(self.timeline)
        return card

    def _build_incident_list(self) -> Card:
        card = Card(padding=14, spacing=10)
        self.list_title = label("Incidents", "H2")
        card.layout_.addLayout(hbox(self.list_title, STRETCH))

        self.list_container = QWidget()
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.list_container)
        scroll.setMinimumWidth(400)
        card.layout_.addWidget(scroll, 1)
        return card

    def _empty_state(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        layout.addStretch()
        center = Qt.AlignmentFlag.AlignHCenter
        layout.addWidget(icon_label("shield-check", theme.SUCCESS, 40), alignment=center)
        layout.addWidget(label("No suspicious activity found", "H2"), alignment=center)
        hint = label("Try the High sensitivity setting if you expected an incident.", "Muted", wrap=True)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch()
        return widget

    # ---- showing a result -------------------------------------------------------------
    def show_result(self, result: AnalysisResult) -> None:
        self.result = result
        video = result.video
        self.subtitle.setText(
            f"{video.name}  ·  analysed {result.created_at:%d %b %Y, %H:%M}  ·  "
            f"{result.sensitivity} sensitivity"
        )
        self._update_stats()
        self.stat_length.set_value(format_duration(video.duration))
        self.stat_time.set_value(format_duration(result.processing_time))

        # Rebuild the incident list
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)  # remove from screen immediately
                item.widget().deleteLater()
        self._cards.clear()
        if result.incidents:
            for incident in result.incidents:
                card = IncidentCard(incident)
                card.selected.connect(self._select_incident)
                card.playRequested.connect(self._play_incident)
                card.saveRequested.connect(self._save_clip)
                card.statusChanged.connect(lambda *_: self._on_status_changed())
                self._cards[incident.id] = card
                self.list_layout.addWidget(card)
            self.list_layout.addStretch()
        else:
            self.list_layout.addWidget(self._empty_state())
        self.list_title.setText(f"Incidents ({len(result.incidents)})")
        self.save_all_button.setEnabled(bool(result.incidents))

        self.timeline.set_data(video.duration, result.incidents)
        self._stop_at_ms = None
        self.player.setSource(QUrl.fromLocalFile(str(video.path)))
        self.time_label.setText(f"00:00 / {format_timestamp(video.duration)}")
        if result.incidents:
            self._select_incident(result.incidents[0].id, seek=True)

    def _update_stats(self) -> None:
        active = self.result.active_incidents
        self.stat_incidents.set_value(str(len(active)), theme.DANGER if active else theme.SUCCESS)
        peak = max((i.peak_confidence for i in active), default=0.0)
        self.stat_peak.set_value(f"{peak:.0%}" if active else "–")

    def _on_status_changed(self) -> None:
        self._update_stats()
        self.timeline.update()

    def stop(self) -> None:
        self.player.stop()

    # ---- playback ---------------------------------------------------------------------
    def _incident(self, incident_id: int):
        return next(i for i in self.result.incidents if i.id == incident_id)

    def _select_incident(self, incident_id: int, seek: bool = True) -> None:
        for card_id, card in self._cards.items():
            card.set_selected(card_id == incident_id)
        self.timeline.set_selected(incident_id)
        if seek:
            self._seek(self._incident(incident_id).start)

    def _play_incident(self, incident_id: int) -> None:
        incident = self._incident(incident_id)
        self._select_incident(incident_id)
        self._stop_at_ms = int(incident.end * 1000)
        self.player.play()

    def _seek(self, seconds: float) -> None:
        self._stop_at_ms = None
        self.player.setPosition(int(seconds * 1000))
        self.timeline.set_position(seconds)

    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self._stop_at_ms = None
            self.player.play()

    def _on_position_changed(self, position_ms: int) -> None:
        if self._stop_at_ms is not None and position_ms >= self._stop_at_ms:
            self._stop_at_ms = None
            self.player.pause()
        seconds = position_ms / 1000
        self.timeline.set_position(seconds)
        if self.result:
            self.time_label.setText(
                f"{format_timestamp(seconds)} / {format_timestamp(self.result.video.duration)}"
            )

    def _update_play_icon(self, state) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setIcon(icons.icon("pause" if playing else "play", theme.TEXT))

    # ---- saving -----------------------------------------------------------------------
    def _output_dir(self) -> Path:
        folder = self.settings.resolved_output_dir / self.result.video.path.stem
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _run_task(self, function, success_message: str, open_path: Path | None = None) -> None:
        if self._task and self._task.is_running():
            self.message.emit("Please wait for the current save to finish.", "info")
            return
        self._task = BackgroundTask(function, self)
        self._task.succeeded.connect(lambda _: self.message.emit(success_message, "success"))
        if open_path:
            self._task.succeeded.connect(
                lambda _: QDesktopServices.openUrl(QUrl.fromLocalFile(str(open_path)))
            )
        self._task.failed.connect(lambda error: QMessageBox.critical(self, "Save failed", error))
        self._task.start()

    def _save_clip(self, incident_id: int) -> None:
        incident = self._incident(incident_id)
        default = self._output_dir() / clip_filename(self.result.video.path, incident)
        path, _ = QFileDialog.getSaveFileName(self, "Save clip", str(default), "MP4 video (*.mp4)")
        if not path:
            return
        video_path = self.result.video.path
        self.message.emit(f"Saving clip for incident #{incident_id}…", "info")
        self._run_task(
            lambda _progress, is_cancelled: export_clip(
                video_path, incident.start, incident.end, path, is_cancelled
            ),
            f"Clip saved: {Path(path).name}",
        )

    def _save_all_clips(self) -> None:
        incidents = self.result.active_incidents
        if not incidents:
            self.message.emit("All incidents are marked as false alarms.", "info")
            return
        folder = QFileDialog.getExistingDirectory(self, "Save clips to folder", str(self._output_dir()))
        if not folder:
            return
        video_path = self.result.video.path
        self.message.emit(f"Saving {len(incidents)} clips…", "info")
        self._run_task(
            lambda progress, is_cancelled: export_clips(
                video_path, incidents, folder, progress, is_cancelled
            ),
            f"{len(incidents)} clips saved",
            open_path=Path(folder),
        )

    def _export_report(self) -> None:
        default = self._output_dir() / f"{self.result.video.path.stem}_report.html"
        path, _ = QFileDialog.getSaveFileName(self, "Export report", str(default), "HTML report (*.html)")
        if not path:
            return
        try:
            build_html_report(self.result, path)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.message.emit("Report exported. Use your browser's Print → Save as PDF for a PDF copy.",
                          "success")
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
