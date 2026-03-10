#!/usr/bin/env bash
# =============================================================================
# EasyPicture macOS 打包脚本
# 生成 dist/EasyPicture.app（双击可运行的 .app 包）
#
# 用法：
#   bash scripts/build_mac.sh
#
# 前置条件：
#   1. 已运行 uv sync（安装项目依赖）
#   2. models/ 目录下有 RealESRGAN_x4plus_anime_6B.onnx
#      （若没有，先运行：uv run --with torch --with onnx python tools/convert_to_onnx.py RealESRGAN_x4plus_anime_6B.pth）
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."

cd "$ROOT"

echo "========================================"
echo "  EasyPicture macOS 打包"
echo "========================================"

# ── 检查 ONNX 模型 ──────────────────────────────────────────────────────────
ONNX_FILE="models/RealESRGAN_x4plus_anime_6B.onnx"
if [ ! -f "$ONNX_FILE" ]; then
    echo ""
    echo "[警告] 未找到 ONNX 模型文件：$ONNX_FILE"
    echo "       打包将继续，但打包后的应用无法使用 AI 变清晰功能。"
    echo "       要包含模型，请先运行："
    echo "         uv run --with torch --with onnx python tools/convert_to_onnx.py RealESRGAN_x4plus_anime_6B.pth"
    echo ""
fi

# ── 安装 / 检查 pyinstaller ──────────────────────────────────────────────────
echo "[1/4] 检查 PyInstaller..."
if ! uv run python -c "import PyInstaller" 2>/dev/null; then
    echo "      安装 PyInstaller..."
    uv add --dev "pyinstaller>=6.0"
fi
echo "      OK"

# ── 清理旧构建产物 ────────────────────────────────────────────────────────────
echo "[2/4] 清理旧构建产物..."
rm -rf dist/EasyPicture dist/EasyPicture.app build/EasyPicture
echo "      OK"

# ── 执行打包 ──────────────────────────────────────────────────────────────────
echo "[3/4] 执行 PyInstaller 打包（可能需要几分钟）..."
uv run pyinstaller easypicture.spec --noconfirm
echo "      OK"

# ── 检查结果 ──────────────────────────────────────────────────────────────────
echo "[4/4] 检查打包结果..."
APP_PATH="dist/EasyPicture.app"
if [ -d "$APP_PATH" ]; then
    SIZE=$(du -sh "$APP_PATH" | cut -f1)
    echo ""
    echo "========================================"
    echo "  打包成功！"
    echo ""
    echo "  输出路径：$ROOT/dist/EasyPicture.app"
    echo "  应用大小：$SIZE"
    echo ""
    echo "  双击即可运行，或：open dist/EasyPicture.app"
    echo "========================================"
else
    echo "[错误] 未找到 dist/EasyPicture.app，打包可能失败。"
    exit 1
fi
