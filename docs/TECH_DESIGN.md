# EasyPicture 技术设计文档

**版本**：v1.0  
**日期**：2026-03-09  
**技术栈**：Python 3.11+ / OpenCV 4.x / PyQt6 / NumPy  
**包管理**：uv（替代 pip + venv）

---

## 一、整体架构

### 1.1 分层架构

```
┌──────────────────────────────────────────────────────┐
│                   UI 层（PyQt6）                       │
│  MainWindow / Canvas / ToolBar / StatusBar / Dialogs  │
├──────────────────────────────────────────────────────┤
│               控制层（Controller）                     │
│       AppController — 协调 UI 事件与核心处理           │
├──────────────────────────────────────────────────────┤
│               核心处理层（Core）                       │
│  ImageProcessor / GrabCutProcessor / HistoryManager   │
├──────────────────────────────────────────────────────┤
│               数据模型层（Model）                      │
│          ImageModel — 持有图像 numpy 数组             │
└──────────────────────────────────────────────────────┘
```

### 1.2 数据流

```
用户操作（鼠标/键盘）
      ↓
  UI 事件（PyQt6 Signal）
      ↓
  AppController（信号路由）
      ↓
  Core 处理（OpenCV 计算）
      ↓
  ImageModel 更新（numpy array 替换）
      ↓
  Canvas 刷新（QPixmap 重绘）
      ↓
  用户看到结果
```

### 1.3 图像数据规范

- **内存格式**：`numpy.ndarray`，dtype `uint8`
  - 彩色图：shape `(H, W, 3)`，通道顺序 **BGR**（OpenCV 默认）
  - 含透明：shape `(H, W, 4)`，通道顺序 **BGRA**
- **显示转换**：BGR → RGB，再转 `QImage` → `QPixmap`
- **原则**：原始数组始终保持原始分辨率；视图缩放仅在 `Canvas` 显示时缩放 `QPixmap`

---

## 二、项目结构

```
easyPicture/
├── main.py                     # 应用入口，创建 QApplication 和 MainWindow
├── requirements.txt            # 依赖列表
├── resources/
│   └── icons/                  # 工具栏图标（SVG/PNG）
├── ui/
│   ├── __init__.py
│   ├── main_window.py          # MainWindow：窗口框架、菜单栏、状态栏
│   ├── canvas.py               # Canvas：图片显示、鼠标事件、选区绘制
│   ├── toolbar.py              # ToolBar：左侧工具面板，工具切换
│   └── dialogs.py              # 导出对话框、GrabCut 确认对话框
├── core/
│   ├── __init__.py
│   ├── image_model.py          # ImageModel：持有当前图像状态
│   ├── image_processor.py      # 裁剪、旋转、删除选区等基础操作
│   ├── grabcut.py              # GrabCut 抠图处理
│   └── history.py              # 撤销/重做历史栈
├── controller/
│   ├── __init__.py
│   └── app_controller.py       # 信号连接与业务逻辑调度
└── docs/                       # 文档目录
```

---

## 三、核心模块设计

### 3.1 ImageModel（数据模型）

负责持有当前编辑图像的所有状态。

```python
class ImageModel:
    original_path: str           # 原始文件路径
    current_image: np.ndarray    # 当前工作图像（BGRA）
    selection: QRect | None      # 当前矩形选区（画布坐标）
    is_dirty: bool               # 是否有未保存修改
```

**关键设计**：
- `current_image` 始终是 BGRA 四通道（导入时如无透明通道自动添加 alpha=255）
- 导出时根据格式决定是否保留 alpha 通道

### 3.2 ImageProcessor（图像处理）

所有基础图像操作，均为纯函数，输入输出均为 `np.ndarray`。

| 方法                                 | 说明                                        |
|------------------------------------|---------------------------------------------|
| `crop(img, x1, y1, x2, y2)`        | 裁剪指定矩形区域，返回新数组                  |
| `rotate_90cw(img)`                 | 顺时针旋转 90°                              |
| `rotate_90ccw(img)`                | 逆时针旋转 90°                              |
| `rotate_180(img)`                  | 旋转 180°                                   |
| `rotate_arbitrary(img, angle)`     | 任意角度旋转（带画布扩展，保留完整内容）       |
| `delete_selection(img, mask)`      | 将 mask 区域 alpha 设为 0（透明删除）         |
| `read_image(path)`                 | 读取图片，返回 BGRA ndarray，保持原始尺寸     |
| `write_image(img, path, quality)`  | 写入图片，PNG 无损，JPG 按 quality 参数      |

