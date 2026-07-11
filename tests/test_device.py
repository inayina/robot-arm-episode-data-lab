from __future__ import annotations

import pytest


def test_cpu_device_and_checkpoint_roundtrip(tmp_path) -> None:
    torch = pytest.importorskip("torch")
    from training.device import cpu_state_dict, resolve_device
    from training.policies.mlp_policy import MLPPolicy

    device, info = resolve_device("cpu")
    model = MLPPolicy(8, 7).to(device)
    output = model(torch.zeros(2, 8, device=device))
    assert output.shape == (2, 7)
    path = tmp_path / "model.pt"
    torch.save(cpu_state_dict(model), path)
    restored = MLPPolicy(8, 7)
    restored.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
    assert restored(torch.zeros(2, 8)).shape == output.shape


def test_cuda_forward_when_available() -> None:
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA is unavailable")
    from training.device import resolve_device
    from training.policies.mlp_policy import MLPPolicy

    device, _ = resolve_device("cuda")
    assert MLPPolicy(8, 7).to(device)(torch.zeros(2, 8, device=device)).shape == (2, 7)
