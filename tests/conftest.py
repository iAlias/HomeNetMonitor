"""Pytest configuration: mock PyQt6 when not installed so core-logic tests run."""
from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _mock_pyqt6() -> None:
    """Insert lightweight stubs for PyQt6 modules into sys.modules."""
    if "PyQt6" in sys.modules:
        return  # already installed — nothing to do

    # Base stubs
    pyqt6 = ModuleType("PyQt6")
    qtcore = ModuleType("PyQt6.QtCore")
    qtwidgets = ModuleType("PyQt6.QtWidgets")
    qtgui = ModuleType("PyQt6.QtGui")

    # QThread stub that behaves like a real thread for testing
    class _QThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def wait(self, msecs=0):
            pass

        def isRunning(self):
            return False

    class _pyqtSignal:
        """Minimal pyqtSignal replacement that records connections."""

        def __init__(self, *args):
            self._callbacks = []

        def connect(self, cb):
            self._callbacks.append(cb)

        def emit(self, *args):
            for cb in self._callbacks:
                cb(*args)

        def __call__(self, *args):
            return self

    qtcore.QThread = _QThread
    qtcore.pyqtSignal = _pyqtSignal
    qtcore.QTimer = MagicMock()
    qtcore.Qt = MagicMock()

    qtwidgets.QWidget = MagicMock()
    qtwidgets.QMainWindow = MagicMock()

    qtgui.QIcon = MagicMock()
    qtgui.QColor = MagicMock()

    pyqt6.QtCore = qtcore
    pyqt6.QtWidgets = qtwidgets
    pyqt6.QtGui = qtgui

    sys.modules["PyQt6"] = pyqt6
    sys.modules["PyQt6.QtCore"] = qtcore
    sys.modules["PyQt6.QtWidgets"] = qtwidgets
    sys.modules["PyQt6.QtGui"] = qtgui


_mock_pyqt6()
