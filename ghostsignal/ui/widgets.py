"""Small shared widget-building helpers for the left/right panels."""
from __future__ import annotations
from PyQt6.QtWidgets import QGroupBox, QVBoxLayout, QWidget


def labeled_group(title: str, inner: QWidget) -> QGroupBox:
    """Wrap ``inner`` in a titled QGroupBox with a single-widget vertical layout.

    Mirrors the repeated ``QGroupBox(title) + QVBoxLayout + addWidget`` pattern
    used throughout v1's ``_make_left_panel``/``_make_right_panel``.
    """
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.setContentsMargins(8, 4, 8, 8)
    layout.addWidget(inner)
    return box
