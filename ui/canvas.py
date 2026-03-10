from __future__ import annotations
from typing import Optional, Tuple

import numpy as np
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal as Signal
from PyQt6.QtGui import (QColor, QImage, QPainter, QPen, QPixmap,
                          QWheelEvent, QKeyEvent, QMouseEvent,
                          QDragEnterEvent, QDropEvent)
from PyQt6.QtWidgets import QWidget

from ui.toolbar import CanvasTool

# 8 个缩放手柄索引
_TL, _TC, _TR, _RC, _BR, _BC, _BL, _LC = range(8)

# 手柄对应的光标
_HANDLE_CURSORS = {
    _TL: Qt.CursorShape.SizeFDiagCursor,
    _TC: Qt.CursorShape.SizeVerCursor,
    _TR: Qt.CursorShape.SizeBDiagCursor,
    _RC: Qt.CursorShape.SizeHorCursor,
    _BR: Qt.CursorShape.SizeFDiagCursor,
    _BC: Qt.CursorShape.SizeVerCursor,
    _BL: Qt.CursorShape.SizeBDiagCursor,
    _LC: Qt.CursorShape.SizeHorCursor,
}

HANDLE_SIZE = 8   # 手柄正方形边长（画布像素）


def ndarray_to_qpixmap(img: np.ndarray) -> QPixmap:
    """将 BGRA numpy 数组转换为 QPixmap。"""
    h, w = img.shape[:2]
    if img.shape[2] == 4:
        rgba = np.ascontiguousarray(img[:, :, [2, 1, 0, 3]])  # BGRA → RGBA
        qimg = QImage(rgba.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888)
    else:
        rgb = np.ascontiguousarray(img[:, :, ::-1])  # BGR → RGB
        qimg = QImage(rgb.tobytes(), w, h, w * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)


