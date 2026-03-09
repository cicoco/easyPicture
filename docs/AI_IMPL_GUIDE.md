# EasyPicture AI 实现步骤指南

**目标**：指导 AI 分阶段、可验证地实现 EasyPicture 桌面图片编辑工具。  
**原则**：每步只做一件事，步骤完成后有明确的验证方式，前一步是后一步的前提。

---

## 阅读前提

在开始任何步骤前，AI 必须先阅读以下文档：
- `docs/PRD.md` — 了解产品功能边界
- `docs/TECH_DESIGN.md` — 了解架构设计和技术细节
- `docs/MODULE_API.md` — 了解各模块的接口定义

---

## 实现阶段总览

```
Phase 0: 环境初始化
Phase 1: 数据模型层
Phase 2: 图像处理核心层
Phase 3: 主窗口与画布骨架
Phase 4: 文件导入/导出
Phase 5: 旋转功能
Phase 6: 区域选择与裁剪
Phase 7: 删除选区内容
Phase 8: GrabCut 抠图
Phase 9: 撤销/重做
Phase 10: 体验打磨与打包
```

---

## Phase 0：环境初始化

### Step 0.1 — 创建项目结构与依赖文件

**任务**：创建完整目录结构和 `pyproject.toml`（使用 uv 管理依赖）。

**创建以下文件和目录**：

```
easyPicture/
├── main.py                  （空文件占位）
├── pyproject.toml           （uv 项目配置，替代 requirements.txt）
├── resources/
│   └── icons/               （空目录，后续放图标）
├── ui/
│   ├── __init__.py
│   ├── main_window.py       （空文件占位）
│   ├── canvas.py            （空文件占位）
│   ├── toolbar.py           （空文件占位）
│   └── dialogs.py           （空文件占位）
├── core/
│   ├── __init__.py
│   ├── image_model.py       （空文件占位）
│   ├── image_processor.py   （空文件占位）
│   ├── grabcut.py           （空文件占位）
│   └── history.py           （空文件占位）
└── controller/
    ├── __init__.py
    └── app_controller.py    （空文件占位）
```

**pyproject.toml 内容**：
```toml
[project]
name = "easypicture"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "opencv-python>=4.8.0",
    "PyQt6>=6.5.0",
    "numpy>=1.24.0",
    "Pillow>=10.0.0",
]

[project.scripts]
easypicture = "main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**验证**：运行 `uv sync` 无报错；`uv run python -c "import cv2, PyQt6, numpy"` 成功。

---

### Step 0.2 — 创建最小可运行空窗口

**任务**：`main.py` 创建最小 PyQt6 空白窗口，确认环境正常。

**main.py 实现要求**：
- 创建 `QApplication`
- 创建 `QMainWindow`，标题为 "EasyPicture"，窗口尺寸 1280×800
- 调用 `app.exec()` 进入事件循环

**验证**：运行 `uv run python main.py` 能弹出空白窗口，无报错退出。

---

## Phase 1：数据模型层

### Step 1.1 — 实现 ImageModel

**文件**：`core/image_model.py`

**实现要求**（参考 `docs/MODULE_API.md` 第二节）：
- 所有属性和方法按接口文档实现
- `set_image()` 调用后：`is_dirty=False`，`selection=None`，`source_path` 更新
- `update_image()` 调用后：`is_dirty=True`
- `set_selection()` 需要保证 `x1 < x2, y1 < y2`（自动 normalize）
- `current_image` 始终为 BGRA 格式（shape[-1] == 4）

**验证**（在 Python shell 中）：
```python
import numpy as np
from core.image_model import ImageModel
m = ImageModel()
assert m.image is None
assert m.is_dirty == False

fake = np.zeros((100, 200, 4), dtype=np.uint8)
m.set_image(fake, "/tmp/test.png")
assert m.width == 200
assert m.height == 100
assert m.is_dirty == False

m.update_image(fake.copy())
assert m.is_dirty == True

m.set_selection(50, 30, 10, 10)
x1,y1,x2,y2 = m.selection
assert x1 < x2 and y1 < y2  # 验证自动 normalize

