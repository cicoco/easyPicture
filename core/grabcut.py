from __future__ import annotations
from typing import Tuple

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal as Signal


class GrabCutWorker(QObject):
    """
    在 QThread 中执行 GrabCut 抠图。

    流程：
      1. 大图缩放 → GrabCut 提取前景 mask
      2. 形态学修复：填洞 + 去噪点
      3. 保留最大连通域（去掉孤立碎块）
      4. 双线性插值放大 mask 回原始尺寸
      5. 边缘羽化：高斯模糊边缘 → 软 alpha 过渡
      6. 合并到 BGRA 结果（背景 alpha=0）
    """

    finished = Signal(object)   # np.ndarray BGRA
    failed   = Signal(str)
    progress = Signal(int)      # 0-100

    def __init__(self, img: np.ndarray,
                 rect: Tuple[int, int, int, int],
                 iter_count: int = 5) -> None:
        super().__init__()
        self.img = img
        self.rect = rect
        self.iter_count = iter_count

    def run(self) -> None:
        try:
            self.progress.emit(5)

            bgr = cv2.cvtColor(self.img, cv2.COLOR_BGRA2BGR)
            orig_h, orig_w = bgr.shape[:2]

            # ----------------------------------------------------------
            # 1. 大图缩放（加速 GrabCut）
            # ----------------------------------------------------------
            MAX_SIZE = 1200
            scale = 1.0
            if max(orig_h, orig_w) > MAX_SIZE:
                scale = MAX_SIZE / max(orig_h, orig_w)
                bgr_small = cv2.resize(bgr, None, fx=scale, fy=scale,
                                       interpolation=cv2.INTER_AREA)
            else:
                bgr_small = bgr.copy()

            sh, sw = bgr_small.shape[:2]

            # 将 rect 映射到缩放后的坐标，并保证合法
            rx, ry, rw, rh = self.rect
            rx  = max(1, min(int(rx * scale), sw - 2))
            ry  = max(1, min(int(ry * scale), sh - 2))
            rw  = max(1, min(int(rw * scale), sw - rx - 1))
            rh  = max(1, min(int(rh * scale), sh - ry - 1))

            self.progress.emit(15)

            # ----------------------------------------------------------
            # 2. GrabCut
            # ----------------------------------------------------------
            mask       = np.zeros(bgr_small.shape[:2], np.uint8)
            bgd_model  = np.zeros((1, 65), np.float64)
            fgd_model  = np.zeros((1, 65), np.float64)

            cv2.grabCut(bgr_small, mask, (rx, ry, rw, rh),
                        bgd_model, fgd_model,
                        self.iter_count, cv2.GC_INIT_WITH_RECT)

            self.progress.emit(60)

            # 二值前景 mask（小尺寸）
            fg_small = np.where(
                (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
            ).astype(np.uint8)

            # ----------------------------------------------------------
            # 3. 形态学修复（在缩放图上操作，速度快）
            # ----------------------------------------------------------
            # 3a. 闭运算：填补前景内部的小空洞
            k_close = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (_odd(max(3, int(min(sh, sw) * 0.012))),) * 2
            )
            fg_small = cv2.morphologyEx(fg_small, cv2.MORPH_CLOSE,
                                        k_close, iterations=2)

            # 3b. 开运算：去除边缘细碎噪点
            k_open = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (_odd(max(3, int(min(sh, sw) * 0.006))),) * 2
            )
            fg_small = cv2.morphologyEx(fg_small, cv2.MORPH_OPEN,
                                        k_open, iterations=1)

            self.progress.emit(70)

            # ----------------------------------------------------------
            # 4. 保留最大连通域（丢弃孤立碎块）
            # ----------------------------------------------------------
            fg_small = _keep_largest_component(fg_small)

            self.progress.emit(78)

            # ----------------------------------------------------------
            # 5. 放大 mask 回原始尺寸（双线性插值 → 自然过渡）
            # ----------------------------------------------------------
            if scale != 1.0:
                fg_full = cv2.resize(fg_small, (orig_w, orig_h),
                                     interpolation=cv2.INTER_LINEAR)
            else:
                fg_full = fg_small.copy()

            self.progress.emit(85)

            # ----------------------------------------------------------
            # 6. 边缘羽化：仅对边缘区域做软 alpha 过渡
            # ----------------------------------------------------------
            fg_full = _feather_edges(fg_full, orig_h, orig_w)

            self.progress.emit(95)

            # ----------------------------------------------------------
            # 7. 合并到 BGRA：背景 alpha=0，主体 alpha=前景 mask 值
            # ----------------------------------------------------------
            result = self.img.copy()
            result[:, :, 3] = fg_full

            self.progress.emit(100)
            self.finished.emit(result)

        except Exception as exc:
            self.failed.emit(str(exc))


# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------

def _odd(n: int) -> int:
    """确保 kernel 尺寸为奇数。"""
    return n if n % 2 == 1 else n + 1


def _keep_largest_component(mask: np.ndarray) -> np.ndarray:
    """
    连通域分析：只保留面积最大的前景区域，过滤掉孤立碎块。
    同时保留面积 ≥ 最大区域 20% 的其他区域（避免主体被切割）。
    """
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if num_labels <= 2:
        return mask   # 只有背景 + 一个前景，无需处理

    # stats[0] 是背景，从 1 开始
    areas = stats[1:, cv2.CC_STAT_AREA]
    max_area = int(areas.max())
    threshold = max_area * 0.20   # 保留面积超过最大区域 20% 的连通域

    result = np.zeros_like(mask)
    for i, area in enumerate(areas):
        if area >= threshold:
            result[labels == (i + 1)] = 255
    return result


def _feather_edges(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    """
    对前景 mask 的边缘做高斯羽化，生成平滑的 alpha 通道。

    策略：
    - 核心区域（离边缘较远）保持 alpha=255（完全不透明）
    - 边缘区域用 Gaussian blur 产生软过渡
    - 背景区域（mask==0）保持 alpha=0
    """
    # 羽化半径：图像短边的约 0.5%，最小 3px，最大 15px
    feather_r = max(3, min(15, int(min(h, w) * 0.005)))
    ksize = _odd(feather_r * 2 + 1)

    # 对整个 mask 做高斯模糊（边界处自然衰减）
    soft = cv2.GaussianBlur(mask, (ksize, ksize), 0)

    # 规则：
    #   mask==255 → 取 max(soft, 200) 保证核心区不透明
    #   mask==0   → 取 min(soft, 55)  背景仅允许微弱羽化溢出，避免大片半透
    alpha = np.where(mask == 255,
                     np.clip(soft.astype(np.int32) + 30, 0, 255),
                     np.clip(soft.astype(np.int32) - 30, 0, 255)
                     ).astype(np.uint8)

    # 再做一次阈值保护：让核心前景锁死在 255
    core = cv2.erode(mask, np.ones((3, 3), np.uint8), iterations=feather_r // 2)
    alpha = np.where(core == 255, 255, alpha).astype(np.uint8)

    return alpha
