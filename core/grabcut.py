from __future__ import annotations
from typing import Tuple

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal as Signal


class GrabCutWorker(QObject):
    """在 QThread 中执行 GrabCut 抠图，通过信号返回结果。"""

    finished = Signal(object)   # np.ndarray — 抠图完成，BGRA 结果
    failed = Signal(str)        # str — 错误信息
    progress = Signal(int)      # int 0-100

    def __init__(self, img: np.ndarray,
                 rect: Tuple[int, int, int, int],
                 iter_count: int = 5) -> None:
        super().__init__()
        self.img = img
        self.rect = rect
        self.iter_count = iter_count

    def run(self) -> None:
        try:
            self.progress.emit(10)

            # 转为 BGR（GrabCut 不支持 BGRA）
            bgr = cv2.cvtColor(self.img, cv2.COLOR_BGRA2BGR)
            h, w = bgr.shape[:2]

            # 大图缩放优化
            scale = 1.0
            max_size = 1500
            if max(h, w) > max_size:
                scale = max_size / max(h, w)
                bgr_small = cv2.resize(bgr, None, fx=scale, fy=scale,
                                       interpolation=cv2.INTER_AREA)
                rx, ry, rw, rh = self.rect
                rect_small = (
                    max(1, int(rx * scale)),
                    max(1, int(ry * scale)),
                    max(1, int(rw * scale)),
                    max(1, int(rh * scale)),
                )
            else:
                bgr_small = bgr
                rect_small = self.rect

            # 确保 rect 在图像边界内且尺寸合法
            sh, sw = bgr_small.shape[:2]
            rx, ry, rw, rh = rect_small
            rx = max(1, min(rx, sw - 2))
            ry = max(1, min(ry, sh - 2))
            rw = max(1, min(rw, sw - rx - 1))
            rh = max(1, min(rh, sh - ry - 1))
            rect_small = (rx, ry, rw, rh)

            self.progress.emit(30)

            mask = np.zeros(bgr_small.shape[:2], np.uint8)
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)

            cv2.grabCut(bgr_small, mask, rect_small,
                        bgd_model, fgd_model,
                        self.iter_count, cv2.GC_INIT_WITH_RECT)

            self.progress.emit(80)

            # 生成前景 mask
            fg_mask = np.where(
                (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
            ).astype(np.uint8)

            # 缩放 mask 回原始尺寸
            if scale != 1.0:
                fg_mask = cv2.resize(fg_mask, (w, h),
                                     interpolation=cv2.INTER_NEAREST)

            result = self.img.copy()
            result[:, :, 3] = fg_mask

            self.progress.emit(100)
            self.finished.emit(result)

        except Exception as exc:
            self.failed.emit(str(exc))
