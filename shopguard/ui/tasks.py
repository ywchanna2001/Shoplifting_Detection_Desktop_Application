"""Runs slow work (video analysis, saving clips) on a background thread.

Rule of thumb for desktop apps: never do slow work on the main (UI) thread, or the
window freezes. Work runs in a QThread and talks to the UI only through signals,
which Qt safely delivers back on the main thread.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from shopguard.core.common import CancelCheck, OperationCancelled, ProgressCallback

logger = logging.getLogger(__name__)

TaskFunction = Callable[[ProgressCallback, CancelCheck], Any]


class _Worker(QObject):
    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, function: TaskFunction) -> None:
        super().__init__()
        self._function = function
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        try:
            result = self._function(self.progress.emit, lambda: self._cancel_requested)
        except OperationCancelled:
            self.cancelled.emit()
        except Exception as exc:  # report any failure to the UI instead of crashing
            logger.exception("Background task failed")
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.succeeded.emit(result)


class BackgroundTask(QObject):
    """Usage:
        task = BackgroundTask(lambda progress, is_cancelled: slow_work(progress, is_cancelled))
        task.succeeded.connect(on_done)
        task.start()
    """

    progress = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()  # always emitted last, whatever the outcome

    def __init__(self, function: TaskFunction, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread = QThread()
        self._worker = _Worker(function)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress)
        self._worker.succeeded.connect(self.succeeded)
        self._worker.failed.connect(self.failed)
        self._worker.cancelled.connect(self.cancelled)
        for outcome in (self._worker.succeeded, self._worker.failed, self._worker.cancelled):
            outcome.connect(self._thread.quit)
        self._thread.finished.connect(self.finished)

    def start(self) -> None:
        self._thread.start()

    def cancel(self) -> None:
        self._worker.request_cancel()

    def is_running(self) -> bool:
        return self._thread.isRunning()

    def wait(self, timeout_ms: int = 5000) -> bool:
        return self._thread.wait(timeout_ms)
