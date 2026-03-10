from __future__ import annotations

import numpy as np
from pathlib import Path
from PyQt6.QtCore import Qt, QThread
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog

from core.grabcut import GrabCutWorker
from core.history import HistoryManager
from core.image_model import ImageModel
from core.image_processor import ImageProcessor
from core.realesrgan import (
    RealESRGANWorker,
    is_model_available,
    is_runtime_available,
    runtime_error_message,
)
from ui.dialogs import (
    JpegQualityDialog,
    ResizeDialog,
    AiClarifyDialog,
    SpritePreviewDialog,
)
from ui.main_window import MainWindow
from ui.toolbar import CanvasTool

_TOOL_NAMES = {
    CanvasTool.NONE:    "-",
    CanvasTool.PAN:     "平移",
    CanvasTool.LAYER_MOVE: "图层",
    CanvasTool.SELECT:  "选框",
    CanvasTool.CROP:    "裁剪",
    CanvasTool.GRABCUT: "抠图",
    CanvasTool.SPRITE:  "雪碧图",
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
        self._esrgan_thread: QThread | None = None
        self._esrgan_worker: RealESRGANWorker | None = None
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
        lp = w.layer_panel

        # 文件
        w.open_triggered.connect(self.open_image)
        w.add_layer_triggered.connect(self.add_image_layer)
        w.clear_layers_triggered.connect(self.clear_all_layers)
        w.export_triggered.connect(self.export_image)

        # 图像
        w.trim_triggered.connect(self.do_trim_to_content)
        w.resize_triggered.connect(self.do_resize_to_size)
        w.sprite_preview_triggered.connect(self.preview_sprite_sheet)
        w.sprite_export_triggered.connect(self.export_sprite_sheet)
        w.sprite_per_row_changed.connect(self._on_sprite_per_row_changed)
        w.sprite_panel.closed.connect(self._on_sprite_panel_closed)

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
        tb.trim_clicked.connect(self.do_trim_to_content)
        tb.resize_clicked.connect(self.do_resize_to_size)
        tb.clarify_clicked.connect(self.do_ai_clarify)

        # 画布选区变化 → 同步到 model 和 CropPanel
        cv.selection_changed.connect(self._on_selection_changed)
        cv.selection_cleared.connect(self._on_selection_cleared)
        cv.delete_key_pressed.connect(self.do_delete_selection)
        cv.file_dropped.connect(self._on_file_dropped)
        cv.layer_selected.connect(self._on_layer_selected)
        cv.layer_moved.connect(self._on_layer_moved)
        cv.layer_move_finished.connect(self._on_layer_move_finished)
        cv.layer_reorder_requested.connect(self._on_layer_reorder_requested)
        cv.layer_delete_requested.connect(self._on_layer_delete_requested)
        # 画布缩放变化 → 同步到 CropPanel（更新视图尺寸提示）
        cv.zoom_changed.connect(cp.set_zoom)

        # 图层面板
        lp.layer_selected.connect(self._on_layer_panel_selected)
        lp.layer_visibility_toggled.connect(self._on_layer_visibility_toggled)
        lp.layer_order_changed.connect(self._on_layer_order_changed)

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
        self._push_history_snapshot()
        self._refresh_canvas_from_model(zoom_fit=True)
        self._update_sprite_panel_info()
        self.window.update_image_info(self.model.width, self.model.height)
        self.window.crop_panel.set_image_size(self.model.width, self.model.height)
        self.window.setWindowTitle(f"EasyPicture — {path}")
        self._update_undo_redo_state()

    def add_image_layer(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.window, "添加图片为图层", "", _OPEN_FILTER
        )
        if not path:
            return
        self.add_image_layer_from_path(path)

    def add_image_layer_from_path(self, path: str) -> None:
        try:
            img = ImageProcessor.read_image(path)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self.window, "添加图层失败", str(exc))
            return

        self.model.add_layer(img, Path(path).name, source_path=path)
        self._push_history_snapshot()
        self._refresh_canvas_from_model(zoom_fit=(len(self.model.layers) == 1))
        self._update_sprite_panel_info()
        self.window.update_image_info(self.model.width, self.model.height)
        self.window.crop_panel.set_image_size(self.model.width, self.model.height)
        self.window.show_message(f"已添加图层：{Path(path).name}")
        self._update_undo_redo_state()

    def clear_all_layers(self) -> None:
        if not self.model.layers:
            return
        reply = QMessageBox.question(
            self.window,
            "清空所有图层",
            "将移除当前画布上的全部图层，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.model.clear_layers():
            self._push_history_snapshot()
            self.window.canvas.clear_selection()
            self._refresh_canvas_from_model()
            self._update_sprite_panel_info()
            self.window.update_image_info(self.model.width, self.model.height)
            self.window.crop_panel.set_image_size(self.model.width, self.model.height)
            self.window.show_message("已清空所有图层")
            self._update_undo_redo_state()

    def export_image(self) -> bool:
        if self.model.image is None:
            QMessageBox.information(self.window, "提示", "请先打开一张图片")
            return False

        path, selected_filter = QFileDialog.getSaveFileName(
            self.window, "导出图片", "", _SAVE_FILTER
        )
        if not path:
            return False

        # 补充扩展名
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
                return False
            quality = dlg.quality

        try:
            merged = self.model.image
            if merged is None:
                return False
            ImageProcessor.write_image(merged, path, quality)
            self.model.mark_saved()
            self.window.show_message(f"已保存：{path}")
            self.window.setWindowTitle(f"EasyPicture — {path}")
            return True
        except Exception as exc:
            QMessageBox.critical(self.window, "导出失败", str(exc))
            return False

    # ------------------------------------------------------------------
    # 通用变换入口
    # ------------------------------------------------------------------

    def _apply_transform(self, new_img: np.ndarray, zoom_fit: bool = False) -> None:
        """保存历史 → 更新 model → 刷新画布 → 更新状态栏。"""
        self.model.update_image(new_img)
        self._push_history_snapshot()
        self._refresh_canvas_from_model(zoom_fit=zoom_fit)
        self._update_sprite_panel_info()
        self.window.update_image_info(self.model.width, self.model.height)
        # 图像尺寸变化时同步 crop_panel 的坐标上限
        self.window.crop_panel.set_image_size(self.model.width, self.model.height)
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
        self._apply_transform(new_img, zoom_fit=True)

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
        self.model.restore_from_snapshot(prev)
        self.window.canvas.clear_selection()
        self._refresh_canvas_from_model()
        self._update_sprite_panel_info()
        self.window.update_image_info(self.model.width, self.model.height)
        self.window.crop_panel.set_image_size(self.model.width, self.model.height)
        self._update_undo_redo_state()

    def redo(self) -> None:
        nxt = self.history.redo()
        if nxt is None:
            return
        self.model.restore_from_snapshot(nxt)
        self.window.canvas.clear_selection()
        self._refresh_canvas_from_model()
        self._update_sprite_panel_info()
        self.window.update_image_info(self.model.width, self.model.height)
        self.window.crop_panel.set_image_size(self.model.width, self.model.height)
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

        if not Path(path).suffix:
            if "PNG" in selected_filter:
                path += ".png"
            elif "JPEG" in selected_filter:
                path += ".jpg"
            elif "TIFF" in selected_filter:
                path += ".tiff"
            else:
                path += ".bmp"

        x1, y1, x2, y2 = sel
        cropped = ImageProcessor.crop(self.model.image, x1, y1, x2, y2)

        ext = Path(path).suffix.lower()
        quality = 95
        if ext in (".jpg", ".jpeg"):
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
    # 符合画布（Trim to content）
    # ------------------------------------------------------------------

    def do_trim_to_content(self) -> None:
        """一键裁去四周透明像素，保留主体内容（F-08）。"""
        if self.model.image is None:
            QMessageBox.information(self.window, "提示", "请先打开一张图片")
            return
        try:
            new_img = ImageProcessor.trim_to_content(self.model.image)
        except ValueError as exc:
            QMessageBox.information(self.window, "符合画布", str(exc))
            return

        # 尺寸未变化
        if new_img.shape == self.model.image.shape:
            QMessageBox.information(self.window, "符合画布",
                                    "图片四周无透明像素，无需裁切。")
            return

        old_w, old_h = self.model.width, self.model.height
        self._apply_transform(new_img, zoom_fit=True)
        self.window.show_message(
            f"符合画布：{old_w}×{old_h} → {self.model.width}×{self.model.height}"
        )

    # ------------------------------------------------------------------
    # 缩放到指定尺寸
    # ------------------------------------------------------------------

    def do_resize_to_size(self) -> None:
        """弹出缩放对话框，将图片重采样到指定尺寸（F-09）。"""
        if self.model.image is None:
            QMessageBox.information(self.window, "提示", "请先打开一张图片")
            return

        dlg = ResizeDialog(self.model.width, self.model.height, self.window)
        result = dlg.get_values()
        if result is None:
            return

        try:
            new_img = ImageProcessor.resize_to_size(
                self.model.image,
                result["w"],
                result["h"],
                result["keep_aspect"],
                sharpen=False,
                interp="lanczos",
            )
        except ValueError as exc:
            QMessageBox.critical(self.window, "缩放失败", str(exc))
            return

        self._apply_transform(new_img, zoom_fit=True)
        self.window.show_message(
            f"缩放完成：{self.model.width}×{self.model.height}"
        )

    # ------------------------------------------------------------------
    # AI 变清晰
    # ------------------------------------------------------------------

    def do_ai_clarify(self) -> None:
        """AI 变清晰：使用 Real-ESRGAN 超分辨率放大（2x/4x），重建细节。"""
        if self.model.image is None:
            QMessageBox.information(self.window, "提示", "请先打开一张图片")
            return

        if not is_runtime_available():
            detail = runtime_error_message()
            QMessageBox.critical(
                self.window, "运行时不可用",
                "检测到 onnxruntime 不可用，AI 变清晰已禁用。\n\n"
                "请在目标系统安装/打包 onnxruntime 及其依赖后重试。"
                + (f"\n\n详细错误：\n{detail}" if detail else "")
            )
            return

        if not is_model_available():
            from core.realesrgan import _current_model_stem
            QMessageBox.critical(
                self.window, "模型未找到",
                f"请先准备 ONNX 模型文件：\n\n"
                f"1. 下载 {_current_model_stem}.pth\n"
                "   https://github.com/xinntao/Real-ESRGAN/releases\n\n"
                "2. 放入 models/ 目录\n\n"
                "3. 运行转换脚本（需要 torch）：\n"
                f"   uv run --with torch python tools/convert_to_onnx.py {_current_model_stem}.pth\n\n"
                "详情见 models/README.md"
            )
            return

        dlg = AiClarifyDialog(self.model.width, self.model.height, self.window)
        params = dlg.get_values()
        if params is None:
            return

        self._progress_dialog = QProgressDialog(
            "AI 变清晰处理中，请稍候...", None, 0, 100, self.window
        )
        self._progress_dialog.setWindowTitle("AI 变清晰")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.show()

        self._esrgan_thread = QThread()
        self._esrgan_worker = RealESRGANWorker(
            self.model.image.copy(),
            scale=params["scale"],
            denoise_strength=params["denoise"],
        )
        self._esrgan_worker.moveToThread(self._esrgan_thread)

        self._esrgan_worker.progress.connect(self._progress_dialog.setValue)
        self._esrgan_worker.finished.connect(self._on_esrgan_done)
        self._esrgan_worker.failed.connect(self._on_esrgan_failed)
        self._esrgan_thread.started.connect(self._esrgan_worker.run)
        self._esrgan_thread.start()

    def _on_esrgan_done(self, result: np.ndarray) -> None:
        self._esrgan_thread.quit()
        self._esrgan_thread.wait()
        if self._progress_dialog:
            self._progress_dialog.close()
        self._apply_transform(result, zoom_fit=True)
        self.window.show_message(
            f"AI 变清晰完成：{self.model.width}×{self.model.height}"
        )

    def _on_file_dropped(self, path: str) -> None:
        if self.model.image is None:
            self.open_image_from_path(path)
            return
        self.add_image_layer_from_path(path)

    def _on_layer_selected(self, idx: int) -> None:
        self.model.set_active_layer(idx)
        self.window.layer_panel.set_active_layer(idx)
        self.window.canvas.set_active_layer(idx)

    def _on_layer_panel_selected(self, idx: int) -> None:
        self.model.set_active_layer(idx)
        self.window.canvas.set_active_layer(idx)
        self.window.layer_panel.set_active_layer(idx)

    def _on_layer_visibility_toggled(self, idx: int, visible: bool) -> None:
        if self.model.set_layer_visible(idx, visible):
            self._push_history_snapshot()
            self._refresh_canvas_from_model()
            self._update_sprite_panel_info()
            self._update_sprite_canvas_view()
            self._update_undo_redo_state()

    def _on_layer_order_changed(self, order: list[int]) -> None:
        if self.model.reorder_layers_by_indices(order):
            self._push_history_snapshot()
            self._refresh_canvas_from_model()
            self._update_sprite_panel_info()
            self._update_sprite_canvas_view()
            self._update_undo_redo_state()

    def _on_layer_moved(self, idx: int, x: int, y: int) -> None:
        self.model.move_layer_to(idx, x, y)

    def _on_layer_move_finished(self, idx: int) -> None:
        if idx >= 0:
            self._push_history_snapshot()
            self._update_undo_redo_state()

    def _on_layer_reorder_requested(self, idx: int, action: str) -> None:
        new_idx = self.model.reorder_layer(idx, action)
        if new_idx != idx:
            self._push_history_snapshot()
        self._refresh_canvas_from_model()
        self._update_sprite_panel_info()
        self._update_sprite_canvas_view()
        self._update_undo_redo_state()

    def _on_layer_delete_requested(self, idx: int) -> None:
        if self.model.remove_layer(idx):
            self._push_history_snapshot()
            self.window.canvas.clear_selection()
            self.window.crop_panel.set_image_size(self.model.width, self.model.height)
            self.window.update_image_info(self.model.width, self.model.height)
            self._refresh_canvas_from_model()
            self._update_sprite_panel_info()
            self._update_sprite_canvas_view()
            self._update_undo_redo_state()

    def _on_esrgan_failed(self, err: str) -> None:
        self._esrgan_thread.quit()
        self._esrgan_thread.wait()
        if self._progress_dialog:
            self._progress_dialog.close()
        QMessageBox.critical(
            self.window, "AI 变清晰失败",
            f"处理过程出错：{err}\n\n"
            "建议：图片过大时可先用「改变尺寸」缩小后再处理。"
        )

    # ------------------------------------------------------------------
    # 工具切换
    # ------------------------------------------------------------------

    def _on_tool_selected(self, tool_int: int) -> None:
        tool = CanvasTool(tool_int)
        self.window.canvas.set_tool(tool)
        self.window.update_tool(_TOOL_NAMES.get(tool, "-"))

        cp = self.window.crop_panel
        sp = self.window.sprite_panel
        if tool == CanvasTool.CROP:
            # 显示裁剪面板并初始化图像尺寸限制
            if self.model.image is not None:
                cp.set_image_size(self.model.width, self.model.height)
            # 若已有选区，同步到面板
            sel = self.model.selection
            if sel:
                cp.set_selection(*sel)
            cp.show()
            sp.hide()
            self.window.canvas.set_sprite_sheet(None)
            self._refresh_canvas_from_model()
        elif tool == CanvasTool.SPRITE:
            cp.hide()
            self._update_sprite_panel_info()
            sp.show()
            self._update_sprite_canvas_view()
        else:
            cp.hide()
            sp.hide()
            self.window.canvas.set_sprite_sheet(None)
            self._refresh_canvas_from_model()

    def _on_sprite_panel_closed(self) -> None:
        self.window.toolbar.set_tool(CanvasTool.NONE)
        self.window.canvas.set_tool(CanvasTool.NONE)
        self.window.sprite_panel.hide()
        self.window.canvas.set_sprite_sheet(None)
        self._refresh_canvas_from_model()
        self.window.update_tool("-")

    def _refresh_canvas_from_model(self, zoom_fit: bool = False) -> None:
        layers = [{
            "name": layer.name,
            "image": layer.image,
            "x": layer.x,
            "y": layer.y,
            "visible": layer.visible,
            "source_path": layer.source_path,
        } for layer in self.model.layers]
        self.window.canvas.set_layers(
            layers,
            self.model.width,
            self.model.height,
            self.model.active_layer_index,
        )
        self.window.layer_panel.set_layers(layers, self.model.active_layer_index)
        if zoom_fit:
            self.window.canvas.zoom_fit()

    def _push_history_snapshot(self) -> None:
        self.history.push(self.model.get_state_snapshot())

    def _get_sprite_frames(self) -> list[np.ndarray]:
        return [layer.image for layer in self.model.layers if layer.visible]

    def _on_sprite_per_row_changed(self, _value: int) -> None:
        self._update_sprite_panel_info()
        self._update_sprite_canvas_view()

    def _update_sprite_panel_info(self) -> None:
        frames = self._get_sprite_frames()
        if not frames:
            self.window.sprite_panel.set_info("无可用图层")
            self.window.canvas.set_sprite_sheet(None)
            return
        per_row = max(1, self.window.sprite_panel.per_row)
        _, rows, cols = ImageProcessor.build_sprite_sheet(frames, per_row)
        self.window.sprite_panel.set_info(
            f"{len(frames)} 帧  ·  {cols}×{rows} 网格"
        )

    def preview_sprite_sheet(self) -> None:
        frames = self._get_sprite_frames()
        if not frames:
            QMessageBox.information(self.window, "雪碧图", "没有可预览的图层")
            return
        dlg = SpritePreviewDialog(frames, self.window)
        dlg.exec()

    def export_sprite_sheet(self) -> None:
        frames = self._get_sprite_frames()
        if not frames:
            QMessageBox.information(self.window, "雪碧图", "没有可导出的图层")
            return

        per_row = max(1, self.window.sprite_panel.per_row)
        sheet, rows, cols = ImageProcessor.build_sprite_sheet(frames, per_row)

        path, selected_filter = QFileDialog.getSaveFileName(
            self.window, "导出雪碧图", "", _SAVE_FILTER
        )
        if not path:
            return

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
        quality = 95
        if ext in (".jpg", ".jpeg"):
            dlg = JpegQualityDialog(self.window, 95)
            if dlg.exec() != JpegQualityDialog.DialogCode.Accepted:
                return
            quality = dlg.quality

        try:
            ImageProcessor.write_image(sheet, path, quality)
            self.window.show_message(
                f"已导出雪碧图：{cols}×{rows} 网格，{len(frames)} 帧"
            )
        except Exception as exc:
            QMessageBox.critical(self.window, "导出雪碧图失败", str(exc))

    def _update_sprite_canvas_view(self) -> None:
        if self.window.canvas is None:
            return
        if self.window.sprite_panel.isVisible() and self.window.canvas.tool == CanvasTool.SPRITE:
            frames = self._get_sprite_frames()
            if not frames:
                self.window.canvas.set_sprite_sheet(None)
                return
            per_row = max(1, self.window.sprite_panel.per_row)
            sheet, _, _ = ImageProcessor.build_sprite_sheet(frames, per_row)
            self.window.canvas.set_sprite_sheet(sheet)
