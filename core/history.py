from __future__ import annotations
from copy import deepcopy
from typing import Any, Optional


class HistoryManager:
    """编辑历史管理，支持任意可深拷贝状态的撤销（Undo）和重做（Redo）。"""

    MAX_STEPS: int = 20

    def __init__(self) -> None:
        self._stack: list[Any] = []
        self._cursor: int = -1  # 指向当前状态的索引

    def push(self, state: Any) -> None:
        """保存当前状态，清空 redo 分支，超出上限时删除最旧条目。"""
        if self._cursor < len(self._stack) - 1:
            self._stack = self._stack[: self._cursor + 1]

        self._stack.append(deepcopy(state))

        if len(self._stack) > self.MAX_STEPS:
            self._stack.pop(0)

        self._cursor = len(self._stack) - 1

    def undo(self) -> Optional[Any]:
        """撤销，返回上一步状态副本；无法撤销时返回 None。"""
        if self._cursor <= 0:
            return None
        self._cursor -= 1
        return deepcopy(self._stack[self._cursor])

    def redo(self) -> Optional[Any]:
        """重做，返回下一步状态副本；无法重做时返回 None。"""
        if self._cursor >= len(self._stack) - 1:
            return None
        self._cursor += 1
        return deepcopy(self._stack[self._cursor])

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
