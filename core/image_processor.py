from __future__ import annotations
import math
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


class ImageProcessor:
    """图像处理工具类，所有方法均为静态纯函数，不修改输入，返回新数组。"""

    # ------------------------------------------------------------------
    # 文件读写
    # ------------------------------------------------------------------

    @staticmethod
    def read_image(path: str) -> np.ndarray:
        """
        读取图片文件，返回 BGRA uint8 数组。
        支持 PNG/JPG/BMP/TIFF/WEBP，兼容中文路径。
        """
        if not Path(path).exists():
            raise FileNotFoundError(f"文件不存在: {path}")

        buf = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)

        if img is None:
            raise ValueError(f"无法解码图片: {path}")

        # 统一转为 BGRA 4 通道
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
        elif img.shape[2] == 3:
            bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            bgra[:, :, 3] = 255
            img = bgra
        # 已是 BGRA (shape[2]==4)：直接使用

        return img

    @staticmethod
    def write_image(img: np.ndarray, path: str, quality: int = 95) -> None:
        """
        将图像写入文件。
        PNG/TIFF：无损，保留 alpha。
        JPG：alpha 合并到白底，quality 参数控制质量。
        兼容中文路径。
        """
        ext = Path(path).suffix.lower()
        if ext == ".png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 1]
            success, buf = cv2.imencode(".png", img, params)
            if not success:
                raise RuntimeError("PNG 编码失败")
            buf.tofile(path)

        elif ext in (".jpg", ".jpeg"):
            bgr = ImageProcessor.alpha_composite_white(img)
            q = max(1, min(100, quality))
            params = [cv2.IMWRITE_JPEG_QUALITY, q]
            success, buf = cv2.imencode(".jpg", bgr, params)
            if not success:
                raise RuntimeError("JPG 编码失败")
            buf.tofile(path)

        elif ext in (".tiff", ".tif"):
            success, buf = cv2.imencode(".tiff", img)
            if not success:
                raise RuntimeError("TIFF 编码失败")
            buf.tofile(path)

        elif ext == ".bmp":
            success, buf = cv2.imencode(".bmp", img)
            if not success:
                raise RuntimeError("BMP 编码失败")
            buf.tofile(path)

        else:
            raise ValueError(f"不支持的导出格式: {ext}")

    @staticmethod
    def alpha_composite_white(img: np.ndarray) -> np.ndarray:
        """将 BGRA 图像合并到白色背景，返回 BGR 图像。"""
        if img.shape[2] == 3:
            return img.copy()

        bgr = img[:, :, :3].astype(np.float32)
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        white = np.full_like(bgr, 255.0)
        result = bgr * alpha + white * (1.0 - alpha)
        return result.astype(np.uint8)

    # ------------------------------------------------------------------
    # 变换操作
    # ------------------------------------------------------------------

    @staticmethod
    def crop(img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """裁剪图像，坐标自动 clamp 防止越界。"""
        h, w = img.shape[:2]
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))
        if x2 <= x1 or y2 <= y1:
            return img.copy()
        return img[y1:y2, x1:x2].copy()

    @staticmethod
    def rotate_90cw(img: np.ndarray) -> np.ndarray:
        """顺时针旋转 90°，无插值，完全无损。"""
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

    @staticmethod
    def rotate_90ccw(img: np.ndarray) -> np.ndarray:
        """逆时针旋转 90°，无插值，完全无损。"""
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    @staticmethod
    def rotate_180(img: np.ndarray) -> np.ndarray:
        """旋转 180°，无插值，完全无损。"""
        return cv2.rotate(img, cv2.ROTATE_180)

    @staticmethod
    def rotate_arbitrary(img: np.ndarray, angle: float,
                         expand: bool = True) -> np.ndarray:
        """
        任意角度旋转（正值逆时针，负值顺时针）。
        expand=True 时扩展画布保留完整内容，使用 LANCZOS4 高质量插值。
        """
        h, w = img.shape[:2]
        cx, cy = w / 2.0, h / 2.0
        M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)

        if expand:
            cos_a = abs(math.cos(math.radians(angle)))
            sin_a = abs(math.sin(math.radians(angle)))
            new_w = int(h * sin_a + w * cos_a)
            new_h = int(h * cos_a + w * sin_a)
            M[0, 2] += (new_w / 2.0) - cx
            M[1, 2] += (new_h / 2.0) - cy
        else:
            new_w, new_h = w, h

        result = cv2.warpAffine(
            img, M, (new_w, new_h),
            flags=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0, 0)
        )
        return result

    @staticmethod
    def delete_selection(img: np.ndarray,
                         x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """
        将矩形选区内容 alpha 设为 0（透明删除）。
        返回新数组，不修改输入。
        """
        result = img.copy()
        h, w = result.shape[:2]
        x1 = max(0, min(x1, w))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h))
        y2 = max(0, min(y2, h))
        if result.shape[2] == 4:
            result[y1:y2, x1:x2, 3] = 0
        else:
            result[y1:y2, x1:x2] = 0
        return result
