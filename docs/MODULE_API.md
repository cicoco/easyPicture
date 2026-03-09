# EasyPicture 模块接口设计文档

**版本**：v1.0  
**日期**：2026-03-09

---

## 一、模块依赖关系

```
main.py
  └── AppController
        ├── MainWindow（UI）
        │     ├── Canvas
        │     ├── ToolBar
        │     └── StatusBar
        ├── ImageModel（数据）
        ├── ImageProcessor（处理）
        ├── GrabCutProcessor（抠图）
        └── HistoryManager（历史）
```

---

## 二、core/image_model.py

### `class ImageModel`

```python
class ImageModel:
    """持有当前编辑图像的所有状态，作为唯一数据源。"""

    @property
    def image(self) -> np.ndarray | None:
        """当前工作图像（BGRA, uint8），未打开图片时为 None。"""

    @property
    def width(self) -> int:
        """图像宽度（像素），无图片时为 0。"""

    @property
    def height(self) -> int:
        """图像高度（像素），无图片时为 0。"""

    @property
    def has_alpha(self) -> bool:
        """当前图像是否有实际透明内容（alpha 通道非全 255）。"""

    @property
    def is_dirty(self) -> bool:
        """是否有未保存的修改。"""

    @property
    def source_path(self) -> str | None:
        """原始文件路径，None 表示新建或未打开。"""

    @property
    def selection(self) -> tuple[int, int, int, int] | None:
        """当前选区 (x1, y1, x2, y2)，图像坐标系，无选区时为 None。"""

    def set_image(self, img: np.ndarray, path: str | None = None) -> None:
        """设置新图像，重置 dirty 状态和选区。"""

    def update_image(self, img: np.ndarray) -> None:
        """更新图像内容（编辑操作后调用），标记为 dirty。"""

    def set_selection(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """设置选区，坐标自动归一化（确保 x1<x2, y1<y2）。"""

    def clear_selection(self) -> None:
        """清除当前选区。"""

    def mark_saved(self) -> None:
        """标记为已保存状态。"""
```

---

## 三、core/image_processor.py

### `class ImageProcessor`

所有方法均为纯函数（无状态），不修改输入，返回新数组。

```python
class ImageProcessor:

    @staticmethod
    def read_image(path: str) -> np.ndarray:
        """
        读取图片文件，返回 BGRA uint8 数组。
        - 支持 PNG/JPG/BMP/TIFF/WEBP
        - 灰度图自动转 BGRA
        - 3 通道 BGR 自动添加 alpha=255
        - 兼容中文路径（Windows）
        
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件无法解码
        """

    @staticmethod
    def write_image(img: np.ndarray, path: str, quality: int = 95) -> None:
        """
        将图像写入文件。
        - PNG/TIFF：无损，保留 alpha 通道
        - JPG：quality 参数控制质量（1-100），alpha 通道合并到白底
        - 兼容中文路径
        
        Args:
            img:     BGRA 图像数组
            path:    目标文件路径（含扩展名）
            quality: JPG 质量（1-100），仅对 JPG 有效，默认 95
        
        Raises:
            PermissionError: 无写入权限
            ValueError: 不支持的格式
        """

    @staticmethod
    def crop(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """
        裁剪图像。
        
        Args:
            img:        BGRA 图像
            x1, y1:    左上角（图像坐标）
            x2, y2:    右下角（图像坐标，不含）
        
        Returns:
            裁剪后的新 BGRA 数组
        """

    @staticmethod
    def rotate_90cw(img: np.ndarray) -> np.ndarray:
        """顺时针旋转 90°，无插值，完全无损。"""

    @staticmethod
    def rotate_90ccw(img: np.ndarray) -> np.ndarray:
        """逆时针旋转 90°，无插值，完全无损。"""

    @staticmethod
    def rotate_180(img: np.ndarray) -> np.ndarray:
        """旋转 180°，无插值，完全无损。"""

    @staticmethod
    def rotate_arbitrary(img: np.ndarray, angle: float,
                         expand: bool = True) -> np.ndarray:
        """
        任意角度旋转。
        
        Args:
            img:    BGRA 图像
            angle:  旋转角度（度），正值逆时针，负值顺时针
            expand: True 时扩展画布保留完整内容；False 时保持原尺寸（内容可能被裁剪）
        
        Returns:
            旋转后的 BGRA 数组（使用 LANCZOS4 插值）
        """

    @staticmethod
    def delete_selection(img: np.ndarray,
                         x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """
        将矩形选区内容设为透明（alpha=0）。
        
        Args:
            img:        BGRA 图像
            x1,y1,x2,y2: 选区坐标（图像坐标系）
        
        Returns:
            修改后的新 BGRA 数组（原数组不变）
        """

    @staticmethod
    def trim_to_content(img: np.ndarray,
                        threshold: int = 0) -> np.ndarray:
        """
        裁去图片四周多余的透明像素，保留主体内容的最小边界框（F-08）。

        等同于 Photoshop「图像 → 裁切 → 基于透明像素」。

        算法：
            1. 取 alpha 通道，找所有 alpha > threshold 的像素
            2. 计算其行列最小/最大下标（bounding box）
            3. 裁切并返回新数组

        Args:
            img:       BGRA 图像（必须含 alpha 通道）
            threshold: 判定"透明"的 alpha 阈值（0-255），默认 0（即 alpha=0 才算透明）

        Returns:
            裁切后的新 BGRA 数组，尺寸 ≤ 原图

        Raises:
            ValueError: 图片全透明，无内容可保留
        """

    @staticmethod
    def resize_to_size(img: np.ndarray,
                       target_w: int,
                       target_h: int,
                       keep_aspect: bool = True) -> np.ndarray:
        """
        将图片重采样到指定尺寸（F-09）。

        - keep_aspect=True：等比缩放，以较小约束边生效；若只约束单边，另一边传 0。
        - keep_aspect=False：拉伸到精确 target_w × target_h。
        - 缩小时使用 LANCZOS4，放大时使用 CUBIC。

        Args:
            img:         BGRA 图像
            target_w:    目标宽度（像素）；0 = 按高度自动计算（keep_aspect=True 有效）
            target_h:    目标高度（像素）；0 = 按宽度自动计算（keep_aspect=True 有效）
            keep_aspect: 是否保持宽高比，默认 True

        Returns:
            重采样后的新 BGRA 数组

        Raises:
            ValueError: target_w 和 target_h 同时为 0，或值为负
        """

    @staticmethod
    def alpha_composite_white(img: np.ndarray) -> np.ndarray:
        """
        将 BGRA 图像合并到白色背景，返回 BGR 图像。
        用于 JPG 导出时处理透明区域。
        """
```

