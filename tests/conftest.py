"""Pytest 共享 fixture."""

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def cleanup_qt_widgets():
    """每个测试结束后关闭所有顶层窗口，避免跨测试的 QObject/COM 状态污染."""
    yield
    app = QApplication.instance()
    if app is None:
        return
    for widget in list(app.topLevelWidgets()):
        try:
            widget.close()
            widget.deleteLater()
        except Exception:
            pass
    app.processEvents()