m.clear_selection()
assert m.selection is None
print("ImageModel: OK")
```

---

## Phase 2：图像处理核心层

### Step 2.1 — 实现 ImageProcessor 基础 I/O

**文件**：`core/image_processor.py`

**仅实现 `read_image` 和 `write_image`**（参考 `docs/TECH_DESIGN.md` 第 4.1、4.2 节）：

`read_image` 要求：
- 使用 `np.fromfile` + `cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)` 读取
- 灰度图转 BGRA，BGR 图添加 alpha=255 通道
- 返回统一的 BGRA ndarray
- 抛出 `FileNotFoundError` 和 `ValueError`

`write_image` 要求：
- PNG：`cv2.IMWRITE_PNG_COMPRESSION=1`，保留 alpha，使用 `.tofile()` 写入
- JPG：先调用 `alpha_composite_white()` 去除透明，再用 `IMWRITE_JPEG_QUALITY` 写入
- TIFF：直接无损写入

`alpha_composite_white` 要求：
- 将 BGRA 的透明区域合成到白色背景，返回 BGR

**验证**：
```python
from core.image_processor import ImageProcessor
import numpy as np

# 创建测试 BGRA 图像（红色，半透明）
img = np.zeros((100, 100, 4), dtype=np.uint8)
img[:, :, 2] = 255  # R
img[:, :, 3] = 128  # alpha
ImageProcessor.write_image(img, "/tmp/test_out.png")

# 读回并验证
read_back = ImageProcessor.read_image("/tmp/test_out.png")
assert read_back.shape == (100, 100, 4), f"shape error: {read_back.shape}"
assert read_back.dtype == np.uint8
print("ImageProcessor I/O: OK")
```

---

### Step 2.2 — 实现 ImageProcessor 变换操作

**文件**：`core/image_processor.py`（继续追加）

**实现**：`crop`、`rotate_90cw`、`rotate_90ccw`、`rotate_180`、`rotate_arbitrary`、`delete_selection`

关键实现要求：
- `rotate_90cw/ccw/180` 使用 `cv2.rotate()`，**不得使用仿射变换**（保证无损）
- `rotate_arbitrary` 使用 `cv2.getRotationMatrix2D` + `cv2.warpAffine`，`flags=cv2.INTER_LANCZOS4`，`expand=True` 时计算新画布尺寸以保留完整内容
- `crop` 对坐标做 clamp 防止越界
- `delete_selection` 返回新数组（不改变输入），将选区的 alpha 通道置为 0

**验证**：
```python
from core.image_processor import ImageProcessor
import numpy as np

img = np.zeros((100, 200, 4), dtype=np.uint8)
img[:, :, 3] = 255

# 裁剪
cropped = ImageProcessor.crop(img, 10, 20, 110, 80)
assert cropped.shape == (60, 100, 4)

# 旋转
r90 = ImageProcessor.rotate_90cw(img)
assert r90.shape == (200, 100, 4)
r180 = ImageProcessor.rotate_180(img)
assert r180.shape == (100, 200, 4)
r90x4 = img
for _ in range(4):
    r90x4 = ImageProcessor.rotate_90cw(r90x4)
assert np.array_equal(r90x4, img), "旋转4次应还原"

# 删除选区
deleted = ImageProcessor.delete_selection(img, 10, 10, 50, 50)
assert deleted[30, 30, 3] == 0     # 选区内透明
assert deleted[80, 80, 3] == 255   # 选区外不变
assert img[30, 30, 3] == 255       # 原数组不变

print("ImageProcessor transforms: OK")
```

---

### Step 2.3 — 实现 HistoryManager

**文件**：`core/history.py`

**实现要求**（参考 `docs/MODULE_API.md` 第五节）：
- `push` 存储深拷贝（`img.copy()`），不存引用
- 超过 `MAX_STEPS=20` 时删除最旧条目
- `push` 后清空 redo 分支
- `undo`/`redo` 返回图像副本（不返回内部引用）

**验证**：
```python
from core.history import HistoryManager
import numpy as np

h = HistoryManager()
assert not h.can_undo
assert not h.can_redo

