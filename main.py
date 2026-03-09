import signal
import sys

from PyQt6.QtWidgets import QApplication

from controller.app_controller import AppController
from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("EasyPicture")
    app.setOrganizationName("EasyPicture")

    # 恢复默认 SIGINT 处理，使 Ctrl+C 能正常终止 Qt 事件循环
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = MainWindow()
    controller = AppController(window)
    window.controller = controller

    window.show()
    window.raise_()          # 确保窗口置于最前
    window.activateWindow()  # 主动获取系统焦点，避免 macOS 首次点击只激活不触发
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
