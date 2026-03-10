from __future__ import annotations

from PyQt6.QtCore import pyqtSignal as Signal, Qt
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel,
                              QSpinBox, QPushButton, QFrame)


class CropPanel(QWidget):
    """
    裁剪工具底部面板：显示/编辑当前选区的 X/Y/W/H，
    提供"确认裁剪"、"导出裁剪"、"取消"操作。
    """

    # 用户修改了数值框 → 通知 Canvas 同步选区
    values_changed = Signal(int, int, int, int)   # x1, y1, x2, y2（图像坐标）
    crop_confirmed = Signal()    # 确认裁剪（替换当前图像）
    crop_exported = Signal()     # 导出裁剪结果（不替换当前图像）
    crop_cancelled = Signal()    # 取消

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(48)
        self._updating = False   # 防止信号循环
        self._img_w = 0
        self._img_h = 0
        self._zoom_factor: float = 1.0
        self._init_ui()
        self.hide()  # 默认隐藏，切换到裁剪工具时才显示

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background: #2b2b2b;
                border-top: 1px solid #444;
            }
            QLabel {
                color: #aaa;
                font-size: 12px;
                background: transparent;
                border: none;
            }
            QSpinBox {
                background: #3c3c3c;
                color: #eee;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
                font-size: 12px;
                min-width: 64px;
            }
            QSpinBox:focus { border-color: #1e6fa5; }
            QPushButton {
                border-radius: 5px;
                font-size: 12px;
                padding: 4px 14px;
                border: 1px solid #555;
                color: #eee;
                background: #3c3c3c;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton#btn_confirm {
                background: #1e6fa5;
                border-color: #3a9bd5;
                font-weight: bold;
            }
            QPushButton#btn_confirm:hover { background: #2480be; }
            QPushButton#btn_export {
                background: #2e7d32;
                border-color: #4caf50;
            }
            QPushButton#btn_export:hover { background: #388e3c; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        layout.addWidget(QLabel("裁剪区域："))

        layout.addWidget(QLabel("X"))
        self._spin_x = self._make_spin()
        layout.addWidget(self._spin_x)

        layout.addWidget(QLabel("Y"))
        self._spin_y = self._make_spin()
        layout.addWidget(self._spin_y)

        layout.addWidget(QLabel("宽"))
        self._spin_w = self._make_spin()
        layout.addWidget(self._spin_w)

        layout.addWidget(QLabel("高"))
        self._spin_h = self._make_spin()
        layout.addWidget(self._spin_h)

        # 尺寸提示（同时显示原图像素和视图像素）
        self._hint = QLabel("在图片上拖拽框选裁剪区域")
        self._hint.setStyleSheet("color: #888; font-size: 11px; background:transparent; border:none;")
        layout.addWidget(self._hint)

        layout.addStretch()

        # 分隔线
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #444; border: none; background: #444;")
        sep.setFixedWidth(1)
        layout.addWidget(sep)

        btn_confirm = QPushButton("✓ 确认裁剪")
        btn_confirm.setObjectName("btn_confirm")
        btn_confirm.setToolTip("将图像裁剪为当前选区（Ctrl+Enter）")
        btn_confirm.clicked.connect(self.crop_confirmed)
        layout.addWidget(btn_confirm)

        btn_export = QPushButton("↓ 导出裁剪")
        btn_export.setObjectName("btn_export")
        btn_export.setToolTip("将裁剪区域另存为新文件，不修改当前图像")
        btn_export.clicked.connect(self.crop_exported)
        layout.addWidget(btn_export)

        btn_cancel = QPushButton("✕ 取消")
        btn_cancel.setToolTip("取消裁剪（Esc）")
        btn_cancel.clicked.connect(self.crop_cancelled)
        layout.addWidget(btn_cancel)

    def _make_spin(self) -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(0, 99999)
        sb.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        sb.valueChanged.connect(self._on_spin_changed)
        return sb

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def set_image_size(self, w: int, h: int) -> None:
        """设置当前图像尺寸，用于 spinbox 范围限制。"""
        self._img_w = w
        self._img_h = h
        self._updating = True
        self._spin_x.setMaximum(max(0, w - 1))
        self._spin_y.setMaximum(max(0, h - 1))
        self._spin_w.setMaximum(w)
        self._spin_h.setMaximum(h)
        self._updating = False

    def set_zoom(self, zoom_factor: float) -> None:
        """由 Canvas zoom_changed 信号触发，更新视图尺寸提示。"""
        self._zoom_factor = zoom_factor
        self._update_hint()

    def set_selection(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """由 Canvas/Controller 调用，同步选区到数值框。"""
        self._updating = True
        self._spin_x.setValue(x1)
        self._spin_y.setValue(y1)
        self._spin_w.setValue(max(1, x2 - x1))
        self._spin_h.setValue(max(1, y2 - y1))
        self._updating = False
        self._update_hint()

    def get_selection(self) -> tuple[int, int, int, int]:
        """返回当前 spinbox 的选区 (x1, y1, x2, y2)。"""
        x1 = self._spin_x.value()
        y1 = self._spin_y.value()
        w = self._spin_w.value()
        h = self._spin_h.value()
        return x1, y1, x1 + w, y1 + h

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _on_spin_changed(self) -> None:
        if self._updating:
            return
        # W/H 不能超出图像边界
        x1 = self._spin_x.value()
        y1 = self._spin_y.value()
        w = self._spin_w.value()
        h = self._spin_h.value()
        if self._img_w > 0:
            w = min(w, self._img_w - x1)
            h = min(h, self._img_h - y1)
        self._updating = True
        self._spin_w.setValue(max(1, w))
        self._spin_h.setValue(max(1, h))
        self._updating = False
        self.values_changed.emit(x1, y1, x1 + w, y1 + h)
        self._update_hint()

    def _update_hint(self) -> None:
        """根据当前选区尺寸和缩放比，更新提示标签。"""
        w = self._spin_w.value()
        h = self._spin_h.value()
        if w <= 0 or h <= 0:
            self._hint.setText("在图片上拖拽框选裁剪区域")
            self._hint.setStyleSheet(
                "color: #666; font-size: 11px; background:transparent; border:none;")
            return

        z = self._zoom_factor
        if abs(z - 1.0) < 0.01:
            # 缩放接近 100%，只显示原图尺寸
            self._hint.setText(f"裁剪结果：{w} × {h} px")
            self._hint.setStyleSheet(
                "color: #aaa; font-size: 11px; background:transparent; border:none;")
        else:
            # 显示视图尺寸（当前屏幕上看到的像素数）和原图尺寸
            vw = int(round(w * z))
            vh = int(round(h * z))
            pct = int(round(z * 100))
            self._hint.setText(
                f"裁剪结果：{w} × {h} px（当前 {pct}% 视图下看起来是 {vw} × {vh} px）"
            )
            color = "#f0a030" if z > 1.0 else "#888"
            self._hint.setStyleSheet(
                f"color: {color}; font-size: 11px; background:transparent; border:none;")
