from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                              QLabel, QSlider, QPushButton, QDialogButtonBox)


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