**旋转无损实现**：
- 90°/180°/270° 旋转使用 `cv2.rotate()`，无插值，像素1:1对应，完全无损
- 任意角度旋转使用 `cv2.warpAffine()`，`flags=cv2.INTER_LANCZOS4`（高质量插值）

### 3.3 GrabCutProcessor（抠图）

```python
class GrabCutProcessor:
    def run(self, img: np.ndarray, rect: tuple) -> np.ndarray:
        """
        输入：原始 BGR 图像 + 用户框选的矩形 (x, y, w, h)
        输出：BGRA 图像，背景区域 alpha=0（透明）
        """
```

**GrabCut 执行流程**：

```
1. 将输入图转为 BGR（去掉 alpha）
2. 初始化 mask = np.zeros，bgdModel, fgdModel
3. cv2.grabCut(img, mask, rect, bgdModel, fgdModel, iterCount=5, mode=cv2.GC_INIT_WITH_RECT)
4. 生成二值前景 mask：(mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)
5. 在原图上添加 alpha 通道，mask=0 的区域设 alpha=0
6. 返回 BGRA 图像
```

**性能优化**：
- 大图（> 2000px）先缩放到 1500px 执行 GrabCut，结果 mask 再放大回原始尺寸
- 在子线程（`QThread`）中执行，避免 UI 卡顿
- 执行期间显示进度对话框

### 3.4 HistoryManager（撤销/重做）

```python
class HistoryManager:
    _stack: list[np.ndarray]   # 历史快照栈
    _cursor: int               # 当前位置指针
    MAX_STEPS = 20             # 最大撤销步数
    
    def push(self, img: np.ndarray)   # 保存快照（深拷贝）
    def undo(self) -> np.ndarray      # 返回上一步图像
    def redo(self) -> np.ndarray      # 返回下一步图像
    def can_undo(self) -> bool
    def can_redo(self) -> bool
```

**内存控制**：
- 每个历史快照是图像的深拷贝
- 超过 MAX_STEPS 时，弹出最旧的快照
- 对于大图（> 10MB），可考虑只保存 10 步

### 3.5 Canvas（画布组件）

继承 `QWidget`，是用户交互的核心组件。

**视图缩放**：
- 维护 `zoom_factor: float`（默认 1.0）
- 鼠标事件坐标通过 `canvas_to_image(x, y)` 转换为图像真实坐标
- `QPixmap` 按 `zoom_factor` 缩放后绘制，原始数据不变

**鼠标事件状态机**：

```
IDLE ──(工具选择)──► SELECT_MODE
                         │
                    mousePressEvent
                         │
                    DRAWING_SELECTION ──(拖拽)──► 实时绘制选框
                         │
                    mouseReleaseEvent
                         │
                    SELECTION_READY ──(Delete)──► 执行删除
                                    ──(裁剪按钮)──► 执行裁剪
                                    ──(抠图按钮)──► 执行 GrabCut
```

**选区绘制**：
- 使用 `QPainter` 在 `paintEvent` 中绘制虚线矩形（`Qt.PenStyle.DashLine`）
- 选区外区域叠加半透明蒙层（`QColor(0, 0, 0, 80)`）

---

## 四、关键技术细节

### 4.1 图片读取（保持原始质量）

```python
def read_image(path: str) -> np.ndarray:
    # 使用 np.fromfile 处理中文路径问题（Windows）
    buf = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)  # 保留 alpha 通道
    
    if img is None:
        raise ValueError(f"无法读取图片: {path}")
    
    # 统一转为 BGRA 4 通道
    if img.ndim == 2:  # 灰度图
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:  # BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        img[:, :, 3] = 255  # alpha 全不透明
    # BGRA：直接使用
    return img
```

### 4.2 图片写入（无损导出）

