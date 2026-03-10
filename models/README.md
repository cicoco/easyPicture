# AI 模型文件说明

此目录用于存放「AI 变清晰」功能所需的模型文件。

## 当前默认模型

**`RealESRGAN_x4plus_anime_6B`**（动漫/插画风格，适用广泛）

## 支持的模型

| 模型文件名 | 架构 | 参数量 | 适用场景 |
|---|---|---|---|
| `RealESRGAN_x4plus_anime_6B.pth` | RRDBNet (6 blocks) | 4.5M | 动漫、插画、通用 ✅ 默认 |
| `realesr-general-x4v3.pth` | SRVGGNetCompact | 1.2M | 通用真实照片（体积小） |

## 操作步骤

### 步骤 1：下载 .pth 模型

从 Real-ESRGAN 官方 GitHub Releases 下载：

```
https://github.com/xinntao/Real-ESRGAN/releases
```

或从 HuggingFace 下载：

```
https://huggingface.co/gemasai/RealESRGAN_x4plus_anime_6B/tree/main
```

下载后放入 `models/` 目录。

### 步骤 2：转换为 ONNX 格式

EasyPicture 使用 `onnxruntime` 进行推理，需先将 `.pth` 转换为 `.onnx`。
转换脚本会**自动检测模型架构**，无需手动指定：

```bash
# 转换默认模型（anime 6B）
uv run --with torch --with onnx python tools/convert_to_onnx.py RealESRGAN_x4plus_anime_6B.pth

# 或转换通用模型
uv run --with torch --with onnx python tools/convert_to_onnx.py realesr-general-x4v3.pth
```

转换成功后会生成对应的 `.onnx` 文件，即可在 EasyPicture 中使用。

### 步骤 3：启动应用

```bash
uv run python main.py
```

点击工具栏「✨ AI变清晰」，选择放大倍率和去噪强度，开始处理。

## 模型说明

### RealESRGAN_x4plus_anime_6B（默认）
- **架构**：RRDBNet（6 个 RRDB 块）
- **原生放大倍率**：4x
- **适用场景**：动漫、插画、CG 图像，通用场景也效果良好

### realesr-general-x4v3
- **架构**：SRVGGNetCompact（紧凑版，参数量更少）
- **原生放大倍率**：4x
- **适用场景**：真实照片，速度更快

## 切换模型

两种方式切换：

1. 在代码中动态切换（需要重启应用）：
   ```python
   from core.realesrgan import set_model
   set_model("realesr-general-x4v3")   # 不含 .onnx 扩展名
   ```

2. 修改 `core/realesrgan.py` 中的 `_DEFAULT_MODEL_STEM` 常量。

## 注意事项

- `.pth` 和 `.onnx` 文件已加入 `.gitignore`，不会提交到 Git 仓库
- 首次使用时 ONNX 会话加载需要数秒，之后缓存在内存中
- CPU 推理速度：小图（512×512）约 10-60 秒，大图按分块数量线性增加