imgs = [np.full((10,10,4), i, dtype=np.uint8) for i in range(5)]
for img in imgs:
    h.push(img)

assert h.can_undo
assert not h.can_redo

prev = h.undo()
assert prev[0,0,0] == 3  # 回到第4张

prev2 = h.undo()
assert prev2[0,0,0] == 2  # 回到第3张

redone = h.redo()
assert redone[0,0,0] == 3  # 重做到第4张

# push 后 redo 清空
h.push(imgs[0])
assert not h.can_redo

print("HistoryManager: OK")
```

---

## Phase 3：主窗口与画布骨架

### Step 3.1 — 实现 ToolBar

**文件**：`ui/toolbar.py`

**实现要求**：
- 继承 `QToolBar` 或 `QWidget`（竖向排列）
- 包含以下工具按钮（用文字标签即可，图标后续补充）：
  - 选框（SELECT）
  - 裁剪（CROP）
  - 抠图（GRABCUT）
  - 删除选区（DELETE）
  - 顺时针旋转（ROTATE_CW）
  - 逆时针旋转（ROTATE_CCW）
- 每个按钮点击后发出对应 Signal：
  - `tool_selected = Signal(int)` — 工具切换时发出工具枚举值
  - `rotate_cw_clicked = Signal()`
  - `rotate_ccw_clicked = Signal()`
  - `crop_clicked = Signal()`
  - `delete_clicked = Signal()`
  - `grabcut_clicked = Signal()`
- 工具按钮（SELECT/CROP/GRABCUT）互斥高亮（选中态）

**验证**：视觉检查——运行后侧边出现竖向工具按钮，点击可切换高亮状态。

---

### Step 3.2 — 实现 Canvas 骨架（显示 + 缩放）

**文件**：`ui/canvas.py`

**此步骤只实现图片显示和视图缩放，不含选区交互**。

**实现要求**：
- 继承 `QWidget`，使用 `QPainter` 在 `paintEvent` 中绘制
- `set_image(img: np.ndarray)` — 将 BGRA ndarray 转为 `QPixmap` 并显示
- `refresh(img: np.ndarray)` — 更新图像，保持当前 zoom
- `zoom_factor` 初始值 1.0
- `zoom_fit()` — 计算最合适的缩放比例使图片完整显示在窗口内
- `zoom_in()` / `zoom_out()` — 步进 ±0.25
- `Ctrl/Cmd + 滚轮` 触发缩放
- 空格键 + 鼠标拖动 实现画布平移（记录 `pan_offset`）
- ndarray → QPixmap 转换使用 `docs/TECH_DESIGN.md` 第 4.3 节的方法

**验证**：能加载并显示一张图片，滚轮缩放正常，空格拖动正常。

---

### Step 3.3 — 实现 MainWindow 并串联

**文件**：`ui/main_window.py`，同步更新 `main.py`

**实现要求**：
- `MainWindow` 继承 `QMainWindow`
- 布局：左侧 `ToolBar`，中央 `Canvas`，底部 `StatusBar`
- 菜单栏包含：
  - 文件菜单：打开（Ctrl+O）、导出（Ctrl+S）、退出
  - 编辑菜单：撤销（Ctrl+Z）、重做（Ctrl+Shift+Z / Ctrl+Y）
- 状态栏显示：图片尺寸（如 `1920×1080`）、当前缩放（如 `75%`）、当前工具名称
- 提供以下 Signal 供 Controller 连接：
  - `open_triggered = Signal()`
  - `export_triggered = Signal()`
  - `undo_triggered = Signal()`
  - `redo_triggered = Signal()`
- `main.py` 中实例化 `MainWindow` 并调用 `show()`

**验证**：运行后看到完整窗口布局（工具栏+画布+状态栏+菜单栏），菜单可点击但功能暂未实现。

---

## Phase 4：文件导入/导出

### Step 4.1 — 实现 AppController 基础骨架

**文件**：`controller/app_controller.py`

**此步骤只连接文件 I/O 信号，其他方法留空占位**。

**实现要求**：
- `__init__(self, window: MainWindow)` 中：
  - 创建 `ImageModel`、`HistoryManager` 实例
  - 创建 `ImageProcessor` 实例（或直接用静态方法）
  - 将 `window.open_triggered` 连接到 `self.open_image`
  - 将 `window.export_triggered` 连接到 `self.export_image`
  - 将 `window.toolbar.rotate_cw_clicked` 连接到 `self.do_rotate_cw`（留空占位）
  - （其他信号连接后续步骤逐步添加）

`open_image` 实现：
1. `QFileDialog.getOpenFileName`，filter 为 `"Images (*.png *.jpg *.jpeg *.bmp *.tiff *.webp)"`
2. 若用户取消则返回
3. 若 `model.is_dirty`，弹出 `QMessageBox` 询问是否保存
4. `ImageProcessor.read_image(path)` 读取图片
5. `model.set_image(img, path)`
6. `history.clear()`
7. `window.canvas.set_image(img)`
8. `window.canvas.zoom_fit()`
9. 更新状态栏：尺寸、缩放比例

`export_image` 实现：
1. 若 `model.image is None`，提示无图片
2. `QFileDialog.getSaveFileName`，filter 含 PNG/JPG/TIFF
3. 若图片有透明内容且用户选 JPG，弹出警告
4. JPG 时弹出质量选择对话框（滑块 1-100，默认 95）
5. `ImageProcessor.write_image(img, path, quality)` 保存
6. `model.mark_saved()`
7. 状态栏提示"已保存"

**同步更新 main.py**：在创建 `MainWindow` 后，创建 `AppController(window)`。

**验证**：
- 打开一张图片后画布显示该图片，状态栏显示正确尺寸
- 导出后用系统图片查看器打开，质量无明显损失
- 打开 PNG 后导出为 PNG，文件大小接近原始大小

---

## Phase 5：旋转功能

### Step 5.1 — 实现旋转操作

**文件**：`controller/app_controller.py`（添加旋转方法）

**实现要求**：

```python
def _apply_transform(self, new_img: np.ndarray):
    """通用：保存历史 → 更新 model → 刷新画布"""
    self.history.push(self.model.image.copy())
    self.model.update_image(new_img)
    self.window.canvas.refresh(new_img)
    # 更新状态栏尺寸

