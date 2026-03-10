# -*- mode: python ; coding: utf-8 -*-
#
# EasyPicture macOS 打包配置
# 生成：EasyPicture.app（macOS .app 双击可运行）
#
# 用法：
#   uv run pyinstaller easypicture.spec
#
# 输出：dist/EasyPicture.app

from pathlib import Path

ROOT = Path(SPECPATH)

# ─── 打包进 app 的数据文件 ────────────────────────────────────────────────────

datas = []

# 将 models/ 目录下所有 .onnx 文件打包进去（如有）
for onnx in (ROOT / "models").glob("*.onnx"):
    datas.append((str(onnx), "models"))

# ─── 分析 ─────────────────────────────────────────────────────────────────────

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # onnxruntime 动态扩展
        "onnxruntime",
        "onnxruntime.capi",
        "onnxruntime.capi._pybind_state",
        # opencv
        "cv2",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除不需要的大型库（torch 仅用于 .pth→.onnx 转换，运行时不需要）
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
    upx=False,           # macOS 上 UPX 可能导致签名问题，保持关闭
    console=False,       # 不显示终端窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,    # None = 当前架构（arm64 或 x86_64）
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EasyPicture",
)

# macOS .app 包（双击运行）
app = BUNDLE(
    coll,
    name="EasyPicture.app",
    icon=None,            # 可替换为 resources/icons/app.icns
    bundle_identifier="com.easypicture.app",
    version="0.1.0",
    info_plist={
        "CFBundleDisplayName": "EasyPicture",
        "CFBundleName": "EasyPicture",
        "CFBundleExecutable": "EasyPicture",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        "LSApplicationCategoryType": "public.app-category.graphics-design",
        "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": True,
        "NSAppleScriptEnabled": False,
        # 允许拖入图片文件
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Image File",
                "CFBundleTypeRole": "Editor",
                "LSItemContentTypes": [
                    "public.png", "public.jpeg", "public.bmp",
                    "public.tiff", "org.webmproject.webp",
                ],
            }
        ],
    },
)
