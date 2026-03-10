from __future__ import annotations
from enum import IntEnum

from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QLabel, QSizePolicy


class CanvasTool(IntEnum):
    NONE = 0
    SELECT = 1
    CROP = 2
    GRABCUT = 3
    PAN = 4


class ToolBar(QWidget):
    """左侧竖向工具栏。"""

    tool_selected = Signal(int)       # CanvasTool 枚举值
    crop_clicked = Signal()
    delete_clicked = Signal()
    grabcut_clicked = Signal()
    rotate_cw_clicked = Signal()
    rotate_ccw_clicked = Signal()
    trim_clicked = Signal()
    resize_clicked = Signal()
    clarify_clicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(64)
        self._tool_buttons: dict[CanvasTool, QPushButton] = {}
        self._current_tool = CanvasTool.NONE
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 8, 4, 8)
        layout.setSpacing(4)

        self.setStyleSheet("""
            QWidget {
                background: #2b2b2b;
            }
            QPushButton {
                background: #3c3c3c;
                color: #cccccc;
                border: 1px solid #555;
                border-radius: 6px;
                font-size: 11px;
                padding: 6px 2px;
            }
            QPushButton:hover {
                background: #4a4a4a;
                border-color: #777;
            }
            QPushButton:checked {
                background: #1e6fa5;
                border-color: #3a9bd5;
                color: #ffffff;
            }
            QPushButton:pressed {
                background: #155a87;
            }
            QLabel {
                color: #666;
                font-size: 9px;
                qproperty-alignment: AlignCenter;
            }
        """)

        # 工具分组标题
        select_label = QLabel("视图")
        layout.addWidget(select_label)

        # 手型平移工具
        btn_pan = self._make_tool_btn("✋\n平移", CanvasTool.PAN)
        btn_pan.setToolTip("平移工具：拖拽移动画面（也可按住空格键临时切换）")
        layout.addWidget(btn_pan)

        layout.addWidget(self._make_divider())

        select_label2 = QLabel("选择")
        layout.addWidget(select_label2)

        # 矩形选框
        btn_select = self._make_tool_btn("⬚\n选框", CanvasTool.SELECT)
        layout.addWidget(btn_select)

        # 裁剪
        btn_crop = self._make_tool_btn("✂\n裁剪", CanvasTool.CROP)
        layout.addWidget(btn_crop)

        # 抠图（第一步：框选工具）
        btn_grabcut = self._make_tool_btn("✦\n抠图", CanvasTool.GRABCUT)
        btn_grabcut.setToolTip("第①步：点击激活，在图片上拖拽框选主体")
        layout.addWidget(btn_grabcut)

        # 抠图（第二步：执行按钮）
        self._btn_run_grabcut = QPushButton("▶\n执行")
        self._btn_run_grabcut.setFixedHeight(42)
        self._btn_run_grabcut.setToolTip("第②步：框选完成后点击，开始抠图")
        self._btn_run_grabcut.setEnabled(False)
        self._btn_run_grabcut.setStyleSheet("""
            QPushButton {
                background: #2b4a1e;
                color: #aaa;
                border: 1px solid #4a6e35;
                border-radius: 6px;
                font-size: 10px;
                padding: 4px 2px;
            }
            QPushButton:enabled {
                background: #2e7d32;
                color: #fff;
                border-color: #4caf50;
            }
            QPushButton:enabled:hover { background: #388e3c; }
            QPushButton:enabled:pressed { background: #1b5e20; }
        """)
        self._btn_run_grabcut.clicked.connect(self.grabcut_clicked)
        layout.addWidget(self._btn_run_grabcut)

        layout.addWidget(self._make_divider())

        action_label = QLabel("操作")
        layout.addWidget(action_label)

        # 删除选区（动作按钮，无选中态）
        btn_delete = QPushButton("🗑\n删除")
        btn_delete.setFixedHeight(50)
        btn_delete.setToolTip("删除选区内容 (Delete)")
        btn_delete.clicked.connect(self.delete_clicked)
        layout.addWidget(btn_delete)

        layout.addWidget(self._make_divider())

        rotate_label = QLabel("旋转")
        layout.addWidget(rotate_label)

        # 顺时针旋转
        btn_cw = QPushButton("↻\n顺时针")
        btn_cw.setFixedHeight(50)
        btn_cw.setToolTip("顺时针旋转 90°")
        btn_cw.clicked.connect(self.rotate_cw_clicked)
        layout.addWidget(btn_cw)

        # 逆时针旋转
        btn_ccw = QPushButton("↺\n逆时针")
        btn_ccw.setFixedHeight(50)
        btn_ccw.setToolTip("逆时针旋转 90°")
        btn_ccw.clicked.connect(self.rotate_ccw_clicked)
        layout.addWidget(btn_ccw)

        layout.addWidget(self._make_divider())

        image_label = QLabel("图像")
        layout.addWidget(image_label)

        # 符合画布
        btn_trim = QPushButton("⊡\n符合画布")
        btn_trim.setFixedHeight(50)
        btn_trim.setToolTip(
            "符合画布：裁去四周透明像素，保留主体内容最小边界框\n"
            "（不改变图片质量，仅裁掉空白区域）"
        )
        btn_trim.clicked.connect(self.trim_clicked)
        layout.addWidget(btn_trim)

        # 缩放到指定尺寸
        btn_resize = QPushButton("⇲\n改变尺寸")
        btn_resize.setFixedHeight(50)
        btn_resize.setToolTip(
            "改变图片尺寸（真正修改像素数量）\n"
            "⚠ 这会重新采样图片，与 Cmd+/- 的视图缩放不同\n"
            "缩小后像素减少，放大看会变模糊，可 Cmd+Z 撤销"
        )
        btn_resize.clicked.connect(self.resize_clicked)
        layout.addWidget(btn_resize)

        # AI 变清晰
        btn_clarify = QPushButton("✨\nAI变清晰")
        btn_clarify.setFixedHeight(50)
        btn_clarify.setToolTip(
            "AI 变清晰（Real-ESRGAN）\n"
            "使用 AI 超分辨率真正重建细节\n"
            "选择 2x 或 4x 放大，放大后可裁剪\n"
            "需要 models/RealESRGAN_x4plus_anime_6B.onnx\n"
            "（详见 models/README.md）"
        )
        btn_clarify.setStyleSheet("""
            QPushButton {
                background: #1a3a2a;
                color: #ccc;
                border: 1px solid #2d7a50;
                border-radius: 6px;
                font-size: 11px;
                padding: 6px 2px;
            }
            QPushButton:hover {
                background: #225c3c;
                border-color: #4acd80;
                color: #fff;
            }
            QPushButton:pressed { background: #112a1e; }
        """)
        btn_clarify.clicked.connect(self.clarify_clicked)
        layout.addWidget(btn_clarify)

        layout.addStretch()

    def _make_divider(self) -> QFrame:
        """创建水平分隔线。"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        return line

    def _make_tool_btn(self, label: str, tool: CanvasTool) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFixedHeight(50)
        btn.setToolTip(label.replace("\n", " "))
        btn.clicked.connect(lambda checked, t=tool: self._on_tool_clicked(t))
        self._tool_buttons[tool] = btn
        return btn

    def _on_tool_clicked(self, tool: CanvasTool) -> None:
        # 如果点击已选中的工具，取消选中
        if self._current_tool == tool:
            self._current_tool = CanvasTool.NONE
            self._tool_buttons[tool].setChecked(False)
            self.tool_selected.emit(int(CanvasTool.NONE))
            return

        # 取消其他工具的选中
        for t, btn in self._tool_buttons.items():
            btn.setChecked(t == tool)

        self._current_tool = tool
        self.tool_selected.emit(int(tool))

    def set_tool(self, tool: CanvasTool) -> None:
        """外部设置当前工具。"""
        self._current_tool = tool
        for t, btn in self._tool_buttons.items():
            btn.setChecked(t == tool)
        # 切离抠图工具时，重置执行按钮
        if tool != CanvasTool.GRABCUT:
            self._btn_run_grabcut.setEnabled(False)

    def set_grabcut_ready(self, has_selection: bool) -> None:
        """有选区时点亮执行按钮，无选区时置灰。"""
        self._btn_run_grabcut.setEnabled(
            has_selection and self._current_tool == CanvasTool.GRABCUT
        )