---

## 四、core/grabcut.py

### `class GrabCutWorker`

```python
class GrabCutWorker(QObject):
    """
    在 QThread 中执行 GrabCut 抠图 + 后处理流水线，避免阻塞主线程。

    后处理步骤（按顺序）：
      1. 形态学闭运算 — 填补前景内部空洞
      2. 形态学开运算 — 去除边缘碎噪点
      3. 连通域过滤   — 只保留最大连通域及面积 ≥ 20% 的区域
      4. INTER_LINEAR 放大 mask — 消除锯齿
      5. 高斯边缘羽化 — 生成软 alpha 过渡，核心区锁定 255
    """

    finished = Signal(object)   # np.ndarray BGRA — 抠图完成
    failed   = Signal(str)      # str — 错误信息
    progress = Signal(int)      # int 0-100 — 进度

    def __init__(self, img: np.ndarray,
                 rect: tuple[int, int, int, int],
                 iter_count: int = 5) -> None:
        """
        Args:
            img:        BGRA 原始图像（深拷贝，不影响原图）
            rect:       用户框选矩形 (x, y, width, height)，图像坐标系
            iter_count: GrabCut 迭代次数，默认 5
        """

    def run(self) -> None:
        """
        执行完整抠图流水线（由 QThread.started 信号触发）。
        完成后发出 finished(bgra_result)，失败发出 failed(err_msg)。
        """
```

**辅助函数**：

```python
def _keep_largest_component(mask: np.ndarray) -> np.ndarray:
    """
    连通域分析，过滤孤立碎块。
    保留面积最大的区域 + 面积 ≥ 最大区域 20% 的其他区域。
    """

def _feather_edges(mask: np.ndarray, h: int, w: int) -> np.ndarray:
    """
    边缘羽化：对前景 mask 边界做高斯软化。
    - 核心区（远离边界）: alpha = 255
    - 边缘过渡区: alpha = Gaussian blur 值（0~255 连续）
    - 背景区: alpha = 0
    羽化半径 = max(3, min(15, min(h,w) * 0.5%))
    """
```

**使用示例**：

```python
# 在 AppController 中
thread = QThread()
worker = GrabCutWorker(img=self.model.image.copy(), rect=(x, y, w, h))
worker.moveToThread(thread)

worker.finished.connect(self._on_grabcut_done)
worker.failed.connect(self._on_grabcut_failed)
worker.progress.connect(self._progress_dialog.setValue)
thread.started.connect(worker.run)
thread.start()
```

---

## 五、core/history.py

### `class HistoryManager`

