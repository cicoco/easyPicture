from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                              QLabel, QSlider, QPushButton, QDialogButtonBox,
                              QSpinBox, QDoubleSpinBox, QCheckBox, QFrame,
                              QButtonGroup, QRadioButton, QGroupBox)


class JpegQualityDialog(QDialog):
    """JPG 导出质量选择对话框。"""

    def __init__(self, parent=None, default_quality: int = 95) -> None:
        super().__init__(parent)
        self.setWindowTitle("导出 JPEG 质量")
        self.setFixedSize(320, 140)
        self._quality = default_quality

        layout = QVBoxLayout(self)

        self._label = QLabel(f"质量：{default_quality}")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(1, 100)
        self._slider.setValue(default_quality)
        self._slider.setTickInterval(10)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self._slider)

        hint = QLabel("1 = 体积最小 / 100 = 质量最佳")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_value_changed(self, value: int) -> None:
        self._quality = value
        self._label.setText(f"质量：{value}")

    @property
    def quality(self) -> int:
        return self._quality


class ResizeDialog(QDialog):
    """缩放到指定尺寸对话框。"""

    def __init__(self, orig_w: int, orig_h: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("缩放图片")
        self.setFixedWidth(340)
        self._orig_w = orig_w
        self._orig_h = orig_h
        self._ratio = orig_w / orig_h if orig_h else 1.0
        self._updating = False   # 防止信号循环

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # 原始尺寸提示
        orig_label = QLabel(f"原始尺寸：<b>{orig_w} × {orig_h}</b> 像素")
        orig_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(orig_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        layout.addWidget(line)

        # 缩放比例行（百分比输入，放在 W/H 上方）
        pct_row = QHBoxLayout()
        pct_row.addWidget(QLabel("缩放比例："))
        self._pct_spin = QDoubleSpinBox()
        self._pct_spin.setRange(0.1, 9999.0)
        self._pct_spin.setValue(100.0)
        self._pct_spin.setSuffix(" %")
        self._pct_spin.setDecimals(1)
        self._pct_spin.setFixedWidth(110)
        pct_row.addWidget(self._pct_spin)
        pct_row.addStretch()
        layout.addLayout(pct_row)

        # 表单：宽度 / 锁比 / 高度
        form = QFormLayout()
        form.setHorizontalSpacing(12)

        self._w_spin = QSpinBox()
        self._w_spin.setRange(1, 99999)
        self._w_spin.setValue(orig_w)
        self._w_spin.setSuffix(" px")
        form.addRow("宽度：", self._w_spin)

        self._lock_check = QCheckBox("锁定宽高比")
        self._lock_check.setChecked(True)
        form.addRow("", self._lock_check)

        self._h_spin = QSpinBox()
        self._h_spin.setRange(1, 99999)
        self._h_spin.setValue(orig_h)
        self._h_spin.setSuffix(" px")
        form.addRow("高度：", self._h_spin)

        layout.addLayout(form)

        # 实际输出尺寸预览（等比时显示实际结果）
        self._result_label = QLabel()
        self._result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._result_label)
        self._update_result_label()

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 连接信号
        self._w_spin.valueChanged.connect(self._on_w_changed)
        self._h_spin.valueChanged.connect(self._on_h_changed)
        self._pct_spin.valueChanged.connect(self._on_pct_changed)
        self._lock_check.toggled.connect(self._on_lock_toggled)

    # ------------------------------------------------------------------

    def _on_w_changed(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        if self._lock_check.isChecked():
            new_h = max(1, int(round(value / self._ratio)))
            self._h_spin.setValue(new_h)
        pct = value / self._orig_w * 100.0
        self._pct_spin.setValue(round(pct, 1))
        self._update_result_label()
        self._updating = False

    def _on_h_changed(self, value: int) -> None:
        if self._updating:
            return
        self._updating = True
        if self._lock_check.isChecked():
            new_w = max(1, int(round(value * self._ratio)))
            self._w_spin.setValue(new_w)
        pct = value / self._orig_h * 100.0
        self._pct_spin.setValue(round(pct, 1))
        self._update_result_label()
        self._updating = False

    def _on_pct_changed(self, value: float) -> None:
        if self._updating:
            return
        self._updating = True
        new_w = max(1, int(round(self._orig_w * value / 100.0)))
        new_h = max(1, int(round(self._orig_h * value / 100.0)))
        self._w_spin.setValue(new_w)
        self._h_spin.setValue(new_h)
        self._update_result_label()
        self._updating = False

    def _on_lock_toggled(self, locked: bool) -> None:
        if locked:
            # 锁定时以宽度为准，重算高度
            self._on_w_changed(self._w_spin.value())

    def _update_result_label(self) -> None:
        w = self._w_spin.value()
        h = self._h_spin.value()
        self._result_label.setText(f"输出尺寸：{w} × {h} 像素")

    # ------------------------------------------------------------------

    def get_values(self) -> dict | None:
        """exec() 后调用，返回 {'w', 'h', 'keep_aspect'} 或 None（取消）。"""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return {
            "w": self._w_spin.value(),
            "h": self._h_spin.value(),
            "keep_aspect": self._lock_check.isChecked(),
        }


class AiClarifyDialog(QDialog):
    """AI 变清晰对话框：选择放大倍率（2x/4x）和去噪强度。"""

    def __init__(self, orig_w: int, orig_h: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AI 变清晰")
        self.setFixedWidth(360)
        self._orig_w = orig_w
        self._orig_h = orig_h
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 原始尺寸提示
        orig_label = QLabel(f"当前尺寸：<b>{self._orig_w} × {self._orig_h}</b> 像素")
        orig_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(orig_label)

        # 分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        layout.addWidget(line)

        # 放大倍率选择
        scale_group = QGroupBox("放大倍率")
        scale_layout = QHBoxLayout(scale_group)
        self._radio_2x = QRadioButton("2x")
        self._radio_4x = QRadioButton("4x")
        self._radio_2x.setChecked(True)
        self._btn_group = QButtonGroup(self)
        self._btn_group.addButton(self._radio_2x)
        self._btn_group.addButton(self._radio_4x)
        scale_layout.addWidget(self._radio_2x)
        scale_layout.addWidget(self._radio_4x)
        scale_layout.addStretch()
        layout.addWidget(scale_group)

        # 输出尺寸预览
        self._size_label = QLabel()
        self._size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._size_label.setStyleSheet("color: #4acd80; font-size: 12px; font-weight: bold;")
        layout.addWidget(self._size_label)

        # 去噪强度滑块
        denoise_group = QGroupBox("去噪强度")
        denoise_layout = QVBoxLayout(denoise_group)

        self._denoise_slider = QSlider(Qt.Orientation.Horizontal)
        self._denoise_slider.setRange(0, 100)
        self._denoise_slider.setValue(50)
        self._denoise_slider.setTickInterval(25)
        self._denoise_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        denoise_layout.addWidget(self._denoise_slider)

        self._denoise_label = QLabel("0.50  — 均衡模式")
        self._denoise_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._denoise_label.setStyleSheet("color: #aaa; font-size: 11px;")
        denoise_layout.addWidget(self._denoise_label)

        hint = QLabel("0 = 保留纹理颗粒   /   1 = 强力去噪（适合老照片）")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #777; font-size: 10px;")
        denoise_layout.addWidget(hint)

        layout.addWidget(denoise_group)

        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("开始处理")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 连接信号
        self._radio_2x.toggled.connect(self._update_size_label)
        self._radio_4x.toggled.connect(self._update_size_label)
        self._denoise_slider.valueChanged.connect(self._update_denoise_label)

        self._update_size_label()
        self._update_denoise_label(50)

    def _update_size_label(self) -> None:
        scale = 2 if self._radio_2x.isChecked() else 4
        out_w, out_h = self._orig_w * scale, self._orig_h * scale
        self._size_label.setText(
            f"{self._orig_w}×{self._orig_h}  →  {out_w}×{out_h} 像素"
        )

    def _update_denoise_label(self, value: int) -> None:
        strength = value / 100.0
        if strength < 0.3:
            desc = "弱去噪，保留纹理颗粒"
        elif strength < 0.7:
            desc = "均衡模式"
        else:
            desc = "强去噪，适合噪点图"
        self._denoise_label.setText(f"{strength:.2f}  — {desc}")

    def get_values(self) -> dict | None:
        """显示对话框并返回用户选择，取消返回 None。"""
        if self.exec() != QDialog.DialogCode.Accepted:
            return None
        return {
            "scale": 2 if self._radio_2x.isChecked() else 4,
            "denoise": self._denoise_slider.value() / 100.0,
        }


def _ndarray_to_qpixmap(img: np.ndarray) -> QPixmap:
    h, w = img.shape[:2]
    rgba = np.ascontiguousarray(img[:, :, [2, 1, 0, 3]])
    qimg = QImage(rgba.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


class SpritePreviewDialog(QDialog):
    """雪碧图预览对话框：播放逐帧动画。"""

    def __init__(self, frames: list[np.ndarray], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("雪碧图预览")
        self.resize(640, 420)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("雪碧图播放预览")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        self._anim_label = QLabel()
        self._anim_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._anim_label.setMinimumHeight(280)
        self._anim_label.setStyleSheet("background:#1f1f1f; border:1px solid #3d3d3d;")
        layout.addWidget(self._anim_label)

        hint = QLabel("播放顺序：按图层顺序（底层 -> 顶层）")
        hint.setStyleSheet("color:#999; font-size:11px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        ctrl_row = QHBoxLayout()
        ctrl_row.addStretch()
        ctrl_row.addWidget(QLabel("播放间隔："))
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(16, 2000)
        self._interval_spin.setValue(500)
        self._interval_spin.setSuffix(" ms")
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        ctrl_row.addWidget(self._interval_spin)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        self._frames = frames
        self._frame_idx = 0

        self._timer_id = self.startTimer(self._interval_spin.value())
        self._update_anim_frame()

    def timerEvent(self, event) -> None:
        if not self._frames:
            return
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        self._update_anim_frame()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_anim_frame()

    def closeEvent(self, event) -> None:
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None
        super().closeEvent(event)

    def _on_interval_changed(self, value: int) -> None:
        if self._timer_id is not None:
            self.killTimer(self._timer_id)
        self._timer_id = self.startTimer(max(16, value))

    def _update_anim_frame(self) -> None:
        if not self._frames:
            self._anim_label.setText("无可播放帧")
            return
        frame = self._frames[self._frame_idx]
        pix = _ndarray_to_qpixmap(frame)
        self._anim_label.setPixmap(
            pix.scaled(
                self._anim_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
