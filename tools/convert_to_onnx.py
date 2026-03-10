"""
将 Real-ESRGAN .pth 模型转换为 .onnx，供 onnxruntime 推理使用。

支持的模型：
  - RealESRGAN_x4plus_anime_6B.pth  → RRDBNet(num_block=6)
  - realesr-general-x4v3.pth        → SRVGGNetCompact(num_conv=32)

用法：
  uv run --with torch python tools/convert_to_onnx.py [模型文件名（不含路径）]

示例：
  uv run --with torch python tools/convert_to_onnx.py RealESRGAN_x4plus_anime_6B.pth
  uv run --with torch python tools/convert_to_onnx.py realesr-general-x4v3.pth
  uv run --with torch python tools/convert_to_onnx.py   # 使用默认模型
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).parent.parent
MODELS_DIR = ROOT / "models"

# ──── 默认模型 ────────────────────────────────────────────────────────────────
DEFAULT_MODEL = "RealESRGAN_x4plus_anime_6B.pth"


# ──── SRVGGNetCompact（realesr-general-x4v3）────────────────────────────────

class SRVGGNetCompact(nn.Module):
    """紧凑型超分辨率网络，用于 realesr-general-x4v3。"""

    def __init__(
        self,
        num_in_ch: int = 3,
        num_out_ch: int = 3,
        num_feat: int = 64,
        num_conv: int = 32,
        upscale: int = 4,
        act_type: str = "prelu",
    ) -> None:
        super().__init__()
        self.upscale = upscale
        self.body: nn.ModuleList = nn.ModuleList()
        self.body.append(nn.Conv2d(num_in_ch, num_feat, 3, 1, 1))
        if act_type == "relu":
            act: nn.Module = nn.ReLU(inplace=True)
        elif act_type == "prelu":
            act = nn.PReLU(num_parameters=num_feat)
        else:
            act = nn.LeakyReLU(negative_slope=0.1, inplace=True)
        self.body.append(act)
        for _ in range(num_conv):
            self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            self.body.append(deepcopy(act))
        self.body.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.upsample = nn.PixelShuffle(upscale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        for layer in self.body:
            x = layer(x)
        return self.upsample(x)


# ──── RRDBNet（RealESRGAN_x4plus / anime 系列）────────────────────────────────

class ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat: int = 64, num_grow_ch: int = 32) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat: int, num_grow_ch: int = 32) -> None:
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    def __init__(
        self,
        num_in_ch: int = 3,
        num_out_ch: int = 3,
        scale: int = 4,
        num_feat: int = 64,
        num_block: int = 23,
        num_grow_ch: int = 32,
    ) -> None:
        super().__init__()
        self.scale = scale
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.conv_first(x)
        body_feat = self.conv_body(self.body(feat))
        feat = feat + body_feat
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        return self.conv_last(self.lrelu(self.conv_hr(feat)))


# ──── 架构自动检测 ─────────────────────────────────────────────────────────────

def _detect_arch(state: dict) -> tuple[nn.Module, str]:
    """根据 state dict 的 key 格式判断架构，返回 (model, arch_name)。"""
    if "conv_first.weight" in state:
        # RRDBNet: 通过 body 层数推断 num_block
        num_block = sum(1 for k in state if k.startswith("body.") and k.endswith(".rdb1.conv1.weight"))
        num_feat = state["conv_first.weight"].shape[0]
        num_grow_ch = state["body.0.rdb1.conv1.weight"].shape[0]
        model = RRDBNet(num_feat=num_feat, num_block=num_block, num_grow_ch=num_grow_ch)
        arch = f"RRDBNet(num_feat={num_feat}, num_block={num_block}, num_grow_ch={num_grow_ch})"
    else:
        # SRVGGNetCompact: body 索引最大值推算 num_conv
        max_idx = max(int(k.split(".")[1]) for k in state if k.startswith("body."))
        num_conv = (max_idx - 1) // 2
        num_feat = state["body.0.weight"].shape[0]
        model = SRVGGNetCompact(num_feat=num_feat, num_conv=num_conv)
        arch = f"SRVGGNetCompact(num_feat={num_feat}, num_conv={num_conv})"
    return model, arch


# ──── 转换主函数 ───────────────────────────────────────────────────────────────

def convert(model_filename: str) -> None:
    pth_path = MODELS_DIR / model_filename
    onnx_path = MODELS_DIR / (Path(model_filename).stem + ".onnx")

    if not pth_path.exists():
        raise FileNotFoundError(f"未找到模型文件：{pth_path}")

    print(f"加载模型：{pth_path}")
    raw = torch.load(pth_path, map_location="cpu", weights_only=True)
    if "params_ema" in raw:
        state = raw["params_ema"]
    elif "params" in raw:
        state = raw["params"]
    else:
        state = raw

    model, arch = _detect_arch(state)
    print(f"检测到架构：{arch}")
    model.load_state_dict(state, strict=True)
    model.eval()
    total_params = sum(p.numel() for p in model.parameters())
    print(f"参数量：{total_params:,}")

    dummy = torch.zeros(1, 3, 64, 64)
    print(f"导出 ONNX（旧版导出器，opset=17）：{onnx_path}")

    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        dynamo=False,
        opset_version=17,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input":  {0: "batch", 2: "height", 3: "width"},
            "output": {0: "batch", 2: "height", 3: "width"},
        },
    )
    print(f"✅ 转换完成！ONNX 已保存到：{onnx_path}")


if __name__ == "__main__":
    filename = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    convert(filename)
