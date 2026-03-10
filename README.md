# EasyPicture

轻量级本地桌面图片编辑工具，全程本地处理，图片质量完整保留，无需联网。

## 功能特性

| 功能 | 说明 |
|------|------|
| **导入 / 导出** | 支持 PNG、JPG、BMP、TIFF、WEBP；PNG 无损，JPG 可调质量 |
| **裁剪** | 鼠标拖拽框选，支持数值精确输入，可导出局部区域 |
| **区域选择 & 删除** | 框选后一键删除，PNG 填充透明，JPG 填充白色 |
| **抠图（背景去除）** | 基于 OpenCV GrabCut + 后处理（形态学 + 连通域 + 边缘羽化），生成透明背景图 |
| **旋转** | 90° / 180° / 270° 无损旋转；任意角度旋转（LANCZOS4 插值） |
| **符合画布** | 一键裁去四周透明像素，保留主体内容最小边界框（抠图后常用） |
| **缩放到指定尺寸** | 自定义宽高，可锁定宽高比，高质量 LANCZOS4 插值 |
| **AI 变清晰** | 使用 Real-ESRGAN 神经网络增强细节纹理，消除模糊、恢复锐度，不改变图片尺寸；模型文件随项目提供，无需联网 |
| **撤销 / 重做** | 多步 Ctrl+Z / Ctrl+Shift+Z |

## 环境要求

- Python **3.11+**
- [uv](https://github.com/astral-sh/uv) 包管理器

## 快速开始

```bash
# 克隆项目
git clone https://github.com/yourname/easyPicture.git
cd easyPicture

# 安装依赖（需要 Python 3.11，uv 会自动创建虚拟环境）
uv sync

# 启动应用
uv run python main.py
```

> **注意**：项目需要 Python 3.11（opencv 的原生扩展暂不支持 3.13）。若系统默认为 3.13，使用：
> ```bash
> uv run --python 3.11 python main.py
> ```

> **AI 变清晰模型**：首次使用前需将 `realesrgan.onnx` 放入项目根目录的 `models/` 文件夹。  
> 可从 [HuggingFace](https://huggingface.co/) 搜索 `realesr-general-x4v3 onnx` 获取，或联系项目维护者。

## 使用说明

### 打开图片

- 菜单栏 **文件 → 打开**，或快捷键 `Ctrl+O`
- 直接将图片文件**拖拽**到窗口

### 裁剪

1. 点击左侧工具栏「✂ 裁剪」按钮
2. 在画布上拖拽框选区域（或在底部面板输入精确数值）
3. 点击「确认裁剪」或「导出裁剪」（导出不修改原图）

### 抠图（去除背景）

1. 点击工具栏「✦ 抠图」按钮（第①步：激活框选模式）
2. 在图片上拖拽框选**主体**区域
3. 点击工具栏「▶ 执行」按钮（第②步：开始计算）
4. 等待进度条完成，背景变为透明
5. 可继续执行「图像 → 符合画布」去除边缘空白

### 缩放图片

- 菜单栏 **图像 → 缩放图片...**，输入目标宽高，勾选「锁定宽高比」保持比例

### 符合画布

- 菜单栏 **图像 → 符合画布**，自动裁去四周透明像素

### 导出图片

- 菜单栏 **文件 → 导出**，或快捷键 `Ctrl+S`
- 含透明区域的图片建议导出为 **PNG**

### 常用快捷键

| 操作 | macOS | Windows / Linux |
|------|-------|-----------------|
| 打开 | `Cmd+O` | `Ctrl+O` |
| 导出 | `Cmd+S` | `Ctrl+S` |
| 撤销 | `Cmd+Z` | `Ctrl+Z` |
| 重做 | `Cmd+Shift+Z` | `Ctrl+Shift+Z` |
| 取消选区 | `Esc` | `Esc` |

## 项目结构

```
easyPicture/
├── main.py                  # 入口
├── pyproject.toml           # 项目依赖（uv 管理）
├── models/                  # AI 模型文件（不提交 git）
│   └── realesrgan.onnx      # Real-ESRGAN ONNX 模型（需手动放入）
├── core/
│   ├── image_model.py       # 图像数据模型
│   ├── image_processor.py   # 纯函数图像处理（裁剪、旋转、缩放…）
│   ├── grabcut.py           # GrabCut 抠图（QThread 异步）
│   ├── realesrgan.py        # Real-ESRGAN 推理（分块 + QThread 异步）
│   └── history.py           # 撤销 / 重做历史栈
├── ui/
│   ├── main_window.py       # 主窗口布局
│   ├── canvas.py            # 画布（显示、缩放、选区交互）
│   ├── toolbar.py           # 左侧工具栏
│   ├── crop_panel.py        # 裁剪面板（数值输入）
│   └── dialogs.py           # 对话框（JPEG 质量、缩放等）
├── controller/
│   └── app_controller.py    # 信号 / 槽中枢，连接 UI 与 Core
├── resources/               # 图标等静态资源
└── docs/                    # 设计文档
    ├── PRD.md
    ├── TECH_DESIGN.md
    ├── MODULE_API.md
    └── AI_IMPL_GUIDE.md
```

## 技术栈

| 组件 | 版本 |
|------|------|
| Python | ≥ 3.11 |
| PyQt6 | ≥ 6.5 |
| OpenCV | ≥ 4.8（opencv-contrib） |
| NumPy | ≥ 1.24 |
| Pillow | ≥ 10.0 |
| onnxruntime | ≥ 1.17（AI 推理，无需 PyTorch） |
| 包管理 | uv |

## 开发

```bash
# 安装依赖
uv sync

# 运行
uv run python main.py

# 添加新依赖示例
uv add <package>
```

## 注意事项

- 抠图结果质量受主体与背景对比度影响，建议在对比度高的图片上使用
- 导出 JPG 时透明区域自动合并到白色背景
- 图片全程以原始分辨率 BGRA 数组存储，导出不经过额外压缩

## License

MIT
