"""
Real-ESRGAN 超分辨率放大模块（基于 onnxruntime 推理）。

默认模型：RealESRGAN_x4plus_anime_6B（原生 4x，RRDBNet 架构）
文件：models/RealESRGAN_x4plus_anime_6B.onnx（需从 .pth 转换，见 tools/convert_to_onnx.py）

切换模型：
    from core.realesrgan import set_model
    set_model("realesr-general-x4v3")   # 不含扩展名

使用方式：
    from core.realesrgan import realesrgan_upscale_bgra, RealESRGANWorker, is_model_available
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal as Signal

try:
    import onnxruntime as ort
    _ORT_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - 依赖环境差异导致
    ort = None
    _ORT_IMPORT_ERROR = exc

def _base_dir() -> Path:
    """返回应用根目录，兼容开发环境和 PyInstaller 打包环境。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent

_MODELS_DIR = _base_dir() / "models"
_DEFAULT_MODEL_STEM = "RealESRGAN_x4plus_anime_6B"
_current_model_stem: str = _DEFAULT_MODEL_STEM


def set_model(stem: str) -> None:
    """切换当前使用的模型（传入不含扩展名的文件名）。会重置 ONNX session。"""
    global _current_model_stem, _session
    _current_model_stem = stem
    _session = None


def _model_path() -> Path:
    return _MODELS_DIR / f"{_current_model_stem}.onnx"


def is_model_available() -> bool:
    """检查当前模型的 ONNX 文件是否存在。"""
    return _model_path().exists()

def is_runtime_available() -> bool:
    """检查 onnxruntime 运行时是否可用。"""
    return ort is not None

def runtime_error_message() -> str:
    """返回 onnxruntime 不可用时的错误文本。"""
    return str(_ORT_IMPORT_ERROR) if _ORT_IMPORT_ERROR else ""


# ─── ONNX 会话（懒加载、单例）────────────────────────────────────────────────

_session: ort.InferenceSession | None = None


def _get_session() -> ort.InferenceSession:
    global _session
    if ort is None:
        raise RuntimeError(
            "onnxruntime 运行时不可用。"
            + (f"\n详细错误：{_ORT_IMPORT_ERROR}" if _ORT_IMPORT_ERROR else "")
        )
    if _session is None:
        _session = ort.InferenceSession(
            str(_model_path()),
            providers=["CPUExecutionProvider"],
        )
    return _session


# ─── 单块推理 ─────────────────────────────────────────────────────────────────

def _infer_tile(session: ort.InferenceSession, inp_name: str,
                tile_rgb: np.ndarray) -> np.ndarray:
    """
    对单个 RGB uint8 tile 执行 ONNX 推理。
    输入：(H, W, 3) uint8
    输出：(H*4, W*4, 3) uint8
    """
    inp = np.ascontiguousarray(
        tile_rgb.astype(np.float32) / 255.0
    ).transpose(2, 0, 1)[np.newaxis]                    # (1, 3, H, W)
    out = session.run(None, {inp_name: inp})[0]          # (1, 3, H*4, W*4)
    return np.clip(out[0].transpose(1, 2, 0) * 255.0, 0, 255).astype(np.uint8)


# ─── 分块推理主函数 ───────────────────────────────────────────────────────────

