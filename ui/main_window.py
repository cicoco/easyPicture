from __future__ import annotations

from PyQt6.QtCore import pyqtSignal as Signal, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                              QStatusBar, QMessageBox, QLabel)

from ui.canvas import Canvas
from ui.crop_panel import CropPanel
from ui.layer_panel import LayerPanel
from ui.sprite_panel import SpritePanel
from ui.toolbar import ToolBar


class MainWindow(QMainWindow):
    """应用主窗口。"""

    open_triggered = Signal()
    add_layer_triggered = Signal()
    clear_layers_triggered = Signal()
    export_triggered = Signal()
    undo_triggered = Signal()
    redo_triggered = Signal()
    trim_triggered = Signal()
    resize_triggered = Signal()
    sprite_preview_triggered = Signal()
    sprite_export_triggered = Signal()
    sprite_per_row_changed = Signal(int)

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

    @property
    def layer_panel(self) -> LayerPanel:
        return self._layer_panel

    @property
    def sprite_panel(self) -> SpritePanel:
        return self._sprite_panel

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

        # 中间竖向：画布 + 裁剪面板
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._canvas = Canvas()
        center_layout.addWidget(self._canvas, 1)

        self._crop_panel = CropPanel()
        center_layout.addWidget(self._crop_panel)

        self._sprite_panel = SpritePanel()
        center_layout.addWidget(self._sprite_panel)

        outer.addWidget(center, 1)

        self._layer_panel = LayerPanel()
        outer.addWidget(self._layer_panel)

        self._sprite_panel.preview_clicked.connect(self.sprite_preview_triggered)
        self._sprite_panel.export_clicked.connect(self.sprite_export_triggered)
        self._sprite_panel.per_row_changed.connect(self.sprite_per_row_changed)

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

        add_layer_action = QAction("添加图片为图层...", self)
        add_layer_action.setShortcut(
            QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_O)
        )
        add_layer_action.triggered.connect(self.add_layer_triggered)
        file_menu.addAction(add_layer_action)

        clear_layers_action = QAction("清空所有图层", self)
        clear_layers_action.setShortcut(
            QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.SHIFT | Qt.Key.Key_Delete)
        )
        clear_layers_action.setStatusTip("移除当前画布中的全部图层")
        clear_layers_action.triggered.connect(self.clear_layers_triggered)
        file_menu.addAction(clear_layers_action)

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

        # 图像菜单
        image_menu = menubar.addMenu("图像")

        self.trim_action = QAction("符合画布", self)
        self.trim_action.setStatusTip("裁去四周透明像素，保留主体内容的最小边界框")
        self.trim_action.triggered.connect(self.trim_triggered)
        image_menu.addAction(self.trim_action)

        self.resize_action = QAction("缩放图片...", self)
        self.resize_action.setShortcut(
            QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_R)
        )
        self.resize_action.setStatusTip("将图片重采样到指定像素尺寸")
        self.resize_action.triggered.connect(self.resize_triggered)
        image_menu.addAction(self.resize_action)

        # 视图菜单
        view_menu = menubar.addMenu("视图")

        self.toggle_layer_panel_action = QAction("显示图层栏", self)
        self.toggle_layer_panel_action.setCheckable(True)
        self.toggle_layer_panel_action.setChecked(True)
        self.toggle_layer_panel_action.setShortcut(
            QKeySequence(Qt.Modifier.CTRL | Qt.Modifier.ALT | Qt.Key.Key_L)
        )
        self.toggle_layer_panel_action.triggered.connect(
            self._layer_panel.setVisible
        )
        view_menu.addAction(self.toggle_layer_panel_action)

        view_menu.addSeparator()

        zoom_in_action = QAction("放大视图（不修改图片）", self)
        zoom_in_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Equal))
        zoom_in_action.setStatusTip("放大画布显示比例，图片像素数量不变")
        zoom_in_action.triggered.connect(self._canvas.zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction("缩小视图（不修改图片）", self)
        zoom_out_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_Minus))
        zoom_out_action.setStatusTip("缩小画布显示比例，图片像素数量不变")
        zoom_out_action.triggered.connect(self._canvas.zoom_out)
        view_menu.addAction(zoom_out_action)

        zoom_fit_action = QAction("适合窗口", self)
        zoom_fit_action.setShortcut(QKeySequence(Qt.Modifier.CTRL | Qt.Key.Key_0))
        zoom_fit_action.setStatusTip("自适应显示，图片像素数量不变")
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
                saved = self.controller.export_image()
                if saved:
                    event.accept()
                else:
                    event.ignore()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
