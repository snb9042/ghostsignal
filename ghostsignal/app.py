"""Application bootstrap: build the QApplication, apply v1's theme
(stylesheet + dark palette), show :class:`MainWindow`, and run the event loop.
"""
from __future__ import annotations

import sys
import importlib.resources as res

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor, QPalette

from .ui.main_window import MainWindow, APP_NAME, APP_VERSION


def _load_style_qss() -> str:
    return (res.files("ghostsignal.ui") / "assets" / "style.qss").read_text(encoding="utf-8")


def _dark_palette() -> QPalette:
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#090b0f"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#131920"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#0d1117"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#131920"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#131920"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#00ffa3"))
    pal.setColor(QPalette.ColorRole.Link, QColor("#00ffa3"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#00ffa3"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#090b0f"))
    return pal


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(_load_style_qss())
    app.setPalette(_dark_palette())

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
