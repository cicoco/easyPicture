from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

from core.grabcut import GrabCutWorker
from core.history import HistoryManager
from core.image_model import ImageModel
from core.image_processor import ImageProcessor
from ui.dialogs import JpegQualityDialog
from ui.main_window import MainWindow
from ui.toolbar import CanvasTool

_TOOL_NAMES = {
    CanvasTool.NONE:    "-",
    CanvasTool.SELECT:  "选框",
    CanvasTool.CROP:    "裁剪",
    CanvasTool.GRABCUT: "抠图",
}

_OPEN_FILTER = "图片文件 (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp)"
_SAVE_FILTER = "PNG 无损 (*.png);;JPEG (*.jpg);;TIFF 无损 (*.tiff);;BMP (*.bmp)"


class AppController:
    """协调 UI 事件与核心处理逻辑的中间层。"""

    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self.model = ImageModel()
        self.history = HistoryManager()

        self._grabcut_thread: QThread | None = None
        self._grabcut_worker: GrabCutWorker | None = None
        self._progress_dialog: QProgressDialog | None = None

        self._connect_signals()

    # ------------------------------------------------------------------
    # 信号连接
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        w = self.window
        tb = w.toolbar
        cv = w.canvas
        cp = w.crop_panel

        # 文件
        w.open_triggered.connect(self.open_image)
        w.export_triggered.connect(self.export_image)

        # 编辑
        w.undo_triggered.connect(self.undo)
        w.redo_triggered.connect(self.redo)

        # 工具栏
        tb.tool_selected.connect(self._on_tool_selected)
        tb.rotate_cw_clicked.connect(self.do_rotate_cw)
        tb.rotate_ccw_clicked.connect(self.do_rotate_ccw)
        tb.crop_clicked.connect(self.do_crop)
        tb.delete_clicked.connect(self.do_delete_selection)
        tb.grabcut_clicked.connect(self.do_grabcut)

        # 画布选区变化 → 同步到 model 和 CropPanel
        cv.selection_changed.connect(self._on_selection_changed)
        cv.selection_cleared.connect(self._on_selection_cleared)
        cv.delete_key_pressed.connect(self.do_delete_selection)
        cv.file_dropped.connect(self.open_image_from_path)

        # CropPanel 数值框 → 同步到 Canvas
        cp.values_changed.connect(self._on_crop_panel_values_changed)
        cp.crop_confirmed.connect(self.do_crop)
        cp.crop_exported.connect(self.do_crop_export)
        cp.crop_cancelled.connect(self._on_crop_cancelled)

    # ------------------------------------------------------------------
    # 文件操作
    # ------------------------------------------------------------------

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window, "打开图片", "", _OPEN_FILTER
        )
        if not path:
            return
        self.open_image_from_path(path)

    def open_image_from_path(self, path: str) -> None:
        if self.model.is_dirty:
            msg = QMessageBox(self.window)
            msg.setWindowTitle("未保存的修改")
            msg.setText("当前图片有未保存的修改，确定打开新图片？")
            msg.setStandardButtons(
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            msg.setEscapeButton(QMessageBox.StandardButton.No)
            reply = msg.exec()
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            img = ImageProcessor.read_image(path)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self.window, "打开失败", str(exc))
            return

        self.model.set_image(img, path)
        self.history.clear()
        self.window.canvas.set_image(img)
        self.window.canvas.zoom_fit()
        self.window.update_image_info(self.model.width, self.model.height)
        self.window.crop_panel.set_image_size(self.model.width, self.model.height)
        self.window.setWindowTitle(f"EasyPicture — {path}")
        self._update_undo_redo_state()

    def export_image(self) -> None:
        if self.model.image is None:
            QMessageBox.information(self.window, "提示", "请先打开一张图片")
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self.window, "导出图片", "", _SAVE_FILTER
        )
        if not path:
            return

        # 补充扩展名
        from pathlib import Path
        if not Path(path).suffix:
            if "PNG" in selected_filter:
                path += ".png"
            elif "JPEG" in selected_filter:
                path += ".jpg"
            elif "TIFF" in selected_filter:
                path += ".tiff"
            else:
                path += ".bmp"

        ext = Path(path).suffix.lower()

        # JPG 透明警告
        if ext in (".jpg", ".jpeg") and self.model.has_alpha:
            QMessageBox.warning(
                self.window, "格式警告",
                "当前图片含透明区域，JPEG 格式不支持透明，\n透明部分将以白色填充。"
            )

        # JPG 质量对话框
        quality = 95
        if ext in (".jpg", ".jpeg"):
            dlg = JpegQualityDialog(self.window, 95)
            if dlg.exec() != JpegQualityDialog.DialogCode.Accepted:
                return
            quality = dlg.quality

        try:
            ImageProcessor.write_image(self.model.image, path, quality)
            self.model.mark_saved()
            self.window.show_message(f"已保存：{path}")
            self.window.setWindowTitle(f"EasyPicture — {path}")
        except Exception as exc:
            QMessageBox.critical(self.window, "导出失败", str(exc))

    # ------------------------------------------------------------------
    # 通用变换入口
    # ------------------------------------------------------------------

    def _apply_transform(self, new_img: np.ndarray) -> None:
        """保存历史 → 更新 model → 刷新画布 → 更新状态栏。"""
        if self.model.image is not None:
            self.history.push(self.model.image.copy())
        self.model.update_image(new_img)
        self.window.canvas.refresh(new_img)
        self.window.update_image_info(self.model.width, self.model.height)
        self._update_undo_redo_state()

    # ------------------------------------------------------------------
    # 旋转
    # ------------------------------------------------------------------

    def do_rotate_cw(self) -> None:
        if self.model.image is None:
            return
        self._apply_transform(ImageProcessor.rotate_90cw(self.model.image))

    def do_rotate_ccw(self) -> None:
        if self.model.image is None:
            return
        self._apply_transform(ImageProcessor.rotate_90ccw(self.model.image))

    # ------------------------------------------------------------------
    # 裁剪
    # ------------------------------------------------------------------

    def do_crop(self) -> None:
        sel = self.model.selection
        if sel is None:
            QMessageBox.information(self.window, "提示",
                                    "请先使用选框工具框选裁剪区域")
            return
        x1, y1, x2, y2 = sel
        new_img = ImageProcessor.crop(self.model.image, x1, y1, x2, y2)
        self.model.clear_selection()
        self.window.canvas.clear_selection()
        self._apply_transform(new_img)
        self.window.canvas.zoom_fit()

    # ------------------------------------------------------------------
    # 删除选区
    # ------------------------------------------------------------------

    def do_delete_selection(self) -> None:
        if self.model.image is None:
            return
        sel = self.model.selection
        if sel is None:
            QMessageBox.information(self.window, "提示",
                                    "请先使用选框工具框选要删除的区域")
            return
        x1, y1, x2, y2 = sel
        new_img = ImageProcessor.delete_selection(self.model.image, x1, y1, x2, y2)
        self._apply_transform(new_img)

    # ------------------------------------------------------------------
    # GrabCut 抠图
    # ------------------------------------------------------------------

    def do_grabcut(self) -> None:
        if self.model.image is None:
            return
        sel = self.model.selection
        if sel is None:
            QMessageBox.information(self.window, "提示",
                                    "请先用选框工具圈出要保留的主体区域，然后点击抠图")
            return

        x1, y1, x2, y2 = sel
        rect = (x1, y1, x2 - x1, y2 - y1)

        self._progress_dialog = QProgressDialog(
            "正在抠图，请稍候...", None, 0, 100, self.window
        )
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.show()

        self._grabcut_thread = QThread()
        self._grabcut_worker = GrabCutWorker(self.model.image.copy(), rect)
        self._grabcut_worker.moveToThread(self._grabcut_thread)

        self._grabcut_worker.progress.connect(self._progress_dialog.setValue)
        self._grabcut_worker.finished.connect(self._on_grabcut_done)
        self._grabcut_worker.failed.connect(self._on_grabcut_failed)
        self._grabcut_thread.started.connect(self._grabcut_worker.run)
        self._grabcut_thread.start()

    def _on_grabcut_done(self, result: np.ndarray) -> None:
        self._grabcut_thread.quit()
        self._grabcut_thread.wait()
        if self._progress_dialog:
            self._progress_dialog.close()
        self.model.clear_selection()
        self.window.canvas.clear_selection()
        self._apply_transform(result)

    def _on_grabcut_failed(self, err: str) -> None:
        self._grabcut_thread.quit()
        self._grabcut_thread.wait()
        if self._progress_dialog:
            self._progress_dialog.close()
        QMessageBox.critical(
            self.window, "抠图失败",
            f"抠图过程出错：{err}\n\n建议：请框选更大的区域再试。"
        )

    # ------------------------------------------------------------------
    # 撤销 / 重做
    # ------------------------------------------------------------------

    def undo(self) -> None:
        prev = self.history.undo()
        if prev is None:
            return
        self.model.update_image(prev)
        self.window.canvas.refresh(prev)
        self.window.update_image_info(self.model.width, self.model.height)
        self._update_undo_redo_state()

    def redo(self) -> None:
        nxt = self.history.redo()
        if nxt is None:
            return
        self.model.update_image(nxt)
        self.window.canvas.refresh(nxt)
        self.window.update_image_info(self.model.width, self.model.height)
        self._update_undo_redo_state()

    def _update_undo_redo_state(self) -> None:
        self.window.undo_action.setEnabled(self.history.can_undo)
        self.window.redo_action.setEnabled(self.history.can_redo)

    # ------------------------------------------------------------------
    # 选区同步
    # ------------------------------------------------------------------

    def _on_selection_changed(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Canvas 选区变化 → 同步 model、CropPanel、执行按钮状态。"""
        self.model.set_selection(x1, y1, x2, y2)
        cp = self.window.crop_panel
        if cp.isVisible():
            cp.set_selection(x1, y1, x2, y2)
        self.window.toolbar.set_grabcut_ready(True)

    def _on_selection_cleared(self) -> None:
        self.model.clear_selection()
        self.window.toolbar.set_grabcut_ready(False)

    def _on_crop_panel_values_changed(self, x1: int, y1: int,
                                       x2: int, y2: int) -> None:
        """CropPanel 数值框改变 → 同步到 model 和 Canvas。"""
        self.model.set_selection(x1, y1, x2, y2)
        self.window.canvas.set_selection_from_panel(x1, y1, x2, y2)

    def _on_crop_cancelled(self) -> None:
        self.model.clear_selection()
        self.window.canvas.clear_selection()
        # 退出裁剪工具
        self.window.toolbar.set_tool(CanvasTool.NONE)
        self.window.canvas.set_tool(CanvasTool.NONE)
        self.window.crop_panel.hide()
        self.window.update_tool("-")

    # ------------------------------------------------------------------
    # 导出裁剪区域（不替换当前图像）
    # ------------------------------------------------------------------

    def do_crop_export(self) -> None:
        """将裁剪区域另存为新文件，不修改当前编辑中的图像。"""
        if self.model.image is None:
            return
        sel = self.model.selection
        if sel is None:
            QMessageBox.information(self.window, "提示", "请先框选裁剪区域")
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self.window, "导出裁剪区域", "", _SAVE_FILTER
        )
        if not path:
            return

        from pathlib import Path
        if not Path(path).suffix:
            path += ".png"

        x1, y1, x2, y2 = sel
        cropped = ImageProcessor.crop(self.model.image, x1, y1, x2, y2)

        ext = Path(path).suffix.lower()
        quality = 95
        if ext in (".jpg", ".jpeg"):
            from ui.dialogs import JpegQualityDialog
            dlg = JpegQualityDialog(self.window, 95)
            if dlg.exec() != JpegQualityDialog.DialogCode.Accepted:
                return
            quality = dlg.quality

        try:
            ImageProcessor.write_image(cropped, path, quality)
            self.window.show_message(f"裁剪区域已导出：{path}")
        except Exception as exc:
            QMessageBox.critical(self.window, "导出失败", str(exc))

    # ------------------------------------------------------------------
    # 工具切换
    # ------------------------------------------------------------------

    def _on_tool_selected(self, tool_int: int) -> None:
        tool = CanvasTool(tool_int)
        self.window.canvas.set_tool(tool)
        self.window.update_tool(_TOOL_NAMES.get(tool, "-"))

        cp = self.window.crop_panel
        if tool == CanvasTool.CROP:
            # 显示裁剪面板并初始化图像尺寸限制
            if self.model.image is not None:
                cp.set_image_size(self.model.width, self.model.height)
            # 若已有选区，同步到面板
            sel = self.model.selection
            if sel:
                cp.set_selection(*sel)
            cp.show()
        else:
            cp.hide()
