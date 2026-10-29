"""Small shared types for long-running operations."""

from __future__ import annotations

from typing import Any, Callable

ProgressCallback = Callable[[Any], None]
CancelCheck = Callable[[], bool]


class OperationCancelled(Exception):
    """Raised inside a long-running operation when the user presses Cancel."""


def never_cancelled() -> bool:
    return False


def ignore_progress(_: Any) -> None:
    pass
