import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from lisktranslate.app import MainWindow


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


def main() -> None:
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
