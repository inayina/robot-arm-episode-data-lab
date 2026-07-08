"""测试文本编码器模块（mean_hash 后端，无需 torch，可在 CI 中运行）。"""
from __future__ import annotations

import numpy as np
import pytest

from training.encoders.text_encoder import MeanHashEncoder, build_encoder


def test_mean_hash_encoder_output_shape() -> None:
    enc = MeanHashEncoder(output_dim=512)
    vec = enc.encode("pick up the red box")
    assert vec.shape == (512,)
    assert vec.dtype == np.float32


def test_mean_hash_encoder_deterministic() -> None:
    """相同指令每次产生相同向量。"""
    enc = MeanHashEncoder()
    instr = "pick up the blue cylinder and place it in the right bin"
    v1 = enc.encode(instr)
    v2 = enc.encode(instr)
    np.testing.assert_array_equal(v1, v2)


def test_mean_hash_encoder_different_instructions_produce_different_vectors() -> None:
    enc = MeanHashEncoder()
    v1 = enc.encode("pick up the red box")
    v2 = enc.encode("pick up the green sphere")
    assert not np.allclose(v1, v2), "Different instructions must produce different vectors"


def test_mean_hash_encoder_output_is_unit_vector() -> None:
    """编码向量应归一化为单位向量。"""
    enc = MeanHashEncoder()
    vec = enc.encode("pick up the red box and place it in the left bin")
    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-5, f"Expected unit vector, got norm={norm}"


def test_mean_hash_encoder_custom_dim() -> None:
    enc = MeanHashEncoder(output_dim=128)
    assert enc.output_dim == 128
    vec = enc.encode("test")
    assert vec.shape == (128,)


def test_build_encoder_mean_hash() -> None:
    enc = build_encoder("mean_hash")
    assert isinstance(enc, MeanHashEncoder)
    assert enc.output_dim == 512


def test_build_encoder_unknown_backend_raises() -> None:
    with pytest.raises(ValueError, match="Unknown text encoder backend"):
        build_encoder("nonexistent_backend")


def test_build_encoder_custom_dim_kwarg() -> None:
    enc = build_encoder("mean_hash", output_dim=64)
    assert enc.output_dim == 64
    assert enc.encode("hello").shape == (64,)
