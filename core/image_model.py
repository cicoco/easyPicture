from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import numpy as np


@dataclass
class ImageLayer:
    """单个图层数据。"""
    name: str
    image: np.ndarray  # BGRA
    x: int = 0
    y: int = 0
    visible: bool = True
    source_path: Optional[str] = None

    @property
    def width(self) -> int:
        return self.image.shape[1]

    @property
    def height(self) -> int:
        return self.image.shape[0]


class ImageModel:
    """持有当前编辑图像的所有状态，作为唯一数据源。"""

    def __init__(self) -> None:
        self._layers: list[ImageLayer] = []
        self._canvas_w: int = 0
        self._canvas_h: int = 0
        self._active_layer_idx: int = -1
        self._composited_cache: Optional[np.ndarray] = None
        self._composited_dirty: bool = True
        self._source_path: Optional[str] = None
        self._is_dirty: bool = False
        self._selection: Optional[Tuple[int, int, int, int]] = None

    # ------------------------------------------------------------------
    # 只读属性
    # ------------------------------------------------------------------

    @property
    def image(self) -> Optional[np.ndarray]:
        """当前工作图像（所有可见图层合成结果），未打开图片时为 None。"""
        if not self._layers:
            return None
        return self._get_composited_image_copy()

    @property
    def width(self) -> int:
        """图像宽度（像素），无图片时为 0。"""
        return self._canvas_w

    @property
    def height(self) -> int:
        """图像高度（像素），无图片时为 0。"""
        return self._canvas_h

    @property
    def has_alpha(self) -> bool:
        """当前图像是否有实际透明内容（alpha 通道非全 255）。"""
        merged = self.image
        if merged is None or merged.shape[2] < 4:
            return False
        return bool(np.any(merged[:, :, 3] < 255))

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

    @property
    def layers(self) -> list[ImageLayer]:
        """按底->顶顺序返回图层列表。"""
        return self._layers

    @property
    def active_layer_index(self) -> int:
        return self._active_layer_idx

    @property
    def active_layer(self) -> Optional[ImageLayer]:
        if 0 <= self._active_layer_idx < len(self._layers):
            return self._layers[self._active_layer_idx]
        return None

    # ------------------------------------------------------------------
    # 变更方法
    # ------------------------------------------------------------------

    def set_image(self, img: np.ndarray, path: Optional[str] = None) -> None:
        """设置新图像，重置 dirty 状态和选区。"""
        name = Path(path).name if path else "图层 1"
        self._layers = [
            ImageLayer(
                name=name, image=img.copy(), x=0, y=0, visible=True, source_path=path
            )
        ]
        self._canvas_w = img.shape[1]
        self._canvas_h = img.shape[0]
        self._active_layer_idx = 0
        self._composited_cache = None
        self._composited_dirty = True
        self._source_path = path
        self._is_dirty = False
        self._selection = None

    def update_image(self, img: np.ndarray) -> None:
        """
        更新图像内容（编辑操作后调用），会将当前内容扁平化为单图层。
        用于兼容现有旋转/裁剪/抠图等处理流程。
        """
        self._layers = [ImageLayer(name="合并结果", image=img.copy(), x=0, y=0, visible=True)]
        self._canvas_w = img.shape[1]
        self._canvas_h = img.shape[0]
        self._active_layer_idx = 0
        self._composited_cache = None
        self._composited_dirty = True
        self._is_dirty = True
        self._selection = None

    def add_layer(self, img: np.ndarray, name: str, source_path: Optional[str] = None) -> None:
        """添加新图层到顶层。"""
        if not self._layers:
            self.set_image(img, source_path or name)
            self._source_path = None
            self._is_dirty = True
            return

        self._layers.append(
            ImageLayer(
                name=name, image=img.copy(), x=0, y=0, visible=True, source_path=source_path
            )
        )
        self._active_layer_idx = len(self._layers) - 1
        self._ensure_canvas_size()
        self._composited_dirty = True
        self._is_dirty = True

    def set_active_layer(self, idx: int) -> None:
        if 0 <= idx < len(self._layers):
            self._active_layer_idx = idx

    def move_layer_to(self, idx: int, x: int, y: int) -> None:
        if not (0 <= idx < len(self._layers)):
            return
        layer = self._layers[idx]
        max_x = max(0, self._canvas_w - layer.width)
        max_y = max(0, self._canvas_h - layer.height)
        layer.x = max(0, min(x, max_x))
        layer.y = max(0, min(y, max_y))
        self._composited_dirty = True
        self._is_dirty = True

    def set_layer_visible(self, idx: int, visible: bool) -> bool:
        """设置图层可见性，状态发生变化时返回 True。"""
        if not (0 <= idx < len(self._layers)):
            return False
        layer = self._layers[idx]
        if layer.visible == visible:
            return False
        layer.visible = visible
        self._composited_dirty = True
        self._is_dirty = True
        return True

    def reorder_layer(self, idx: int, action: str) -> int:
        """
        调整图层顺序。
        action: "up" | "down" | "top" | "bottom"
        返回调整后的图层索引；失败返回原索引。
        """
        if not (0 <= idx < len(self._layers)):
            return idx
        if len(self._layers) <= 1:
            return idx

        new_idx = idx
        if action == "up" and idx < len(self._layers) - 1:
            new_idx = idx + 1
        elif action == "down" and idx > 0:
            new_idx = idx - 1
        elif action == "top":
            new_idx = len(self._layers) - 1
        elif action == "bottom":
            new_idx = 0
        else:
            return idx

        layer = self._layers.pop(idx)
        self._layers.insert(new_idx, layer)
        self._active_layer_idx = new_idx
        self._composited_dirty = True
        self._is_dirty = True
        return new_idx

    def reorder_layers_by_indices(self, order: list[int]) -> bool:
        """
        按给定顺序重排图层。
        order 表示“新顺序（底->顶）由旧索引组成”的列表。
        """
        n = len(self._layers)
        if n <= 1:
            return False
        if len(order) != n or set(order) != set(range(n)):
            return False
        if order == list(range(n)):
            return False

        old_layers = self._layers
        self._layers = [old_layers[i] for i in order]
        old_active = self._active_layer_idx
        if old_active >= 0:
            self._active_layer_idx = order.index(old_active)
        self._composited_dirty = True
        self._is_dirty = True
        return True

    def remove_layer(self, idx: int) -> bool:
        """删除指定图层，成功返回 True。"""
        if not (0 <= idx < len(self._layers)):
            return False
        self._layers.pop(idx)
        if not self._layers:
            self._canvas_w = 0
            self._canvas_h = 0
            self._active_layer_idx = -1
            self._composited_cache = None
        else:
            self._ensure_canvas_size()
            self._active_layer_idx = min(idx, len(self._layers) - 1)
            self._composited_dirty = True
        self._is_dirty = True
        self._selection = None
        return True

    def clear_layers(self) -> bool:
        """清空所有图层，成功返回 True。"""
        if not self._layers:
            return False
        self._layers = []
        self._canvas_w = 0
        self._canvas_h = 0
        self._active_layer_idx = -1
        self._composited_cache = None
        self._composited_dirty = True
        self._selection = None
        self._is_dirty = True
        return True

    def pick_top_layer(self, x: int, y: int) -> int:
        """
        根据画布坐标选中最上层命中图层。
        优先依据 alpha>0，透明像素不算命中。
        """
        for i in range(len(self._layers) - 1, -1, -1):
            layer = self._layers[i]
            if not layer.visible:
                continue
            lx = x - layer.x
            ly = y - layer.y
            if lx < 0 or ly < 0 or lx >= layer.width or ly >= layer.height:
                continue
            if layer.image.shape[2] < 4 or layer.image[ly, lx, 3] > 0:
                return i
        return -1

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

    def get_state_snapshot(self) -> dict:
        """导出当前完整状态快照，用于撤销/重做。"""
        layers = [{
            "name": layer.name,
            "image": layer.image.copy(),
            "x": layer.x,
            "y": layer.y,
            "visible": layer.visible,
            "source_path": layer.source_path,
        } for layer in self._layers]
        return {
            "layers": layers,
            "canvas_w": self._canvas_w,
            "canvas_h": self._canvas_h,
            "active_layer_idx": self._active_layer_idx,
            "source_path": self._source_path,
            "selection": self._selection,
            "is_dirty": self._is_dirty,
        }

    def restore_from_snapshot(self, snapshot: dict) -> None:
        """从快照恢复完整状态。"""
        self._layers = [
            ImageLayer(
                name=item["name"],
                image=item["image"].copy(),
                x=int(item["x"]),
                y=int(item["y"]),
                visible=bool(item["visible"]),
                source_path=item.get("source_path"),
            )
            for item in snapshot.get("layers", [])
        ]
        self._canvas_w = int(snapshot.get("canvas_w", 0))
        self._canvas_h = int(snapshot.get("canvas_h", 0))
        self._active_layer_idx = int(snapshot.get("active_layer_idx", -1))
        self._source_path = snapshot.get("source_path")
        self._selection = snapshot.get("selection")
        self._is_dirty = bool(snapshot.get("is_dirty", False))
        self._composited_cache = None
        self._composited_dirty = True

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _ensure_canvas_size(self) -> None:
        if not self._layers:
            self._canvas_w = 0
            self._canvas_h = 0
            return
        w = 0
        h = 0
        for layer in self._layers:
            w = max(w, layer.x + layer.width)
            h = max(h, layer.y + layer.height)
        self._canvas_w = w
        self._canvas_h = h

    def _compose_layers(self) -> np.ndarray:
        base = np.zeros((self._canvas_h, self._canvas_w, 4), dtype=np.uint8)
        dst_rgb = base[:, :, :3].astype(np.float32)
        dst_a = base[:, :, 3:4].astype(np.float32) / 255.0

        for layer in self._layers:
            if not layer.visible:
                continue
            x1 = layer.x
            y1 = layer.y
            x2 = min(self._canvas_w, layer.x + layer.width)
            y2 = min(self._canvas_h, layer.y + layer.height)
            if x2 <= x1 or y2 <= y1:
                continue

            src = layer.image[: y2 - y1, : x2 - x1].astype(np.float32)
            src_rgb = src[:, :, :3]
            src_a = src[:, :, 3:4] / 255.0

            region_rgb = dst_rgb[y1:y2, x1:x2]
            region_a = dst_a[y1:y2, x1:x2]
            out_a = src_a + region_a * (1.0 - src_a)
            safe_out_a = np.where(out_a > 1e-6, out_a, 1.0)
            out_rgb = (src_rgb * src_a + region_rgb * region_a * (1.0 - src_a)) / safe_out_a

            dst_rgb[y1:y2, x1:x2] = out_rgb
            dst_a[y1:y2, x1:x2] = out_a

        out = np.empty_like(base)
        out[:, :, :3] = np.clip(dst_rgb, 0, 255).astype(np.uint8)
        out[:, :, 3] = np.clip(dst_a[:, :, 0] * 255.0, 0, 255).astype(np.uint8)
        return out

    def _get_composited_image_copy(self) -> np.ndarray:
        if self._composited_cache is None or self._composited_dirty:
            self._composited_cache = self._compose_layers()
            self._composited_dirty = False
        # 返回副本，避免外部意外修改内部缓存
        return self._composited_cache.copy()
