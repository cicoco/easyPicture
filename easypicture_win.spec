# -*- mode: python ; coding: utf-8 -*-
#
# EasyPicture Windows 打包配置
# 生成：dist\EasyPicture\EasyPicture.exe（目录发布）
#
# 用法（在 Windows 机器上执行）：
#   uv sync --extra build
#   uv run pyinstaller easypicture_win.spec
#
# 或直接运行：
#   scripts\build_win.bat

from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

ROOT = Path(SPECPATH)

# ─── 打包进 exe 的数据文件 ─────────────────────────────────────────────────────

datas = []
binaries = []
hiddenimports = []

# onnxruntime：用 collect_all 完整收集包目录、DLL 及子模块
# （仅靠 hiddenimports 无法打包 onnxruntime 的 provider DLL，会导致启动崩溃）
_ort_datas, _ort_bins, _ort_hidden = collect_all("onnxruntime")
datas     += _ort_datas
binaries  += _ort_bins
hiddenimports += _ort_hidden

# 额外收集 onnxruntime 的动态库（onnxruntime.dll / onnxruntime_providers_*.dll）
binaries += collect_dynamic_libs("onnxruntime")

# cv2（opencv）
_cv2_datas, _cv2_bins, _cv2_hidden = collect_all("cv2")
datas     += _cv2_datas
binaries  += _cv2_bins
hiddenimports += _cv2_hidden

# ONNX 模型文件
for onnx in (ROOT / "models").glob("*.onnx"):
    datas.append((str(onnx), "models"))

# ─── 分析 ─────────────────────────────────────────────────────────────────────

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + [
        "onnxruntime",
        "onnxruntime.capi",
        "onnxruntime.capi._pybind_state",
        "cv2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch", "torchvision", "torchaudio",
        "onnxscript",
        "tkinter", "_tkinter",
        "matplotlib", "scipy", "pandas",
        "IPython", "jupyter",
        "test", "unittest",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EasyPicture",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,            # Windows 上 UPX 压缩通常安全
    console=False,       # 不显示黑色命令行窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # 可替换为 resources/icons/app.ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EasyPicture",
)
