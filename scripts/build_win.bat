@echo off
REM =============================================================================
REM EasyPicture Windows 打包脚本
REM 生成 dist\EasyPicture\EasyPicture.exe
REM
REM 用法：在项目根目录双击运行，或：
REM   cd /d C:\path\to\easyPicture
REM   scripts\build_win.bat
REM
REM 前置条件：
REM   1. 已安装 Python 3.11+（建议 3.12）
REM   2. 已安装 uv：pip install uv  （或 winget install astral-sh.uv）
REM   3. 已运行 uv sync 安装项目依赖
REM   4. models\ 目录下有 RealESRGAN_x4plus_anime_6B.onnx
REM      若没有，先在 Python 环境下运行：
REM      uv run --with torch --with onnx python tools\convert_to_onnx.py RealESRGAN_x4plus_anime_6B.pth
REM =============================================================================

setlocal enabledelayedexpansion

cd /d "%~dp0.."
echo ========================================
echo   EasyPicture Windows 打包
echo ========================================

REM ── 检查 ONNX 模型 ──────────────────────────────────────────────────────────
if not exist "models\RealESRGAN_x4plus_anime_6B.onnx" (
    echo.
    echo [警告] 未找到 ONNX 模型文件：models\RealESRGAN_x4plus_anime_6B.onnx
    echo        打包将继续，但打包后的应用无法使用 AI 变清晰功能。
    echo        要包含模型，请先运行转换脚本。
    echo.
)

REM ── 安装 / 检查 pyinstaller ──────────────────────────────────────────────────
echo [1/4] 检查 PyInstaller...
uv run python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo       安装 PyInstaller...
    uv add --dev "pyinstaller>=6.0"
)
echo       OK

REM ── 清理旧构建产物 ────────────────────────────────────────────────────────────
echo [2/4] 清理旧构建产物...
if exist "dist\EasyPicture" rmdir /s /q "dist\EasyPicture"
if exist "build\easypicture" rmdir /s /q "build\easypicture"
echo       OK

REM ── 执行打包 ──────────────────────────────────────────────────────────────────
echo [3/4] 执行 PyInstaller 打包（可能需要几分钟）...
uv run pyinstaller easypicture_win.spec --noconfirm
if errorlevel 1 (
    echo [错误] PyInstaller 打包失败！
    pause
    exit /b 1
)
echo       OK

REM ── 检查结果 ──────────────────────────────────────────────────────────────────
echo [4/4] 检查打包结果...
if exist "dist\EasyPicture\EasyPicture.exe" (
    echo.
    echo ========================================
    echo   打包成功！
    echo.
    echo   输出目录：%CD%\dist\EasyPicture\
    echo   可执行文件：dist\EasyPicture\EasyPicture.exe
    echo.
    echo   发布时将整个 dist\EasyPicture\ 文件夹打包为 zip 即可。
    echo ========================================
) else (
    echo [错误] 未找到 dist\EasyPicture\EasyPicture.exe，打包可能失败。
    pause
    exit /b 1
)

pause
