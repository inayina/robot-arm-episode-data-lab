"""CPU contract tests for SmolVLA S4 action-queue runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from training.smolvla_s3.runtime_s4 import (
    DEFAULT_CONTRACT,
    DEFAULT_CONTRACT_JSON,
    DEFAULT_CONTRACT_YAML,
    ActionChunkQueue,
    assert_contract_matches,
    clamp_absolute_action8,
    clip_gripper,
    contract_from_mapping,
    dump_contract_json,
)

UPSTREAM_CONTRACT_JSON = Path(
    "/home/ina/dev/ros2-arm-teleoperation-suite/src/isaac_sim_adapter"
    "/isaac_sim_adapter/s4_runtime_contract.json"
)


def _chunk(value: float = 1.22) -> list[list[float]]:
    return [
        [0.40, 0.0, 0.20, 0.0, 0.0, 0.0, 1.0, value]
        for _ in range(DEFAULT_CONTRACT.chunk_size)
    ]


def test_clip_gripper_matches_gate_v3_execution_semantics() -> None:
    assert clip_gripper(1.22) == (1.0, True)
    assert clip_gripper(-0.05) == (0.0, True)
    assert clip_gripper(0.7) == (0.7, False)


def test_clamp_absolute_action8_workspace_and_gripper() -> None:
    bounded, clipped = clamp_absolute_action8(
        [0.90, 0.0, 0.01, 0.0, 0.0, 0.0, 1.0, 1.22]
    )
    assert clipped is True
    assert bounded[0] == pytest.approx(0.65)
    assert bounded[2] == pytest.approx(0.02)
    assert bounded[7] == pytest.approx(1.0)


def test_action_chunk_queue_executes_k_and_drops_stale_on_replan() -> None:
    queue = ActionChunkQueue(
        chunk_size=DEFAULT_CONTRACT.chunk_size,
        execute_k=DEFAULT_CONTRACT.n_action_steps,
    )
    assert queue.push_chunk(_chunk(), inference_latency_ms=12.5) == 5
    assert queue.pending == 5
    for step in range(5):
        action = queue.pop_action(now_s=0.1 * step)
        assert action is not None
        assert action[7] == pytest.approx(1.0)
    assert queue.pop_action() is None
    assert queue.stats.queue_underruns == 1

    queue.push_chunk(_chunk(0.9))
    _ = queue.pop_action(now_s=1.0)
    assert queue.pending == 4
    queue.push_chunk(_chunk(0.8), inference_latency_ms=20.0)
    assert queue.stats.dropped_stale_actions >= 4
    assert queue.pending == 5
    summary = queue.stats.summary()
    assert summary["claims_task_success"] is False
    assert summary["ran_isaac"] is False
    assert summary["inference_latency_ms_p50"] == pytest.approx(12.5)


def test_hold_clears_queue_and_blocks_until_reset() -> None:
    queue = ActionChunkQueue()
    queue.push_chunk(_chunk())
    queue.hold("nan_detected")
    assert queue.pending == 0
    with pytest.raises(RuntimeError, match="Hold"):
        queue.push_chunk(_chunk())
    queue.reset()
    assert queue.push_chunk(_chunk()) == 5


def test_checked_in_contract_matches_python_defaults(tmp_path: Path) -> None:
    assert DEFAULT_CONTRACT.chunk_size == 10
    assert DEFAULT_CONTRACT.n_action_steps == 5
    assert DEFAULT_CONTRACT.gripper_min == 0.0
    assert DEFAULT_CONTRACT.gripper_max == 1.0
    assert DEFAULT_CONTRACT.state_dim == 15
    assert DEFAULT_CONTRACT.action_dim == 8

    assert_contract_matches(path=DEFAULT_CONTRACT_JSON)
    yaml_payload = yaml.safe_load(DEFAULT_CONTRACT_YAML.read_text(encoding="utf-8"))
    assert contract_from_mapping(yaml_payload) == DEFAULT_CONTRACT

    regenerated = tmp_path / "s4_runtime_contract.json"
    dump_contract_json(regenerated)
    assert regenerated.read_text(encoding="utf-8") == DEFAULT_CONTRACT_JSON.read_text(
        encoding="utf-8"
    )


def test_upstream_contract_json_is_byte_identical_when_present() -> None:
    if not UPSTREAM_CONTRACT_JSON.is_file():
        pytest.skip("upstream checkout not present beside midstream")
    mid = DEFAULT_CONTRACT_JSON.read_bytes()
    up = UPSTREAM_CONTRACT_JSON.read_bytes()
    assert hashlib.sha256(mid).hexdigest() == hashlib.sha256(up).hexdigest()
    assert json.loads(up.decode("utf-8"))["n_action_steps"] == 5