```python
class HistoryManager:
    """
    图像编辑历史管理，支持撤销（Undo）和重做（Redo）。
    每个历史条目存储图像数组的深拷贝。
    """

    MAX_STEPS: int = 20  # 最大历史步数

    def push(self, img: np.ndarray) -> None:
        """
        保存当前图像状态到历史栈。
        - 执行 push 后，redo 历史清空
        - 超过 MAX_STEPS 时，删除最旧的条目
        """

    def undo(self) -> np.ndarray | None:
        """
        撤销到上一步。
        
        Returns:
            上一步的图像数组，已无法撤销时返回 None
        """

    def redo(self) -> np.ndarray | None:
        """
        重做下一步。
        
        Returns:
            下一步的图像数组，已无法重做时返回 None
        """

    @property
    def can_undo(self) -> bool:
        """是否可以撤销。"""

    @property
    def can_redo(self) -> bool:
        """是否可以重做。"""

    def clear(self) -> None:
        """清空所有历史（打开新图片时调用）。"""
```

---

## 六、ui/canvas.py

### `class Canvas(QWidget)`

```python
class Canvas(QWidget):
    """
    画布组件：图片显示 + 鼠标交互（选区、裁剪等）。
    """

    # 信号
    selection_changed = Signal(int, int, int, int)  # 选区变化 (x1, y1, x2, y2)，图像坐标
    selection_cleared = Signal()                    # 选区取消

    class Tool(Enum):
        NONE      = 0   # 无工具（只浏览）
        SELECT    = 1   # 矩形选框
        CROP      = 2   # 裁剪模式
        GRABCUT   = 3   # 抠图框选

    def set_image(self, img: np.ndarray) -> None:
        """设置并显示新图像，重置缩放和选区。"""

    def refresh(self, img: np.ndarray) -> None:
        """更新图像内容（保持当前缩放和选区）。"""

    def set_tool(self, tool: Tool) -> None:
        """切换当前工具，不同工具影响鼠标交互行为。"""

    def zoom_in(self) -> None:
        """放大视图（步进 25%）。"""

    def zoom_out(self) -> None:
        """缩小视图（步进 25%）。"""

    def zoom_fit(self) -> None:
        """自适应缩放，使图像完整显示在画布内。"""

    def get_selection_image_coords(self) -> tuple[int,int,int,int] | None:
        """
        获取当前选区的图像坐标 (x1, y1, x2, y2)。
        无选区时返回 None。
        """
```

---

## 七、controller/app_controller.py

### `class AppController`

```python
class AppController:
    """
    协调 UI 事件与核心处理逻辑的中间层。
    """

    def __init__(self, window: MainWindow):
        """初始化，创建所有子模块并连接信号。"""

    # 文件操作
    def open_image(self) -> None:
        """打开文件对话框，读取并显示图片。"""

    def export_image(self) -> None:
        """打开导出对话框，保存图片到指定路径。"""

    # 编辑操作
    def do_crop(self) -> None:
        """执行裁剪（使用当前选区），操作前保存到历史。"""

    def do_delete_selection(self) -> None:
        """删除当前选区内容，操作前保存到历史。"""

    def do_grabcut(self) -> None:
        """启动 GrabCut 抠图（使用当前选区作为框）。"""

    def do_rotate_cw(self) -> None:
        """顺时针旋转 90°，保存到历史。"""

    def do_rotate_ccw(self) -> None:
        """逆时针旋转 90°，保存到历史。"""

    def undo(self) -> None:
        """撤销，从历史恢复图像。"""

    def redo(self) -> None:
        """重做，从历史恢复图像。"""
```

---

## 八、信号/槽连接总览

| 发送方（Signal）                          | 接收方（Slot）                            | 触发时机            |
|-----------------------------------------|-----------------------------------------|-------------------|
| `ToolBar.tool_selected(Tool)`           | `Canvas.set_tool()`                     | 工具栏点击工具按钮   |
| `ToolBar.rotate_cw_clicked`             | `AppController.do_rotate_cw()`          | 点击顺时针旋转       |
| `ToolBar.rotate_ccw_clicked`            | `AppController.do_rotate_ccw()`         | 点击逆时针旋转       |
| `ToolBar.crop_clicked`                  | `AppController.do_crop()`               | 点击裁剪确认         |
| `ToolBar.delete_clicked`                | `AppController.do_delete_selection()`   | 点击删除选区         |
| `ToolBar.grabcut_clicked`               | `AppController.do_grabcut()`            | 点击抠图执行         |
| `Canvas.selection_changed(x1,y1,x2,y2)`| `ImageModel.set_selection()`            | 鼠标拖拽完成选区     |
| `Canvas.selection_cleared`              | `ImageModel.clear_selection()`          | 按 Esc 取消选区     |
| `GrabCutProcessor.finished(img)`        | `AppController.on_grabcut_done()`       | GrabCut 完成       |
| `MainWindow.open_action.triggered`      | `AppController.open_image()`            | 菜单/快捷键打开文件  |
| `MainWindow.export_action.triggered`    | `AppController.export_image()`          | 菜单/快捷键导出文件  |
