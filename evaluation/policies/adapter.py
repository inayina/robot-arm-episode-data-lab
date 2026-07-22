"""Model-agnostic Policy Adapter contract (midstream, offline-safe).

This module defines the thin interface only. It does not load ACT checkpoints,
call Isaac, or claim task success. Upstream runtime wrappers may implement the
same method names later without changing three-repo boundaries.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, MutableMapping, Sequence

import math

ACTION_SCHEMA_VERSION = "panda_ee_delta_gripper_v0"
ACTION_DIM = 7
CONTRACT_VERSION = "policy_adapter_contract_v0"


class PolicyAdapterError(ValueError):
    """Raised for interface-lane failures (never rewritten as task success)."""


class PolicyAdapter(ABC):
    """Minimal adapter surface shared by ACT, oracle, rule baselines, and future VLAs."""

    @abstractmethod
    def load_policy(self, checkpoint_or_endpoint: str | None) -> None:
        """Load weights or bind an endpoint. Oracle/rule may accept None."""

    @abstractmethod
    def reset(self, context: Mapping[str, Any]) -> None:
        """Clear chunk/history at episode boundaries."""

    @abstractmethod
    def build_observation(self, raw_state: Mapping[str, Any]) -> dict[str, Any]:
        """Map raw simulator/ROS state into model observation dict."""

    @abstractmethod
    def predict_action(
        self,
        observation: Mapping[str, Any],
        instruction: str | None = None,
    ) -> Sequence[float]:
        """Return model-native raw action (may be longer than 7 for foreign models)."""

    @abstractmethod
    def validate_action(self, action: Sequence[float]) -> Sequence[float]:
        """Check dim/finite; raise PolicyAdapterError on interface failure."""

    @abstractmethod
    def export_action(self, action: Sequence[float]) -> list[float]:
        """Map validated action to ee_delta_gripper[7]."""

    @abstractmethod
    def report_metadata(self) -> dict[str, Any]:
        """Return frozen identity + latest step fields; claims_task_success must be false."""

    @abstractmethod
    def close(self) -> None:
        """Release resources."""


def validate_ee_delta_gripper(action: Sequence[float]) -> list[float]:
    """Shared validator for panda_ee_delta_gripper_v0."""
    if len(action) != ACTION_DIM:
        raise PolicyAdapterError(
            f"expected action dim {ACTION_DIM}, got {len(action)}"
        )
    values = [float(x) for x in action]
    if not all(math.isfinite(v) for v in values):
        raise PolicyAdapterError("action contains non-finite values")
    return values


def empty_step_fields() -> dict[str, Any]:
    """Null runtime fields for identity-only metadata cards."""
    return {
        "inference_latency_ms": None,
        "raw_action": None,
        "postprocessed_action": None,
        "safety_clipping": {
            "applied": False,
            "axes": ["none"],
            "notes": None,
        },
        "failure_lane": "none",
        "claims_task_success": False,
    }


class FixturePolicyAdapter(PolicyAdapter):
    """Offline fixture adapter for unit tests (no ROS / Isaac / GPU)."""

    def __init__(self, identity: MutableMapping[str, Any]) -> None:
        if identity.get("claims_task_success") is not False:
            raise PolicyAdapterError("claims_task_success must be false")
        if identity.get("action_schema_version") != ACTION_SCHEMA_VERSION:
            raise PolicyAdapterError(
                f"action_schema_version must be {ACTION_SCHEMA_VERSION}"
            )
        self._identity = dict(identity)
        self._loaded = False
        self._closed = False
        self._last_raw: list[float] | None = None
        self._last_exported: list[float] | None = None
        self._latency_ms: float | None = None

    def load_policy(self, checkpoint_or_endpoint: str | None) -> None:
        if self._closed:
            raise PolicyAdapterError("adapter already closed")
        # Identity is frozen; path is recorded only for provenance tests.
        self._identity["loaded_from"] = checkpoint_or_endpoint
        self._loaded = True

    def reset(self, context: Mapping[str, Any]) -> None:
        if not self._loaded:
            raise PolicyAdapterError("load_policy required before reset")
        self._identity["last_reset_context"] = dict(context)
        self._last_raw = None
        self._last_exported = None
        self._latency_ms = None

    def build_observation(self, raw_state: Mapping[str, Any]) -> dict[str, Any]:
        state = raw_state.get("state")
        if state is None or len(state) != 8:
            raise PolicyAdapterError("raw_state.state must be length 8")
        return {
            "observation.state": [float(x) for x in state],
            "observation_schema_version": self._identity["observation_schema_version"],
        }

    def predict_action(
        self,
        observation: Mapping[str, Any],
        instruction: str | None = None,
    ) -> Sequence[float]:
        del instruction  # ACT path ignores language; fixture mirrors that.
        if "observation.state" not in observation:
            raise PolicyAdapterError("observation missing observation.state")
        # Near-zero delta, gripper open — mirrors HOME_NO_CLOSE diagnostic shape.
        self._last_raw = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        self._latency_ms = 0.0
        return list(self._last_raw)

    def validate_action(self, action: Sequence[float]) -> Sequence[float]:
        return validate_ee_delta_gripper(action)

    def export_action(self, action: Sequence[float]) -> list[float]:
        exported = validate_ee_delta_gripper(action)
        self._last_exported = exported
        return list(exported)

    def report_metadata(self) -> dict[str, Any]:
        meta = {
            "contract_version": CONTRACT_VERSION,
            "artifact_type": "policy_adapter_metadata",
            "policy_name": self._identity["policy_name"],
            "policy_version": self._identity["policy_version"],
            "checkpoint_hash": self._identity["checkpoint_hash"],
            "dataset_version": self._identity["dataset_version"],
            "benchmark_version": self._identity["benchmark_version"],
            "observation_schema_version": self._identity["observation_schema_version"],
            "action_schema_version": ACTION_SCHEMA_VERSION,
            "trace_run_id": self._identity["trace_run_id"],
            "inference_latency_ms": self._latency_ms,
            "raw_action": self._last_raw,
            "postprocessed_action": self._last_exported,
            "safety_clipping": {
                "applied": False,
                "axes": ["none"],
                "notes": "fixture_adapter_no_runtime_clip",
            },
            "failure_lane": "none",
            "claims_task_success": False,
        }
        return meta

    def close(self) -> None:
        self._closed = True
        self._loaded = False