def _upscale_4x(
    rgb: np.ndarray,
    session: ort.InferenceSession,
    tile_size: int,
    tile_pad: int,
    progress_cb: Callable[[int], None] | None = None,
) -> np.ndarray:
    """
    对 RGB uint8 图像执行 4x 分块推理，返回 RGB uint8（4x 尺寸）。
    progress_cb(pct: int) 可选进度回调，范围 5~90。
    """
    h, w = rgb.shape[:2]
    tiles_x = math.ceil(w / tile_size)
    tiles_y = math.ceil(h / tile_size)
    total = tiles_x * tiles_y
    inp_name = session.get_inputs()[0].name   # 在循环外缓存，避免每次 tile 重复查询

    output = np.zeros((h * 4, w * 4, 3), dtype=np.uint8)

    for ty in range(tiles_y):
        for tx in range(tiles_x):
            # 含 pad 的输入区域
            x0 = max(tx * tile_size - tile_pad, 0)
            y0 = max(ty * tile_size - tile_pad, 0)
            x1 = min((tx + 1) * tile_size + tile_pad, w)
            y1 = min((ty + 1) * tile_size + tile_pad, h)

            out_tile = _infer_tile(session, inp_name, rgb[y0:y1, x0:x1])

            # 有效区域（去掉 pad 放大后的边缘）
            crop_x0 = (tx * tile_size - x0) * 4
            crop_y0 = (ty * tile_size - y0) * 4
            valid_w = min(tile_size, w - tx * tile_size) * 4
            valid_h = min(tile_size, h - ty * tile_size) * 4

            dst_x0 = tx * tile_size * 4
            dst_y0 = ty * tile_size * 4
            output[dst_y0:dst_y0 + valid_h, dst_x0:dst_x0 + valid_w] = \
                out_tile[crop_y0:crop_y0 + valid_h, crop_x0:crop_x0 + valid_w]

            if progress_cb:
                progress_cb(int((ty * tiles_x + tx + 1) / total * 85) + 5)

    return output


# ─── 对外主函数 ───────────────────────────────────────────────────────────────

def realesrgan_upscale_bgra(
    img: np.ndarray,
    scale: int = 4,
    denoise_strength: float = 0.5,
    tile_size: int = 256,
    tile_pad: int = 10,
    progress_cb: Callable[[int], None] | None = None,
) -> np.ndarray:
    """
    Real-ESRGAN 超分辨率放大（2x / 4x）。

    Args:
        img:              BGRA uint8 输入图像
        scale:            2 或 4
        denoise_strength: 0~1，0=保留纹理；1=强去噪（推理前高斯平滑）
        tile_size:        分块大小，默认 256
        tile_pad:         块间重叠像素，默认 10
        progress_cb:      可选进度回调 (0~100)，供 UI 进度条使用

    Returns:
        BGRA uint8，尺寸为原图的 scale 倍
    """
    if scale not in (2, 4):
        raise ValueError("scale 必须是 2 或 4")

    if progress_cb:
        progress_cb(3)

    h, w = img.shape[:2]
    bgr = img[:, :, :3].copy()
    alpha = img[:, :, 3].copy() if img.shape[2] == 4 else None

    if denoise_strength > 0:
        bgr = cv2.GaussianBlur(bgr, (0, 0), denoise_strength * 1.5)

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    session = _get_session()

    if progress_cb:
        progress_cb(8)

    rgb_out = _upscale_4x(rgb, session, tile_size, tile_pad, progress_cb)

    if progress_cb:
        progress_cb(92)

    if scale == 2:
        rgb_out = cv2.resize(rgb_out, (w * 2, h * 2), interpolation=cv2.INTER_LANCZOS4)

    bgr_out = cv2.cvtColor(rgb_out, cv2.COLOR_RGB2BGR)
    target_size = (w * scale, h * scale)

    if alpha is not None:
        alpha_out = cv2.resize(alpha, target_size, interpolation=cv2.INTER_LANCZOS4)
        result = cv2.cvtColor(bgr_out, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = alpha_out
    else:
        result = cv2.cvtColor(bgr_out, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = 255

    return result


# ─── QThread Worker ───────────────────────────────────────────────────────────

class RealESRGANWorker(QObject):
    """在 QThread 子线程执行 Real-ESRGAN 推理。"""

    progress = Signal(int)
    finished = Signal(object)   # np.ndarray BGRA
    failed = Signal(str)

    def __init__(
        self,
        img: np.ndarray,
        scale: int = 4,
        denoise_strength: float = 0.5,
        tile_size: int = 256,
        tile_pad: int = 10,
    ) -> None:
        super().__init__()
        self._img = img
        self._scale = scale
        self._denoise = denoise_strength
        self._tile_size = tile_size
        self._tile_pad = tile_pad

    def run(self) -> None:
        try:
            result = realesrgan_upscale_bgra(
                self._img,
                scale=self._scale,
                denoise_strength=self._denoise,
                tile_size=self._tile_size,
                tile_pad=self._tile_pad,
                progress_cb=self.progress.emit,
            )
            self.progress.emit(100)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
