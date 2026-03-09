from __future__ import annotations
from enum import IntEnum

from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QFrame, QLabel


class CanvasTool(IntEnum):
    NONE = 0
    SELECT = 1
    CROP = 2
    GRABCUT = 3


class ToolBar(QWidget):
    """左侧竖向工具栏。"""

    tool_selected = Signal(int)       # CanvasTool 枚举值
    crop_clicked = Signal()
    delete_clicked = Signal()
    grabcut_clicked = Signal()
    rotate_cw_clicked = Signal()
    rotate_ccw_clicked = Signal()

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
        select_label = QLabel("选择")
        layout.addWidget(select_label)

        # 矩形选框
        btn_select = self._make_tool_btn("⬚\n选框", CanvasTool.SELECT)
        layout.addWidget(btn_select)

        # 裁剪
        btn_crop = self._make_tool_btn("✂\n裁剪", CanvasTool.CROP)
        layout.addWidget(btn_crop)

        # 抠图
        btn_grabcut = self._make_tool_btn("✦\n抠图", CanvasTool.GRABCUT)
        layout.addWidget(btn_grabcut)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        layout.addWidget(line)

        action_label = QLabel("操作")
        layout.addWidget(action_label)

        # 删除选区（动作按钮，无选中态）
        btn_delete = QPushButton("🗑\n删除")
        btn_delete.setFixedHeight(50)
        btn_delete.setToolTip("删除选区内容 (Delete)")
        btn_delete.clicked.connect(self.delete_clicked)
        layout.addWidget(btn_delete)

        # 分隔线
        line2 = QFrame()
        line2.setFrameShape(QFrame.Shape.HLine)
        line2.setStyleSheet("color: #444;")
        layout.addWidget(line2)

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

        layout.addStretch()

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