```python
def write_image(img: np.ndarray, path: str, quality: int = 95):
    ext = Path(path).suffix.lower()
    
    if ext == '.png':
        # PNG 无损，保留 alpha
        params = [cv2.IMWRITE_PNG_COMPRESSION, 1]  # 压缩级别 1（最快，体积略大）
        cv2.imencode('.png', img, params)[1].tofile(path)
    
    elif ext in ('.jpg', '.jpeg'):
        # JPG 不支持透明，先合并 alpha（白底）
        bgr = alpha_composite_white(img)
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        cv2.imencode('.jpg', bgr, params)[1].tofile(path)
    
    elif ext == '.tiff':
        # TIFF 无损
        cv2.imencode('.tiff', img)[1].tofile(path)
```

### 4.3 BGR↔QImage 转换

```python
def ndarray_to_qimage(img: np.ndarray) -> QImage:
    h, w = img.shape[:2]
    if img.shape[2] == 4:  # BGRA
        rgb = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        return QImage(rgb.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
    else:  # BGR
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
```

> 注意：`img.data` 是内存视图，`QImage` 不拷贝数据。需调用 `.copy()` 确保数据不被 GC。

### 4.4 坐标转换（Canvas 坐标 ↔ 图像坐标）

```python
def canvas_to_image(self, cx: int, cy: int) -> tuple[int, int]:
    """将画布像素坐标转换为图像真实坐标"""
    ix = int(cx / self.zoom_factor)
    iy = int(cy / self.zoom_factor)
    # 限制在图像边界内
    ix = max(0, min(ix, self.image_width - 1))
    iy = max(0, min(iy, self.image_height - 1))
    return ix, iy
```

---

## 五、依赖与环境

### 5.1 包管理工具

项目使用 [uv](https://docs.astral.sh/uv/) 作为包管理器（替代 pip + venv）。  
uv 速度比 pip 快 10-100 倍，自动管理虚拟环境，无需手动 activate。

项目依赖声明在 `pyproject.toml`：

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
```

精确的锁定版本记录在 `uv.lock`（自动生成，提交到版本控制）。

### 5.2 开发环境搭建

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 进入项目目录，一条命令完成安装
cd easyPicture
uv sync          # 自动创建 .venv 并安装所有依赖

# 运行应用
uv run python main.py

# 或激活虚拟环境后直接运行
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows
python main.py
```

### 5.3 添加/更新依赖

```bash
uv add opencv-python          # 添加新依赖（自动更新 pyproject.toml 和 uv.lock）
uv add --dev pyinstaller      # 添加开发依赖
uv remove Pillow              # 移除依赖
uv sync                       # 同步环境与 uv.lock 保持一致
```

### 5.4 打包为 macOS .app（PyInstaller）

```bash
uv add --dev pyinstaller

uv run pyinstaller --onefile --windowed \
    --name "EasyPicture" \
    --icon resources/icons/app.icns \
    --add-data "resources:resources" \
    main.py
```

输出：`dist/EasyPicture.app`，预计体积约 70-90MB。

---

## 六、错误处理策略

| 场景                       | 处理方式                                       |
|--------------------------|----------------------------------------------|
| 打开不支持的文件格式         | 弹出提示对话框，列出支持的格式                  |
| 图片读取失败（文件损坏）     | 弹出错误对话框，不改变当前状态                  |
| GrabCut 抠图失败           | 提示用户重新框选，回滚到框选前状态              |
| 导出路径无写权限             | 提示选择其他路径                              |
| 内存不足（超大图）           | 提示图片过大，建议先缩小后编辑                  |

---

## 七、测试要点

| 测试项                     | 验证方法                                     |
|--------------------------|---------------------------------------------|
| PNG 无损导入/导出           | md5 对比原始文件与导出文件，应一致（未编辑时）  |
| 90° 旋转无损               | 旋转 4 次后与原图 md5 对比                   |
| 裁剪坐标精确               | 验证裁剪后图片尺寸等于选区大小                 |
| GrabCut 输出透明背景        | 检查背景区域 alpha=0，前景区域 alpha=255      |
| 撤销/重做完整性             | 连续操作后撤销到初始状态，与原图对比           |
| 中文路径读写               | 路径含中文时文件正常读写                      |