def do_rotate_cw(self):
    if self.model.image is None: return
    self._apply_transform(ImageProcessor.rotate_90cw(self.model.image))

def do_rotate_ccw(self):
    if self.model.image is None: return
    self._apply_transform(ImageProcessor.rotate_90ccw(self.model.image))
```

同时在 `__init__` 中连接信号：
```python
window.toolbar.rotate_cw_clicked.connect(self.do_rotate_cw)
window.toolbar.rotate_ccw_clicked.connect(self.do_rotate_ccw)
```

**验证**：
- 打开一张非正方形图片，点击旋转按钮，宽高互换
- 连续旋转 4 次，图像还原为初始状态
- 旋转后画布显示适应新尺寸

---

## Phase 6：区域选择与裁剪

### Step 6.1 — 实现 Canvas 选区交互

**文件**：`ui/canvas.py`（追加鼠标事件逻辑）

**实现要求**：

新增枚举（在文件顶部）：
```python
from enum import Enum
class CanvasTool(Enum):
    NONE    = 0
    SELECT  = 1
    CROP    = 2
    GRABCUT = 3
```

鼠标事件：
- `mousePressEvent`：记录起点 `drag_start`（画布坐标）
- `mouseMoveEvent`：更新 `drag_end`，调用 `update()` 重绘
- `mouseReleaseEvent`：确定选区，转换为图像坐标，发出 `selection_changed` 信号
- 按 `Esc` 键清除选区，发出 `selection_cleared`

`paintEvent` 追加选区绘制：
- 半透明蒙层（选区外）：`QColor(0, 0, 0, 80)`
- 虚线边框：`QPen(Qt.white, 1, Qt.DashLine)`
- 内部显示选区尺寸文字（如 `320 × 240`）

坐标转换辅助方法：
```python
def canvas_to_image(self, cx, cy) -> tuple[int, int]:
    # 考虑 zoom_factor 和 pan_offset
    ix = int((cx - self.pan_offset.x()) / self.zoom_factor)
    iy = int((cy - self.pan_offset.y()) / self.zoom_factor)
    return (
        max(0, min(ix, self.image_width - 1)),
        max(0, min(iy, self.image_height - 1))
    )
