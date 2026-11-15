import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication

from lisktranslate.app import MainWindow


def _app_id() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Lisk.LiskTranslate")


def _dark(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#1e1f22"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#ececec"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#17181b"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1e1f22"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#ececec"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2a2b30"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ececec"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3f6f5b"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1e1f22"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#ececec"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8b8d93"))
    app.setPalette(palette)
    icon = Path(__file__).with_name("icon.png")
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))


def main() -> None:
    _app_id()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("LiskTranslate")
    app.setFont(QFont("Yu Gothic UI", 10))
    _dark(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
