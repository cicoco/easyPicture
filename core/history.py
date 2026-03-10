from __future__ import annotations
from typing import Optional

import numpy as np


class HistoryManager:
    """图像编辑历史管理，支持撤销（Undo）和重做（Redo）。"""

    MAX_STEPS: int = 20

    def __init__(self) -> None:
        self._stack: list[np.ndarray] = []
        self._cursor: int = -1  # 指向当前状态的索引

    def push(self, img: np.ndarray) -> None:
        """保存当前图像状态，清空 redo 分支，超出上限时删除最旧条目。"""
        if self._cursor < len(self._stack) - 1:
            self._stack = self._stack[: self._cursor + 1]

        self._stack.append(img.copy())

        if len(self._stack) > self.MAX_STEPS:
            self._stack.pop(0)

        self._cursor = len(self._stack) - 1

    def undo(self) -> Optional[np.ndarray]:
        """撤销，返回上一步图像副本；无法撤销时返回 None。"""
        if self._cursor <= 0:
            return None
        self._cursor -= 1
        return self._stack[self._cursor].copy()

    def redo(self) -> Optional[np.ndarray]:
        """重做，返回下一步图像副本；无法重做时返回 None。"""
        if self._cursor >= len(self._stack) - 1:
            return None
        self._cursor += 1
        return self._stack[self._cursor].copy()

    @property
    def can_undo(self) -> bool:
        return self._cursor > 0

    @property
    def can_redo(self) -> bool:
        return self._cursor < len(self._stack) - 1

    def clear(self) -> None:
        """清空所有历史（打开新图片时调用）。"""
        self._stack.clear()
        self._cursor = -1