```

**验证**：
- 在画布上拖拽出现选框，显示尺寸数字
- 选区外有半透明蒙层
- Esc 键取消选区

---

### Step 6.2 — 实现裁剪

**文件**：`controller/app_controller.py`

**实现要求**：

```python
def do_crop(self):
    sel = self.model.selection
    if sel is None:
        QMessageBox.information(self.window, "提示", "请先框选裁剪区域")
        return
    x1, y1, x2, y2 = sel
    new_img = ImageProcessor.crop(self.model.image, x1, y1, x2, y2)
    self.model.clear_selection()
    self.window.canvas.selection = None
    self._apply_transform(new_img)
    self.window.canvas.zoom_fit()
```

在 `__init__` 中连接：`window.toolbar.crop_clicked.connect(self.do_crop)`

在 Canvas 中连接：`canvas.selection_changed.connect(model.set_selection)`

**验证**：
- 框选后点击裁剪，画布显示裁剪后的图片
- 裁剪后画布适应新尺寸
- 撤销后恢复原图

---

## Phase 7：删除选区内容

### Step 7.1 — 实现删除选区

**文件**：`controller/app_controller.py`

**实现要求**：

```python
def do_delete_selection(self):
    sel = self.model.selection
    if sel is None:
        QMessageBox.information(self.window, "提示", "请先框选要删除的区域")
        return
    x1, y1, x2, y2 = sel
    new_img = ImageProcessor.delete_selection(self.model.image, x1, y1, x2, y2)
    self._apply_transform(new_img)
    # 保留选区（用户可能继续操作）
```

**同时**在 `Canvas.keyPressEvent` 中添加：
- `Delete` / `Backspace` 键触发 `delete_key_pressed = Signal()` 信号
- 在 Controller 中连接 `canvas.delete_key_pressed` → `do_delete_selection`

**验证**：
- PNG 图片：框选区域后按 Delete，该区域变为棋盘格（透明）
- JPG 图片：删除后导出为 PNG 仍为透明；导出为 JPG 该区域为白色
- 撤销后区域恢复

---

## Phase 8：GrabCut 抠图

### Step 8.1 — 实现 GrabCutProcessor

**文件**：`core/grabcut.py`

**实现要求**（参考 `docs/MODULE_API.md` 第四节）：

```python
from PyQt6.QtCore import QObject, pyqtSignal as Signal, QThread
import cv2, numpy as np

class GrabCutWorker(QObject):
    finished = Signal(object)   # np.ndarray
    failed   = Signal(str)
    progress = Signal(int)

    def __init__(self, img, rect, iter_count=5):
        super().__init__()
        self.img = img
        self.rect = rect
        self.iter_count = iter_count

    def run(self):
        try:
            self.progress.emit(10)
            bgr = cv2.cvtColor(self.img, cv2.COLOR_BGRA2BGR)
            
            # 大图缩放优化
            h, w = bgr.shape[:2]
            scale = 1.0
            if max(h, w) > 1500:
                scale = 1500 / max(h, w)
                bgr_small = cv2.resize(bgr, None, fx=scale, fy=scale)
                rx, ry, rw, rh = self.rect
                rect_small = (int(rx*scale), int(ry*scale),
                              int(rw*scale), int(rh*scale))
            else:
                bgr_small = bgr
                rect_small = self.rect
            
            self.progress.emit(30)
            mask = np.zeros(bgr_small.shape[:2], np.uint8)
            bgd_model = np.zeros((1, 65), np.float64)
            fgd_model = np.zeros((1, 65), np.float64)
            cv2.grabCut(bgr_small, mask, rect_small, bgd_model, fgd_model,
                        self.iter_count, cv2.GC_INIT_WITH_RECT)
            
            self.progress.emit(80)
            fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
            
            # 放大 mask 回原始尺寸
            if scale != 1.0:
                fg_mask = cv2.resize(fg_mask, (w, h), interpolation=cv2.INTER_NEAREST)
            
            result = self.img.copy()
            result[:, :, 3] = fg_mask
            
            self.progress.emit(100)
            self.finished.emit(result)
        except Exception as e:
            self.failed.emit(str(e))