class Canvas(QWidget):
    """画布组件：图片显示 + 鼠标交互（选区、缩放、平移）。"""

    selection_changed = Signal(int, int, int, int)  # (x1, y1, x2, y2) 图像坐标
    selection_cleared = Signal()
    delete_key_pressed = Signal()
    file_dropped = Signal(str)
    zoom_changed = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.setStyleSheet("background: #1a1a1a;")
        self.setMouseTracking(True)   # 需要 tracking 才能在不按键时更新光标

        self._pixmap: Optional[QPixmap] = None
        self._image_width: int = 0
        self._image_height: int = 0
        self.zoom_factor: float = 1.0
        self._pan_offset: QPoint = QPoint(0, 0)
        self._pan_start: Optional[QPoint] = None
        self._space_held: bool = False
        # 用户是否手动调整过缩放；False 时 resizeEvent 才会自动 zoom_fit
        self._user_zoomed: bool = False

        self._tool: CanvasTool = CanvasTool.NONE

        # 拖拽新建选区
        self._drag_start: Optional[QPoint] = None   # 画布坐标（新建时用）
        self._drag_end: Optional[QPoint] = None

        # 已确定的选区（图像坐标）
        self._selection_rect: Optional[Tuple[int, int, int, int]] = None

        # 移动/缩放已有选区的状态
        # _crop_drag_mode: "none" | "draw" | "move" | "resize"
        self._crop_drag_mode: str = "none"
        self._crop_handle_idx: int = -1          # 当前拖拽的手柄索引
        self._crop_drag_origin: Optional[QPoint] = None   # 按下时的画布坐标
        self._crop_rect_origin: Optional[Tuple[int, int, int, int]] = None  # 按下时的选区

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    @property
    def image_width(self) -> int:
        return self._image_width

    @property
    def image_height(self) -> int:
        return self._image_height

    def set_image(self, img: np.ndarray) -> None:
        self._image_width = img.shape[1]
        self._image_height = img.shape[0]
        self._pixmap = ndarray_to_qpixmap(img)
        self._selection_rect = None
        self._drag_start = None
        self._drag_end = None
        self._user_zoomed = False   # 新图加载后允许自动 fit
        self.zoom_fit()

    def refresh(self, img: np.ndarray) -> None:
        self._image_width = img.shape[1]
        self._image_height = img.shape[0]
        self._pixmap = ndarray_to_qpixmap(img)
        self.update()

    def clear_selection(self) -> None:
        self._selection_rect = None
        self._drag_start = None
        self._drag_end = None
        self._crop_drag_mode = "none"
        self.update()

    def set_selection_from_panel(self, x1: int, y1: int,
                                  x2: int, y2: int) -> None:
        """由 CropPanel 数值框触发，更新选区并重绘（不再发出信号避免循环）。"""
        self._selection_rect = (x1, y1, x2, y2)
        self.update()

    def set_tool(self, tool: CanvasTool) -> None:
        self._tool = tool
        self._update_cursor_for_position(None)

    def zoom_fit(self) -> None:
        if self._image_width == 0 or self._image_height == 0:
            return
        w_ratio = self.width() / self._image_width
        h_ratio = self.height() / self._image_height
        self.zoom_factor = min(w_ratio, h_ratio, 1.0)
        img_w = int(self._image_width * self.zoom_factor)
        img_h = int(self._image_height * self.zoom_factor)
        self._pan_offset = QPoint(
            (self.width() - img_w) // 2,
            (self.height() - img_h) // 2,
        )
        self._user_zoomed = False   # 显式 fit 后重置，下次 resizeEvent 才会自动 fit
        self.zoom_changed.emit(self.zoom_factor)
        self.update()

    def zoom_in(self) -> None:
        self._user_zoomed = True
        self._set_zoom(min(self.zoom_factor + 0.25, 8.0))

    def zoom_out(self) -> None:
        self._user_zoomed = True
        self._set_zoom(max(self.zoom_factor - 0.25, 0.05))

    def get_selection_image_coords(self) -> Optional[Tuple[int, int, int, int]]:
        return self._selection_rect

    # ------------------------------------------------------------------
    # 坐标转换
    # ------------------------------------------------------------------

    def canvas_to_image(self, cx: int, cy: int) -> Tuple[int, int]:
        ix = int((cx - self._pan_offset.x()) / self.zoom_factor)
        iy = int((cy - self._pan_offset.y()) / self.zoom_factor)
        ix = max(0, min(ix, self._image_width - 1))
        iy = max(0, min(iy, self._image_height - 1))
        return ix, iy

    def image_to_canvas(self, ix: int, iy: int) -> Tuple[int, int]:
        cx = int(ix * self.zoom_factor + self._pan_offset.x())
        cy = int(iy * self.zoom_factor + self._pan_offset.y())
        return cx, cy

    # ------------------------------------------------------------------
    # 手柄计算
    # ------------------------------------------------------------------

    def _get_handle_rects(self) -> Optional[list[QRect]]:
        """返回 8 个手柄的 QRect（画布坐标），无选区时返回 None。"""
        if self._selection_rect is None:
            return None
        ix1, iy1, ix2, iy2 = self._selection_rect
        cx1, cy1 = self.image_to_canvas(ix1, iy1)
        cx2, cy2 = self.image_to_canvas(ix2, iy2)
        cxm = (cx1 + cx2) // 2
        cym = (cy1 + cy2) // 2
        hs = HANDLE_SIZE // 2
        pts = [
            (cx1, cy1), (cxm, cy1), (cx2, cy1),
            (cx2, cym),
            (cx2, cy2), (cxm, cy2), (cx1, cy2),
            (cx1, cym),
        ]
        return [QRect(x - hs, y - hs, HANDLE_SIZE, HANDLE_SIZE) for x, y in pts]

    def _hit_test(self, pos: QPoint) -> Tuple[str, int]:
        """
        判断鼠标位置命中了什么：
        返回 ("handle", idx) | ("inside", -1) | ("outside", -1)
        仅在有选区且是 CROP 工具时有意义。
        """
        handles = self._get_handle_rects()
        if handles:
            for i, hr in enumerate(handles):
                if hr.contains(pos):
                    return "handle", i

        if self._selection_rect:
            ix1, iy1, ix2, iy2 = self._selection_rect
            cx1, cy1 = self.image_to_canvas(ix1, iy1)
            cx2, cy2 = self.image_to_canvas(ix2, iy2)
            sel_canvas = QRect(cx1, cy1, cx2 - cx1, cy2 - cy1)
            if sel_canvas.contains(pos):
                return "inside", -1

        return "outside", -1

    def _update_cursor_for_position(self, pos: Optional[QPoint]) -> None:
        """根据鼠标位置更新光标形状。"""
        if self._space_held:
            return
        if self._tool == CanvasTool.PAN:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._tool == CanvasTool.CROP and self._selection_rect and pos:
            hit, idx = self._hit_test(pos)
            if hit == "handle":
                self.setCursor(_HANDLE_CURSORS[idx])
            elif hit == "inside":
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
        elif self._tool in (CanvasTool.SELECT, CanvasTool.CROP,
                             CanvasTool.GRABCUT):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._pixmap:
            return
        if not self._user_zoomed:
            # 未手动缩放（初始加载状态）：正常自适应
            self.zoom_fit()
        else:
            # 用户已手动缩放：保持缩放比，平移偏移跟随窗口尺寸变化居中补偿
            old = event.oldSize()
            if old.isValid():
                dx = (event.size().width() - old.width()) // 2
                dy = (event.size().height() - old.height()) // 2
                self._pan_offset += QPoint(dx, dy)
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._user_zoomed = True
            delta = event.angleDelta().y()
            if delta > 0:
                self._set_zoom(min(self.zoom_factor * 1.15, 8.0))
            else:
                self._set_zoom(max(self.zoom_factor / 1.15, 0.05))
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_held = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.key() == Qt.Key.Key_Escape:
            self.clear_selection()
            self.selection_cleared.emit()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_key_pressed.emit()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self._space_held = False
            self._update_cursor_for_position(None)
        else:
            super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.pos()

        if self._space_held or self._tool == CanvasTool.PAN:
            self._pan_start = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if self._tool == CanvasTool.CROP and self._selection_rect:
            hit, idx = self._hit_test(pos)
            if hit == "handle":
                self._crop_drag_mode = "resize"
                self._crop_handle_idx = idx
                self._crop_drag_origin = pos
                self._crop_rect_origin = self._selection_rect
                return
            elif hit == "inside":
                self._crop_drag_mode = "move"
                self._crop_drag_origin = pos
                self._crop_rect_origin = self._selection_rect
                return

        # 新建选区（draw 模式）
        if self._tool in (CanvasTool.SELECT, CanvasTool.CROP, CanvasTool.GRABCUT):
            self._crop_drag_mode = "draw"
            self._drag_start = pos
            self._drag_end = pos
            self._selection_rect = None   # 清除旧选区

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.pos()

        if (self._space_held or self._tool == CanvasTool.PAN) \
                and self._pan_start is not None:
            self._pan_offset += pos - self._pan_start
            self._pan_start = pos
            self.update()
            return

        if self._crop_drag_mode == "draw":
            self._drag_end = pos
            self.update()
            return

        if self._crop_drag_mode == "move":
            self._do_move(pos)
            return

        if self._crop_drag_mode == "resize":
            self._do_resize(pos)
            return

        # 无拖拽：更新悬停光标
        self._update_cursor_for_position(pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.pos()

        if self._space_held:
            self._pan_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return

        if self._tool == CanvasTool.PAN:
            self._pan_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return

        if self._crop_drag_mode == "draw":
            # 将拖拽矩形转换为图像坐标
            if self._drag_start and self._drag_end:
                ix1, iy1 = self.canvas_to_image(
                    self._drag_start.x(), self._drag_start.y())
                ix2, iy2 = self.canvas_to_image(
                    self._drag_end.x(), self._drag_end.y())
                x1, x2 = min(ix1, ix2), max(ix1, ix2)
                y1, y2 = min(iy1, iy2), max(iy1, iy2)
                if x2 > x1 and y2 > y1:
                    self._selection_rect = (x1, y1, x2, y2)
                    self.selection_changed.emit(x1, y1, x2, y2)
                else:
                    self.selection_cleared.emit()
            self._drag_start = None
            self._drag_end = None

        elif self._crop_drag_mode in ("move", "resize"):
            if self._selection_rect:
                x1, y1, x2, y2 = self._selection_rect
                self.selection_changed.emit(x1, y1, x2, y2)

        self._crop_drag_mode = "none"
        self._crop_handle_idx = -1
        self._crop_drag_origin = None
        self._crop_rect_origin = None
        self._update_cursor_for_position(pos)
        self.update()

    # ------------------------------------------------------------------
    # 移动 / 缩放选区的计算逻辑
    # ------------------------------------------------------------------

    def _do_move(self, pos: QPoint) -> None:
        if not self._crop_drag_origin or not self._crop_rect_origin:
            return
        dx_canvas = pos.x() - self._crop_drag_origin.x()
        dy_canvas = pos.y() - self._crop_drag_origin.y()
        # 画布偏移量 → 图像偏移量
        dx_img = int(dx_canvas / self.zoom_factor)
        dy_img = int(dy_canvas / self.zoom_factor)

        ox1, oy1, ox2, oy2 = self._crop_rect_origin
        rw = ox2 - ox1
        rh = oy2 - oy1

        nx1 = max(0, min(ox1 + dx_img, self._image_width - rw))
        ny1 = max(0, min(oy1 + dy_img, self._image_height - rh))
        self._selection_rect = (nx1, ny1, nx1 + rw, ny1 + rh)
        self.update()

    def _do_resize(self, pos: QPoint) -> None:
        if not self._crop_drag_origin or not self._crop_rect_origin:
            return
        dx = int((pos.x() - self._crop_drag_origin.x()) / self.zoom_factor)
        dy = int((pos.y() - self._crop_drag_origin.y()) / self.zoom_factor)

        ox1, oy1, ox2, oy2 = self._crop_rect_origin
        x1, y1, x2, y2 = ox1, oy1, ox2, oy2

        h = self._crop_handle_idx
        if h in (_TL, _LC, _BL):    x1 = max(0, min(ox1 + dx, x2 - 1))
        if h in (_TR, _RC, _BR):    x2 = max(x1 + 1, min(ox2 + dx, self._image_width))
        if h in (_TL, _TC, _TR):    y1 = max(0, min(oy1 + dy, y2 - 1))
        if h in (_BL, _BC, _BR):    y2 = max(y1 + 1, min(oy2 + dy, self._image_height))

        self._selection_rect = (x1, y1, x2, y2)
        self.update()

    # ------------------------------------------------------------------
    # 拖拽文件
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            self.file_dropped.emit(urls[0].toLocalFile())

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1a1a1a"))

        if self._pixmap is None:
            painter.setPen(QColor("#555"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "拖拽图片到此处，或使用 文件 → 打开")
            return

        img_w = int(self._image_width * self.zoom_factor)
        img_h = int(self._image_height * self.zoom_factor)
        img_rect = QRect(self._pan_offset.x(), self._pan_offset.y(), img_w, img_h)

        self._draw_checkerboard(painter, img_rect)
        painter.drawPixmap(img_rect, self._pixmap)

        # 绘制选区（优先显示实时拖拽）
        if self._crop_drag_mode == "draw" and self._drag_start and self._drag_end:
            self._draw_selection_live(painter)
        elif self._selection_rect is not None:
            self._draw_selection_committed(painter)

    def _draw_checkerboard(self, painter: QPainter, rect: QRect) -> None:
        size = 10
        clip = rect.intersected(self.rect())
        painter.save()
        painter.setClipRect(clip)
        for row in range(rect.height() // size + 2):
            for col in range(rect.width() // size + 2):
                color = (QColor(200, 200, 200) if (row + col) % 2 == 0
                         else QColor(255, 255, 255))
                painter.fillRect(
                    rect.x() + col * size, rect.y() + row * size,
                    size, size, color)
        painter.restore()

    def _draw_selection_live(self, painter: QPainter) -> None:
        x1 = min(self._drag_start.x(), self._drag_end.x())
        y1 = min(self._drag_start.y(), self._drag_end.y())
        x2 = max(self._drag_start.x(), self._drag_end.x())
        y2 = max(self._drag_start.y(), self._drag_end.y())
        self._paint_selection_rect(painter, QRect(x1, y1, x2 - x1, y2 - y1),
                                   show_handles=False)

    def _draw_selection_committed(self, painter: QPainter) -> None:
        ix1, iy1, ix2, iy2 = self._selection_rect
        cx1, cy1 = self.image_to_canvas(ix1, iy1)
        cx2, cy2 = self.image_to_canvas(ix2, iy2)
        sel_rect = QRect(cx1, cy1, cx2 - cx1, cy2 - cy1)
        show_handles = (self._tool == CanvasTool.CROP)
        self._paint_selection_rect(painter, sel_rect, show_handles=show_handles)

    def _paint_selection_rect(self, painter: QPainter, sel_rect: QRect,
                               show_handles: bool = False) -> None:
        # 半透明蒙层（选区外）
        painter.save()
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.setPen(Qt.PenStyle.NoPen)
        full = self.rect()
        painter.drawRect(QRect(full.left(), full.top(),
                               full.width(), sel_rect.top() - full.top()))
        painter.drawRect(QRect(full.left(), sel_rect.bottom(),
                               full.width(), full.bottom() - sel_rect.bottom()))
        painter.drawRect(QRect(full.left(), sel_rect.top(),
                               sel_rect.left() - full.left(), sel_rect.height()))
        painter.drawRect(QRect(sel_rect.right(), sel_rect.top(),
                               full.right() - sel_rect.right(), sel_rect.height()))
        painter.restore()

        # 蚂蚁线边框
        pen_black = QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DashLine)
        pen_white = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen_black)
        painter.drawRect(sel_rect.adjusted(1, 1, -1, -1))
        painter.setPen(pen_white)
        painter.drawRect(sel_rect)

        # 选区尺寸文字
        if self._selection_rect:
            ix1, iy1, ix2, iy2 = self._selection_rect
            text = f"{ix2 - ix1} × {iy2 - iy1}"
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                sel_rect.adjusted(4, 2, 0, 0),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                text,
            )

        # 8 个缩放手柄（仅裁剪工具显示）
        if show_handles:
            handle_rects = self._get_handle_rects()
            if handle_rects:
                painter.setPen(QPen(QColor(255, 255, 255), 1))
                painter.setBrush(QColor(30, 111, 165))
                for rect in handle_rects:
                    painter.drawRect(rect)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _set_zoom(self, new_zoom: float) -> None:
        if self._pixmap is None:
            return
        center = QPoint(self.width() // 2, self.height() // 2)
        old_img = ((center - self._pan_offset).x() / self.zoom_factor,
                   (center - self._pan_offset).y() / self.zoom_factor)
        self.zoom_factor = new_zoom
        self._pan_offset = QPoint(
            int(center.x() - old_img[0] * self.zoom_factor),
            int(center.y() - old_img[1] * self.zoom_factor),
        )
        self.zoom_changed.emit(self.zoom_factor)
        self.update()
