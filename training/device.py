"""PyTorch device selection shared by low-dimensional training scripts."""

from __future__ import annotations


def resolve_device(requested: str):
    import torch

    requested = requested.lower()
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError("device must be one of: auto, cpu, cuda")
    available = bool(torch.cuda.is_available())
    if requested == "cuda" and not available:
        raise RuntimeError(
            "CUDA was requested but torch.cuda.is_available() is false; "
            "check nvidia-smi and the NVIDIA kernel driver"
        )
    selected = "cuda" if requested == "cuda" or (requested == "auto" and available) else "cpu"
    device = torch.device(selected)
    details = {
        "requested": requested,
        "selected": selected,
        "torch_version": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "cuda_available": available,
        "gpu_name": torch.cuda.get_device_name(0) if selected == "cuda" else None,
        "gpu_memory_bytes": (
            int(torch.cuda.get_device_properties(0).total_memory) if selected == "cuda" else None
        ),
    }
    return device, details


def cpu_state_dict(model) -> dict:
    return {key: value.detach().cpu() for key, value in model.state_dict().items()}
