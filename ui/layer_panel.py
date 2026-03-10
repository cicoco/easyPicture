from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                              QListWidget, QListWidgetItem,
                              QAbstractItemView)


class LayerPanel(QWidget):
    """右侧图层清单面板。"""

    layer_selected = Signal(int)  # 图层索引（底=0，顶=n-1）
    layer_visibility_toggled = Signal(int, bool)  # (idx, visible)
    layer_order_changed = Signal(list)  # 新顺序（底->顶）的旧索引列表

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(280)
        self._updating = False
        self._init_ui()

    def _init_ui(self) -> None:
        self.setStyleSheet("""
            QWidget {
                background: #242424;
                border-left: 1px solid #3c3c3c;
            }
            QLabel {
                color: #bbb;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 10px 4px 10px;
                border: none;
                background: transparent;
            }
            QListWidget {
                background: #1f1f1f;
                color: #ddd;
                border: 1px solid #3e3e3e;
                margin: 6px 8px 8px 8px;
                font-size: 12px;
            }
            QListWidget::item {
                border: 1px solid transparent;
                padding: 6px 8px;
            }
            QListWidget::item:selected {
                background: #1e6fa5;
                color: white;
                border-color: #3a9bd5;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title = QLabel("图层")
        layout.addWidget(title)

        self._list = QListWidget()
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setDragEnabled(True)
        self._list.setAcceptDrops(True)
        self._list.setDropIndicatorShown(True)
        self._list.currentItemChanged.connect(self._on_current_item_changed)
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._list, 1)

    def set_layers(self, layers: list[dict], active_idx: int) -> None:
        """刷新图层列表。显示顺序：上层在前。"""
        self._updating = True
        self._list.clear()

        # 显示顺序：底层在上，顶层在下（越上面的图层越靠底部）
        for idx in range(len(layers)):
            layer = layers[idx]
            w = layer["image"].shape[1]
            h = layer["image"].shape[0]
            line1 = layer["name"]
            line2 = f"{w}×{h}  位置({layer['x']}, {layer['y']})"
            if not layer.get("visible", True):
                line1 = f"[隐藏] {line1}"

            item = QListWidgetItem(f"{line1}\n{line2}")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(
                Qt.CheckState.Checked if layer.get("visible", True)
                else Qt.CheckState.Unchecked
            )
            source_path = layer.get("source_path")
            if source_path:
                item.setToolTip(source_path)
            self._list.addItem(item)

            if idx == active_idx:
                self._list.setCurrentItem(item)

        self._updating = False

    def set_active_layer(self, active_idx: int) -> None:
        """按图层索引更新列表选中。"""
        self._updating = True
        for row in range(self._list.count()):
            item = self._list.item(row)
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx == active_idx:
                self._list.setCurrentItem(item)
                break
        self._updating = False

    def _on_current_item_changed(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        if self._updating or current is None:
            return
        idx = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(idx, int):
            self.layer_selected.emit(idx)

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._updating or item is None:
            return
        idx = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(idx, int):
            return
        visible = item.checkState() == Qt.CheckState.Checked
        self.layer_visibility_toggled.emit(idx, visible)

    def _on_rows_moved(self, *_args) -> None:
        if self._updating:
            return
        order: list[int] = []
        for row in range(self._list.count()):
            item = self._list.item(row)
            idx = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(idx, int):
                order.append(idx)
        if order:
            self.layer_order_changed.emit(order)
