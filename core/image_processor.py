from __future__ import annotations
from pathlib import Path

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

    @staticmethod
    def trim_to_content(img: np.ndarray, threshold: int = 0) -> np.ndarray:
        """
        裁去图片四周多余的透明像素，保留主体内容的最小边界框。
        等同于 Photoshop「图像 → 裁切 → 基于透明像素」。

        Args:
            img:       BGRA 图像（含 alpha 通道）
            threshold: alpha 阈值，> threshold 才算不透明，默认 0

        Returns:
            裁切后的新 BGRA 数组

        Raises:
            ValueError: 图片全透明，无内容可保留
        """
        if img.shape[2] < 4:
            raise ValueError("图片不含透明通道，无需符合画布操作")
        alpha = img[:, :, 3]
        mask = alpha > threshold
        if not mask.any():
            raise ValueError("图片全透明，无内容可保留")
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        r0, r1 = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
        c0, c1 = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])
        return img[r0:r1 + 1, c0:c1 + 1].copy()

    # 对外暴露的插值模式名称 → cv2 常量映射
    INTERP_MODES: dict[str, int] = {
        "lanczos":  cv2.INTER_LANCZOS4,   # 高质量插值（默认）
        "nearest":  cv2.INTER_NEAREST,    # 最近邻：零混色，保留原始像素颗粒
    }

    @staticmethod
    def resize_to_size(img: np.ndarray,
                       target_w: int,
                       target_h: int,
                       keep_aspect: bool = True,
                       sharpen: bool = True,
                       interp: str = "lanczos") -> np.ndarray:
        """
        将图片重采样到指定尺寸。

        keep_aspect=True：等比缩放，以 min(tw/w, th/h) 为缩放系数；
            若 target_w 或 target_h 其中一个为 0，则仅按另一边等比计算。
        keep_aspect=False：强制拉伸到精确的 target_w × target_h。

        Args:
            img:         BGRA 图像
            target_w:    目标宽度（像素）；0 表示按高度自动（keep_aspect=True 有效）
            target_h:    目标高度（像素）；0 表示按宽度自动（keep_aspect=True 有效）
            keep_aspect: 是否保持宽高比，默认 True
            sharpen:     缩放后是否应用非锐化蒙版（interp="nearest" 时自动忽略）
            interp:      插值模式："lanczos"（高质量）或 "nearest"（最近邻/保留像素）

        Returns:
            重采样后的新 BGRA 数组
        """
        if target_w < 0 or target_h < 0:
            raise ValueError("目标尺寸不能为负数")
        if target_w == 0 and target_h == 0:
            raise ValueError("target_w 和 target_h 不能同时为 0")

        h, w = img.shape[:2]
        if keep_aspect:
            if target_w == 0:
                scale = target_h / h
            elif target_h == 0:
                scale = target_w / w
            else:
                scale = min(target_w / w, target_h / h)
            new_w = max(1, int(round(w * scale)))
            new_h = max(1, int(round(h * scale)))
        else:
            new_w = target_w if target_w > 0 else w
            new_h = target_h if target_h > 0 else h

        cv2_interp = ImageProcessor.INTERP_MODES.get(interp, cv2.INTER_LANCZOS4)
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2_interp)

        # 最近邻不需要也不应该锐化（像素已经是原色，锐化反而会产生光晕）
        if sharpen and interp != "nearest":
            resized = ImageProcessor._unsharp_mask(resized)

        return resized

    @staticmethod
    def _unsharp_mask(img: np.ndarray,
                      sigma: float = 1.0,
                      strength: float = 0.45) -> np.ndarray:
        """
        非锐化蒙版（Unsharp Mask）：提升缩放后图片的感知清晰度。

        原理：sharpened = original × (1+s) - blurred × s
        只作用于 BGR 三通道，alpha 通道保持不变，避免透明边缘产生光晕。

        Args:
            img:      BGRA 图像
            sigma:    高斯模糊半径，越大锐化范围越宽，默认 1.0
            strength: 锐化强度（0~1），默认 0.45（适中，不过度）
        """
        bgr = img[:, :, :3].astype(np.float32)
        blurred = cv2.GaussianBlur(bgr, (0, 0), sigma)
        sharpened = bgr * (1.0 + strength) - blurred * strength
        sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
        result = img.copy()
        result[:, :, :3] = sharpened
        return result
