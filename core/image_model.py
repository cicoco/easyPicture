from __future__ import annotations
from typing import Optional, Tuple
import numpy as np


class ImageModel:
    """持有当前编辑图像的所有状态，作为唯一数据源。"""

    def __init__(self) -> None:
        self._image: Optional[np.ndarray] = None
        self._source_path: Optional[str] = None
        self._is_dirty: bool = False
        self._selection: Optional[Tuple[int, int, int, int]] = None

    # ------------------------------------------------------------------
    # 只读属性
    # ------------------------------------------------------------------

    @property
    def image(self) -> Optional[np.ndarray]:
        """当前工作图像（BGRA, uint8），未打开图片时为 None。"""
        return self._image

    @property
    def width(self) -> int:
        """图像宽度（像素），无图片时为 0。"""
        if self._image is None:
            return 0
        return self._image.shape[1]

    @property
    def height(self) -> int:
        """图像高度（像素），无图片时为 0。"""
        if self._image is None:
            return 0
        return self._image.shape[0]

    @property
    def has_alpha(self) -> bool:
        """当前图像是否有实际透明内容（alpha 通道非全 255）。"""
        if self._image is None or self._image.shape[2] < 4:
            return False
        return bool(np.any(self._image[:, :, 3] < 255))

    @property
    def is_dirty(self) -> bool:
        """是否有未保存的修改。"""
        return self._is_dirty

    @property
    def source_path(self) -> Optional[str]:
        """原始文件路径，None 表示新建或未打开。"""
        return self._source_path

    @property
    def selection(self) -> Optional[Tuple[int, int, int, int]]:
        """当前选区 (x1, y1, x2, y2)，图像坐标系，无选区时为 None。"""
        return self._selection

    # ------------------------------------------------------------------
    # 变更方法
    # ------------------------------------------------------------------

    def set_image(self, img: np.ndarray, path: Optional[str] = None) -> None:
        """设置新图像，重置 dirty 状态和选区。"""
        self._image = img
        self._source_path = path
        self._is_dirty = False
        self._selection = None

    def update_image(self, img: np.ndarray) -> None:
        """更新图像内容（编辑操作后调用），标记为 dirty。"""
        self._image = img
        self._is_dirty = True

    def set_selection(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """设置选区，坐标自动归一化（确保 x1<x2, y1<y2）。"""
        nx1, nx2 = min(x1, x2), max(x1, x2)
        ny1, ny2 = min(y1, y2), max(y1, y2)
        self._selection = (nx1, ny1, nx2, ny2)

    def clear_selection(self) -> None:
        """清除当前选区。"""
        self._selection = None

    def mark_saved(self) -> None:
        """标记为已保存状态。"""
        self._is_dirty = False