```

**验证**（单元测试）：
```python
# 创建简单测试图（中心圆形前景）
import numpy as np, cv2
from core.grabcut import GrabCutWorker

img = np.zeros((200, 200, 4), dtype=np.uint8)
img[:, :] = [200, 200, 200, 255]  # 灰色背景
cv2.circle(img, (100, 100), 50, (0, 0, 255, 255), -1)  # 红色圆形前景

results = []
worker = GrabCutWorker(img, (50, 50, 100, 100))
worker.finished.connect(lambda r: results.append(r))
worker.run()  # 直接调用（非线程模式验证）

assert len(results) == 1
result = results[0]
assert result.shape[2] == 4, "结果必须是 BGRA"
print("GrabCutWorker: OK")
```

---

### Step 8.2 — 在 Controller 中集成 GrabCut

**文件**：`controller/app_controller.py`

**实现要求**：

```python
def do_grabcut(self):
    sel = self.model.selection
    if sel is None:
        QMessageBox.information(self.window, "提示", "请先用框选工具圈出要保留的主体区域")
        return
    
    x1, y1, x2, y2 = sel
    rect = (x1, y1, x2 - x1, y2 - y1)
    
    # 显示进度对话框
    self._progress_dialog = QProgressDialog("正在抠图...", None, 0, 100, self.window)
    self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
    self._progress_dialog.show()
    
    # 启动子线程
    self._grabcut_thread = QThread()
    self._grabcut_worker = GrabCutWorker(self.model.image.copy(), rect)
    self._grabcut_worker.moveToThread(self._grabcut_thread)
    
    self._grabcut_worker.progress.connect(self._progress_dialog.setValue)
    self._grabcut_worker.finished.connect(self._on_grabcut_done)
    self._grabcut_worker.failed.connect(self._on_grabcut_failed)
    self._grabcut_thread.started.connect(self._grabcut_worker.run)
    self._grabcut_thread.start()

def _on_grabcut_done(self, result: np.ndarray):
    self._grabcut_thread.quit()
    self._progress_dialog.close()
    self.model.clear_selection()
    self._apply_transform(result)

def _on_grabcut_failed(self, err: str):
    self._grabcut_thread.quit()
    self._progress_dialog.close()
    QMessageBox.critical(self.window, "抠图失败", f"抠图过程出错：{err}\n请重新框选尝试")
```

**验证**：
- 打开一张有明显主体的图片（如人物/物品在纯色背景）
- 框选主体区域，点击「抠图」按钮
- 出现进度条，完成后背景变透明（棋盘格显示）
- 导出为 PNG，背景为透明

---

## Phase 9：撤销/重做

### Step 9.1 — 实现撤销/重做逻辑

**文件**：`controller/app_controller.py`

**实现要求**：

```python
def undo(self):
    prev = self.history.undo()
    if prev is None:
        return
    self.model.update_image(prev)
    self.window.canvas.refresh(prev)
    self._update_undo_redo_state()

def redo(self):
    nxt = self.history.redo()
    if nxt is None:
        return
    self.model.update_image(nxt)
    self.window.canvas.refresh(nxt)
    self._update_undo_redo_state()

def _update_undo_redo_state(self):
    """根据 HistoryManager 状态更新菜单项的 enabled 状态"""
    self.window.undo_action.setEnabled(self.history.can_undo)
    self.window.redo_action.setEnabled(self.history.can_redo)
