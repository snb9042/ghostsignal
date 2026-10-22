"""Session-wide pytest setup.

PyQt6's WebEngine binding requires ``QtWebEngineWidgets`` (or
``Qt.AA_ShareOpenGLContexts``) to be imported/set *before* the first
``QCoreApplication``/``QApplication`` instance is created, in the whole
process — not just within the module that uses it. Several test modules
each independently create a `QApplication` at import time (as instructed by
their task briefs), and pytest's collection order interleaves them with
``tests/test_ui_import.py`` (which needs QtWebEngineWidgets). Importing it
once, here, before any test module is collected, makes the suite's result
independent of collection order.
"""
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
