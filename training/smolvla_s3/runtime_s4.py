"""SmolVLA S4 bounded action-queue runtime contract (CPU-only).

Implements the Recovery §8 queue semantics used before Isaac rollout:
chunk=10, execute K=5, replan 0.5 s at 10 Hz, gripper = clip(raw, 0, 1).

Single-source constants live in ``S4RuntimeContract`` and the checked-in
``configs/smolvla_s3/s4_runtime_contract.{yaml,json}``. Upstream Isaac loads a
byte-identical copy and asserts field consistency at startup.

This module does not load SmolVLA weights, start Isaac, or claim task success.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Deque, Mapping, Sequence

CONTRACT_VERSION = "smolvla_s3_s4_runtime_v0"
POLICY_ACTION_SEMANTICS = "absolute_eef_gripper_v0"

# Midstream package root → repo root / configs/smolvla_s3/
_CONTRACT_DIR = Path(__file__).resolve().parents[2] / "configs" / "smolvla_s3"
DEFAULT_CONTRACT_YAML = _CONTRACT_DIR / "s4_runtime_contract.yaml"
DEFAULT_CONTRACT_JSON = _CONTRACT_DIR / "s4_runtime_contract.json"


@dataclass(frozen=True)
class S4RuntimeContract:
    """Frozen S4 online/offline runtime constants (Recovery v3)."""

    contract_version: str = CONTRACT_VERSION
    policy_action_semantics: str = POLICY_ACTION_SEMANTICS
    chunk_size: int = 10
    n_action_steps: int = 5  # execute K; LeRobot deploy n_action_steps
    control_rate_hz: float = 10.0
    replan_period_s: float = 0.5
    state_dim: int = 15
    action_dim: int = 8
    gripper_min: float = 0.0
    gripper_max: float = 1.0
    workspace_min: tuple[float, float, float] = (0.20, -0.40, 0.02)
    workspace_max: tuple[float, float, float] = (0.65, 0.40, 0.75)
    image_height: int = 240
    image_width: int = 320
    camera_key: str = "observation.images.scene"
    claims_task_success: bool = False
    claims_sim2real: bool = False

    @property
    def execute_k(self) -> int:
        return self.n_action_steps

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["workspace_min"] = list(self.workspace_min)
        payload["workspace_max"] = list(self.workspace_max)
        return payload


DEFAULT_CONTRACT = S4RuntimeContract()
DEFAULT_CHUNK_SIZE = DEFAULT_CONTRACT.chunk_size
DEFAULT_EXECUTE_K = DEFAULT_CONTRACT.n_action_steps
DEFAULT_CONTROL_RATE_HZ = DEFAULT_CONTRACT.control_rate_hz
DEFAULT_REPLAN_PERIOD_S = DEFAULT_CONTRACT.replan_period_s


def contract_from_mapping(data: Mapping[str, Any]) -> S4RuntimeContract:
    """Build a contract from a YAML/JSON mapping."""
    required = (
        "contract_version",
        "policy_action_semantics",
        "chunk_size",
        "n_action_steps",
        "control_rate_hz",
        "replan_period_s",
        "state_dim",
        "action_dim",
        "gripper_min",
        "gripper_max",
        "workspace_min",
        "workspace_max",
        "image_height",
        "image_width",
        "camera_key",
        "claims_task_success",
        "claims_sim2real",
    )
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"S4 contract missing fields: {missing}")
    ws_min = tuple(float(v) for v in data["workspace_min"])
    ws_max = tuple(float(v) for v in data["workspace_max"])
    if len(ws_min) != 3 or len(ws_max) != 3:
        raise ValueError("workspace_min/max must have three components")
    return S4RuntimeContract(
        contract_version=str(data["contract_version"]),
        policy_action_semantics=str(data["policy_action_semantics"]),
        chunk_size=int(data["chunk_size"]),
        n_action_steps=int(data["n_action_steps"]),
        control_rate_hz=float(data["control_rate_hz"]),
        replan_period_s=float(data["replan_period_s"]),
        state_dim=int(data["state_dim"]),
        action_dim=int(data["action_dim"]),
        gripper_min=float(data["gripper_min"]),
        gripper_max=float(data["gripper_max"]),
        workspace_min=(ws_min[0], ws_min[1], ws_min[2]),
        workspace_max=(ws_max[0], ws_max[1], ws_max[2]),
        image_height=int(data["image_height"]),
        image_width=int(data["image_width"]),
        camera_key=str(data["camera_key"]),
        claims_task_success=bool(data["claims_task_success"]),
        claims_sim2real=bool(data["claims_sim2real"]),
    )


def load_contract(path: Path | None = None) -> S4RuntimeContract:
    """Load checked-in S4 contract (JSON preferred; YAML needs PyYAML)."""
    target = Path(path) if path is not None else DEFAULT_CONTRACT_JSON
    if not target.is_file():
        # Fall back to YAML when JSON is absent (e.g. partial checkout).
        if path is None and DEFAULT_CONTRACT_YAML.is_file():
            target = DEFAULT_CONTRACT_YAML
        else:
            raise FileNotFoundError(f"S4 runtime contract not found: {target}")
    text = target.read_text(encoding="utf-8")
    if target.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "PyYAML required to load s4_runtime_contract.yaml"
            ) from exc
        data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"S4 contract must be a mapping: {target}")
    return contract_from_mapping(data)


def dump_contract_json(
    path: Path | None = None,
    *,
    contract: S4RuntimeContract = DEFAULT_CONTRACT,
) -> Path:
    """Write the frozen contract as pretty JSON (cross-repo sync artifact)."""
    target = Path(path) if path is not None else DEFAULT_CONTRACT_JSON
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(contract.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def assert_contract_matches(
    contract: S4RuntimeContract | None = None,
    *,
    path: Path | None = None,
    reference: S4RuntimeContract = DEFAULT_CONTRACT,
) -> S4RuntimeContract:
    """Assert a loaded (or provided) contract equals the Python defaults."""
    loaded = contract if contract is not None else load_contract(path)
    if loaded != reference:
        raise AssertionError(
            "S4 runtime contract drift: "
            f"loaded={loaded.to_dict()} reference={reference.to_dict()}"
        )
    if loaded.n_action_steps > loaded.chunk_size:
        raise AssertionError("n_action_steps (K) cannot exceed chunk_size")
    if loaded.gripper_min != 0.0 or loaded.gripper_max != 1.0:
        raise AssertionError("gripper clip must be [0, 1] for gate v3 execution")
    return loaded


@dataclass
class RuntimeSafetyEvent:
    kind: str
    detail: str


@dataclass
class S4RuntimeStats:
    inference_latency_ms: list[float] = field(default_factory=list)
    command_publish_intervals_ms: list[float] = field(default_factory=list)
    queue_underruns: int = 0
    dropped_stale_actions: int = 0
    gripper_clips: int = 0
    hold_or_estop_events: list[RuntimeSafetyEvent] = field(default_factory=list)

    def summary(self) -> dict:
        def _pct(values: list[float], q: float) -> float | None:
            if not values:
                return None
            ordered = sorted(values)
            index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
            return float(ordered[index])

        return {
            "contract_version": CONTRACT_VERSION,
            "inference_latency_ms_p50": _pct(self.inference_latency_ms, 0.50),
            "inference_latency_ms_p95": _pct(self.inference_latency_ms, 0.95),
            "command_publish_jitter_ms_p95": _pct(
                self.command_publish_intervals_ms, 0.95
            ),
            "queue_underruns": self.queue_underruns,
            "dropped_stale_actions": self.dropped_stale_actions,
            "gripper_clips": self.gripper_clips,
            "hold_or_estop_count": len(self.hold_or_estop_events),
            "claims_task_success": False,
            "ran_isaac": False,
        }


def clip_gripper(
    raw: float,
    *,
    gripper_min: float = DEFAULT_CONTRACT.gripper_min,
    gripper_max: float = DEFAULT_CONTRACT.gripper_max,
) -> tuple[float, bool]:
    if not math.isfinite(raw):
        raise ValueError("gripper raw is non-finite")
    clipped = max(float(gripper_min), min(float(gripper_max), float(raw)))
    return clipped, clipped != float(raw)


def clamp_absolute_action8(
    action: Sequence[float],
    *,
    workspace_min: Sequence[float] = DEFAULT_CONTRACT.workspace_min,
    workspace_max: Sequence[float] = DEFAULT_CONTRACT.workspace_max,
    gripper_min: float = DEFAULT_CONTRACT.gripper_min,
    gripper_max: float = DEFAULT_CONTRACT.gripper_max,
) -> tuple[tuple[float, ...], bool]:
    """Clamp abs EEF[8] pose into workspace and gripper into [0, 1]."""
    if len(action) != DEFAULT_CONTRACT.action_dim:
        raise ValueError(
            f"expected action[{DEFAULT_CONTRACT.action_dim}], got [{len(action)}]"
        )
    values = [float(v) for v in action]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("action contains non-finite values")
    clipped = False
    xyz = []
    for index, value in enumerate(values[:3]):
        lo = float(workspace_min[index])
        hi = float(workspace_max[index])
        bound = max(lo, min(hi, value))
        clipped = clipped or bound != value
        xyz.append(bound)
    grip, grip_clipped = clip_gripper(
        values[7], gripper_min=gripper_min, gripper_max=gripper_max
    )
    clipped = clipped or grip_clipped
    return (*xyz, *values[3:7], grip), clipped


class ActionChunkQueue:
    """Execute the first K actions of each chunk; drop the rest on replan."""

    def __init__(
        self,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        execute_k: int = DEFAULT_EXECUTE_K,
    ) -> None:
        if chunk_size <= 0 or execute_k <= 0:
            raise ValueError("chunk_size and execute_k must be positive")
        if execute_k > chunk_size:
            raise ValueError("execute_k cannot exceed chunk_size")
        self.chunk_size = chunk_size
        self.execute_k = execute_k
        self._queue: Deque[tuple[float, ...]] = deque()
        self.stats = S4RuntimeStats()
        self._held = False
        self._last_publish_ts: float | None = None

    def reset(self) -> None:
        dropped = len(self._queue)
        self._queue.clear()
        self.stats.dropped_stale_actions += dropped
        self._held = False
        self._last_publish_ts = None

    def hold(self, reason: str) -> None:
        dropped = len(self._queue)
        self._queue.clear()
        self.stats.dropped_stale_actions += dropped
        self._held = True
        self._last_publish_ts = None
        self.stats.hold_or_estop_events.append(
            RuntimeSafetyEvent(kind="hold", detail=reason)
        )

    def push_chunk(
        self,
        actions: Sequence[Sequence[float]],
        *,
        inference_latency_ms: float | None = None,
    ) -> int:
        if self._held:
            raise RuntimeError("runtime is in Hold; reset before push_chunk")
        if len(actions) != self.chunk_size:
            raise ValueError(
                f"expected chunk of {self.chunk_size}, got {len(actions)}"
            )
        # Drop remaining stale actions from the previous chunk (async replan).
        dropped = len(self._queue)
        self._queue.clear()
        self.stats.dropped_stale_actions += dropped
        if inference_latency_ms is not None:
            self.stats.inference_latency_ms.append(float(inference_latency_ms))
        accepted = 0
        for raw in actions[: self.execute_k]:
            bounded, clipped = clamp_absolute_action8(raw)
            if clipped:
                self.stats.gripper_clips += int(bounded[7] != float(raw[7]))
            self._queue.append(bounded)
            accepted += 1
        return accepted

    def pop_action(self, *, now_s: float | None = None) -> tuple[float, ...] | None:
        if self._held:
            return None
        if not self._queue:
            self.stats.queue_underruns += 1
            return None
        action = self._queue.popleft()
        if now_s is not None:
            if self._last_publish_ts is not None:
                self.stats.command_publish_intervals_ms.append(
                    1000.0 * (float(now_s) - self._last_publish_ts)
                )
            self._last_publish_ts = float(now_s)
        return action

    @property
    def pending(self) -> int:
        return len(self._queue)
