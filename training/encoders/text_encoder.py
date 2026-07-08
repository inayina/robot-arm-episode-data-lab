"""文本编码器模块：为语言条件 ACT 训练提供固定维度的文本向量。

支持两种后端：
  - ``clip``   : 使用 HuggingFace CLIPTextModel（需要 torch + transformers）。
                 在 lerobot conda 环境中自动启用。
  - ``mean_hash``: 纯 numpy 确定性哈希，无需任何 ML 依赖。
                 供 CI / 离线测试使用，不依赖 torch。

接口
----
    encoder = build_encoder("clip")          # 或 "mean_hash"
    vec = encoder.encode("pick up the red box")
    # vec.shape == (512,), dtype=float32

设计原则
--------
    torch / transformers 均为可选导入。未安装时，clip 后端初始化会抛出
    ImportError 并提示切换到 mean_hash。这样 .venv CI 环境完全不受影响。
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass  # 仅用于类型注解，不实际导入 torch

CLIP_OUTPUT_DIM = 512
MEAN_HASH_OUTPUT_DIM = 512


class TextEncoder(ABC):
    """文本编码器抽象基类。"""

    @property
    @abstractmethod
    def output_dim(self) -> int:
        """返回编码向量的维度。"""

    @abstractmethod
    def encode(self, instruction: str) -> np.ndarray:
        """将自然语言指令编码为固定长度浮点向量。

        Parameters
        ----------
        instruction:
            自然语言任务指令，例如 "pick up the red box".

        Returns
        -------
        np.ndarray
            形状 ``(output_dim,)``，dtype ``float32``。
        """


class MeanHashEncoder(TextEncoder):
    """纯 numpy 确定性编码器，用于 CI / 离线测试场景。

    算法：对指令字符串进行 SHA-256 哈希，取前 ``output_dim`` 字节并归一化到
    [-1, 1]，保证相同字符串始终产生相同向量，不需要任何 ML 库。
    """

    def __init__(self, output_dim: int = MEAN_HASH_OUTPUT_DIM) -> None:
        self._output_dim = output_dim

    @property
    def output_dim(self) -> int:
        return self._output_dim

    def encode(self, instruction: str) -> np.ndarray:
        # 重复哈希直到获得足够字节
        raw = b""
        seed = instruction.encode("utf-8")
        while len(raw) < self._output_dim:
            raw += hashlib.sha256(seed + raw).digest()
        arr = np.frombuffer(raw[: self._output_dim], dtype=np.uint8).astype(np.float32)
        # 归一化到 [-1, 1]
        arr = arr / 127.5 - 1.0
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.astype(np.float32)


class CLIPTextEncoder(TextEncoder):
    """基于 HuggingFace CLIPTextModel 的文本编码器（需要 torch + transformers）。

    在 lerobot conda 环境中使用。初始化时会懒加载模型（首次 encode 调用时）。
    """

    MODEL_NAME = "openai/clip-vit-base-patch32"

    def __init__(
        self,
        model_name: str = MODEL_NAME,
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._tokenizer = None
        self._model = None

    @property
    def output_dim(self) -> int:
        return CLIP_OUTPUT_DIM

    def _load(self) -> None:
        """懒加载模型（首次调用时执行）。"""
        if self._model is not None:
            return
        try:
            from transformers import CLIPTextModel, CLIPTokenizer  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "CLIPTextEncoder requires 'transformers'. "
                "Run: pip install transformers\n"
                "Or switch to the 'mean_hash' backend for CI usage."
            ) from exc

        try:
            import torch  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "CLIPTextEncoder requires 'torch'. "
                "Activate the lerobot conda environment or use 'mean_hash' backend."
            ) from exc

        self._torch = torch
        self._tokenizer = CLIPTokenizer.from_pretrained(self._model_name)
        self._model = CLIPTextModel.from_pretrained(self._model_name)
        self._model.eval()
        self._model.to(self._device)

    def encode(self, instruction: str) -> np.ndarray:
        self._load()
        torch = self._torch
        inputs = self._tokenizer(
            instruction,
            return_tensors="pt",
            truncation=True,
            max_length=77,
            padding="max_length",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self._model(**inputs)
        # pooler_output: (1, 512)
        vec = outputs.pooler_output.squeeze(0).cpu().numpy().astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec


_BACKENDS: dict[str, type[TextEncoder]] = {
    "clip": CLIPTextEncoder,
    "mean_hash": MeanHashEncoder,
}


def build_encoder(backend: str = "mean_hash", **kwargs) -> TextEncoder:
    """工厂函数：根据后端名称创建文本编码器实例。

    Parameters
    ----------
    backend:
        ``"clip"`` 或 ``"mean_hash"``。
    **kwargs:
        透传给对应编码器的构造参数。

    Returns
    -------
    TextEncoder
    """
    if backend not in _BACKENDS:
        raise ValueError(
            f"Unknown text encoder backend: {backend!r}. "
            f"Available: {sorted(_BACKENDS)}"
        )
    return _BACKENDS[backend](**kwargs)
