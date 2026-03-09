from __future__ import annotations

from PyQt6.QtCore import pyqtSignal as Signal, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                              QStatusBar, QMessageBox, QLabel)

from ui.canvas import Canvas
from ui.crop_panel import CropPanel
from ui.toolbar import ToolBar


class MainWindow(QMainWindow):
    """应用主窗口。"""

    open_triggered = Signal()
    export_triggered = Signal()
    undo_triggered = Signal()
    redo_triggered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("EasyPicture")
        self.resize(1280, 800)
        self.controller = None   # 由外部注入

        self._init_ui()
        self._init_menu()
        self._init_status_bar()

    # ------------------------------------------------------------------
    # 公开组件引用
    # ------------------------------------------------------------------

    @property
    def canvas(self) -> Canvas:
        return self._canvas

    @property
    def toolbar(self) -> ToolBar:
        return self._toolbar

    @property
    def crop_panel(self) -> CropPanel:
        return self._crop_panel

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        # 外层横向：左工具栏 + 右侧区域
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._toolbar = ToolBar()
        outer.addWidget(self._toolbar)

        # 右侧竖向：画布 + 裁剪面板
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self._canvas = Canvas()
        right_layout.addWidget(self._canvas, 1)

        self._crop_panel = CropPanel()
        right_layout.addWidget(self._crop_panel)

        outer.addWidget(right, 1)

        self.setStyleSheet("""
            QMainWindow { background: #1a1a1a; }
            QMenuBar {
                background: #2b2b2b;
                color: #ccc;
                border-bottom: 1px solid #444;
                padding: 2px;
            }
            QMenuBar::item:selected { background: #3a3a3a; }
            QMenu {
                background: #2b2b2b;
                color: #ccc;
                border: 1px solid #555;
            }
            QMenu::item:selected { background: #1e6fa5; }
            QStatusBar {
                background: #2b2b2b;
                color: #aaa;
                border-top: 1px solid #444;
                font-size: 12px;
                padding: 2px 8px;
            }
        """)

    def _init_menu(self) -> None:
        menubar = self.menuBar()

        # 文件菜单
        file_menu = menubar.addMenu("文件")

        open_action = QAction("打开...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_triggered)
        file_menu.addAction(open_action)

        self.export_action = QAction("导出...", self)
        self.export_action.setShortcut(QKeySequence.StandardKey.Save)
        self.export_action.triggered.connect(self.export_triggered)
        file_menu.addAction(self.export_action)

        file_menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # 编辑菜单
        edit_menu = menubar.addMenu("编辑")

        self.undo_action = QAction("撤销", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.setEnabled(False)
        self.undo_action.triggered.connect(self.undo_triggered)
        edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("重做", self)
        self.redo_action.setShortcuts([
            QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Y),
            QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_Z),
        ])
        self.redo_action.setEnabled(False)
        self.redo_action.triggered.connect(self.redo_triggered)
        edit_menu.addAction(self.redo_action)

        edit_menu.addSeparator()

        rotate_cw_action = QAction("顺时针旋转 90°", self)
        rotate_cw_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_BracketRight))
        rotate_cw_action.triggered.connect(self._toolbar.rotate_cw_clicked)
        edit_menu.addAction(rotate_cw_action)

        rotate_ccw_action = QAction("逆时针旋转 90°", self)
        rotate_ccw_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_BracketLeft))
        rotate_ccw_action.triggered.connect(self._toolbar.rotate_ccw_clicked)
        edit_menu.addAction(rotate_ccw_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图")

        zoom_in_action = QAction("放大", self)
        zoom_in_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Equal))
        zoom_in_action.triggered.connect(self._canvas.zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("缩小", self)
        zoom_out_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Minus))
        zoom_out_action.triggered.connect(self._canvas.zoom_out)
        view_menu.addAction(zoom_out_action)

        zoom_fit_action = QAction("适合窗口", self)
        zoom_fit_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_0))
        zoom_fit_action.triggered.connect(self._canvas.zoom_fit)
        view_menu.addAction(zoom_fit_action)

    def _init_status_bar(self) -> None:
        sb = self.statusBar()

        self._status_size = QLabel("未打开图片")
        self._status_zoom = QLabel("")
        self._status_tool = QLabel("")

        sb.addWidget(self._status_size)
        sb.addPermanentWidget(self._status_tool)
        sb.addPermanentWidget(self._status_zoom)

        # 缩放变化时自动更新
        self._canvas.zoom_changed.connect(self._on_zoom_changed)

    # ------------------------------------------------------------------
    # 状态栏更新
    # ------------------------------------------------------------------

    def update_image_info(self, width: int, height: int) -> None:
        self._status_size.setText(f"  {width} × {height} px")

    def update_zoom(self, zoom: float) -> None:
        self._status_zoom.setText(f"{int(zoom * 100)}%  ")

    def update_tool(self, tool_name: str) -> None:
        self._status_tool.setText(f"工具：{tool_name}  ")

    def show_message(self, msg: str, timeout: int = 3000) -> None:
        self.statusBar().showMessage(msg, timeout)

    def _on_zoom_changed(self, zoom: float) -> None:
        self.update_zoom(zoom)

    # ------------------------------------------------------------------
    # 关闭确认
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self.controller and self.controller.model.is_dirty:
            msg = QMessageBox(self)
            msg.setWindowTitle("未保存的修改")
            msg.setText("图片有未保存的修改，是否在退出前保存？")
            msg.setStandardButtons(
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            # 将窗口 X 按钮映射为"取消"，这样点 X 也能关闭对话框
            msg.setDefaultButton(QMessageBox.StandardButton.Save)
            msg.setEscapeButton(QMessageBox.StandardButton.Cancel)
            reply = msg.exec()
            if reply == QMessageBox.StandardButton.Save:
                self.controller.export_image()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
