from __future__ import annotations

from PyQt6.QtCore import pyqtSignal as Signal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpinBox, QPushButton


class SpritePanel(QWidget):
    """雪碧图底部面板：每行帧数设置、预览播放与导出。"""

    per_row_changed = Signal(int)
    preview_clicked = Signal()
    export_clicked = Signal()
    closed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self._init_ui()
        self.hide()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background: #2b2b2b;
                border-top: 1px solid #444;
            }
            QLabel {
                color: #bbb;
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
                min-width: 72px;
                font-size: 12px;
            }
            QPushButton {
                border-radius: 5px;
                font-size: 12px;
                padding: 4px 12px;
                border: 1px solid #555;
                color: #eee;
                background: #3c3c3c;
            }
            QPushButton:hover { background: #4a4a4a; }
            QPushButton#btn_preview {
                background: #1e6fa5;
                border-color: #3a9bd5;
                font-weight: bold;
            }
            QPushButton#btn_preview:hover { background: #2480be; }
            QPushButton#btn_export {
                background: #2e7d32;
                border-color: #4caf50;
            }
            QPushButton#btn_export:hover { background: #388e3c; }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        layout.addWidget(QLabel("雪碧图：每行"))
        self._spin_per_row = QSpinBox()
        self._spin_per_row.setRange(1, 999)
        self._spin_per_row.setValue(4)
        self._spin_per_row.valueChanged.connect(self.per_row_changed)
        layout.addWidget(self._spin_per_row)
        layout.addWidget(QLabel("帧"))

        self._info = QLabel("未就绪")
        self._info.setStyleSheet("color:#888; font-size:11px;")
        layout.addWidget(self._info)
        layout.addStretch()

        btn_preview = QPushButton("▶ 预览播放")
        btn_preview.setObjectName("btn_preview")
        btn_preview.clicked.connect(self.preview_clicked)
        layout.addWidget(btn_preview)

        btn_export = QPushButton("↓ 导出雪碧图")
        btn_export.setObjectName("btn_export")
        btn_export.clicked.connect(self.export_clicked)
        layout.addWidget(btn_export)

        btn_close = QPushButton("✕ 关闭")
        btn_close.clicked.connect(self.closed)
        layout.addWidget(btn_close)

    @property
    def per_row(self) -> int:
        return self._spin_per_row.value()

    def set_per_row(self, value: int) -> None:
        value = max(1, value)
        if self._spin_per_row.value() != value:
            self._spin_per_row.setValue(value)

    def set_info(self, text: str) -> None:
        self._info.setText(text)