```

在 `__init__` 中连接：
```python
window.undo_triggered.connect(self.undo)
window.redo_triggered.connect(self.redo)
```

**验证**：
- 打开图片 → 旋转 → Ctrl+Z → 图片还原
- 旋转 → 裁剪 → Ctrl+Z（还原裁剪）→ Ctrl+Z（还原旋转）→ 还原到原始
- 撤销到底后菜单项变灰（disabled）

---

## Phase 10：体验打磨

### Step 10.1 — 完善状态栏动态更新

**文件**：`ui/main_window.py` + `controller/app_controller.py`

状态栏应实时显示：
- 图片尺寸：`W × H px`（无图时显示"未打开图片"）
- 当前缩放：`75%`
- 当前工具：`选框` / `裁剪` / `抠图` / `-`

**实现**：在每次图像变化、工具切换、缩放变化后更新状态栏文本。

---

### Step 10.2 — 关闭时的保存确认

**文件**：`ui/main_window.py`

**实现 `closeEvent`**：
```python
def closeEvent(self, event):
    if self.controller and self.controller.model.is_dirty:
        reply = QMessageBox.question(
            self, "未保存的修改",
            "图片有未保存的修改，是否在退出前保存？",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )
        if reply == QMessageBox.StandardButton.Save:
            self.controller.export_image()
            event.accept()
        elif reply == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()
    else:
        event.accept()
```

---

### Step 10.3 — 画布透明背景（棋盘格）

**文件**：`ui/canvas.py`

**实现要求**：
- 在 `paintEvent` 中，绘制图片前先绘制棋盘格背景（灰白交替 10px 格子）
- 使图片透明区域清晰可辨

```python
def _draw_checkerboard(self, painter: QPainter, rect: QRect):
    size = 10
    for row in range(rect.height() // size + 1):
        for col in range(rect.width() // size + 1):
            color = QColor(200, 200, 200) if (row + col) % 2 == 0 else QColor(255, 255, 255)
            painter.fillRect(
                rect.x() + col * size, rect.y() + row * size,
                size, size, color
            )
```

**验证**：
- 打开 PNG 图片后删除选区，透明区域显示棋盘格
- GrabCut 抠图后背景区域显示棋盘格

---

### Step 10.4 — 拖拽打开图片

**文件**：`ui/canvas.py`

**实现要求**：
- 重写 `dragEnterEvent`：检查 MIME 数据是否含文件 URL，接受拖拽
- 重写 `dropEvent`：获取文件路径，发出 `file_dropped = Signal(str)` 信号
- 在 Controller 中连接 `canvas.file_dropped` → `open_image_from_path(path)`

---

## 附录：完整功能检查清单

完成所有 Phase 后，按以下清单逐项验证：

| # | 功能              | 验证步骤                                   | 预期结果                     |
|---|-----------------|------------------------------------------|-----------------------------|
| 1 | 导入图片          | Ctrl+O 选择 PNG/JPG/BMP                  | 图片显示在画布，尺寸正确      |
| 2 | 拖拽打开          | 拖拽图片文件到窗口                         | 同上                        |
| 3 | 导出 PNG（无损）  | 导入图片 → 不做修改 → 导出 PNG            | 文件大小与原图接近，无质量损失 |
| 4 | 导出 JPG         | 导入图片 → 导出 JPG，quality=95           | 文件合理，画质良好            |
| 5 | 裁剪             | 框选区域 → 裁剪                           | 画布变小为选区大小            |
| 6 | 旋转 CW          | 点击顺时针旋转                             | 图片顺时针旋转 90°            |
| 7 | 旋转 CCW         | 点击逆时针旋转                             | 图片逆时针旋转 90°            |
| 8 | 旋转4次还原       | 旋转4次后与原图对比                        | 完全相同                     |
| 9 | 删除选区          | 框选 → Delete 键                          | 选区变透明（棋盘格）           |
| 10| 抠图             | 框选主体 → 点击抠图                        | 背景变透明，保留主体           |
| 11| 撤销             | 操作后 Ctrl+Z                             | 回到上一步                   |
| 12| 重做             | 撤销后 Ctrl+Shift+Z                       | 恢复操作                     |
| 13| 关闭保存确认      | 编辑后直接关闭窗口                         | 弹出保存确认对话框             |
| 14| 中文路径          | 图片放在含中文的路径下打开/保存             | 正常读写，无乱码               |
