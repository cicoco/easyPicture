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

ROOT = Path(SPECPATH)

# ─── 打包进 exe 的数据文件 ─────────────────────────────────────────────────────

datas = []

for onnx in (ROOT / "models").glob("*.onnx"):
    datas.append((str(onnx), "models"))

# ─── 分析 ─────────────────────────────────────────────────────────────────────

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
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
