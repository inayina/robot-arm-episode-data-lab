"""CPU-only policy onboarding preflight for solution-architecture PoCs.

The validator checks identity, integrity, observation/action semantics, runtime
limits, adapter ownership, and non-claims before a bundle may proceed to an
offline or interface evaluation. It does not load a model or authorize runtime,
simulation, training, or hardware execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import yaml


ALLOWED_STATUSES = ("not_run", "pass", "hold", "no_go", "invalid")
SUPPORTED_ACTION_DIMENSIONS = {
    "panda_absolute_eef_gripper_v0": 8,
    "panda_ee_delta_gripper_v0": 7,
}
DOCUMENTS = {
    "policy_identity": "policy_identity.yaml",
    "observation_schema": "observation_schema.yaml",
    "action_schema": "action_schema.yaml",
    "runtime_contract": "runtime_contract.yaml",
    "artifact_manifest": "artifact_manifest.json",
    "adapter_mapping": "adapter_mapping.yaml",
    "sample_action": "sample_action.json",
    "commands": "commands.jsonl",
}


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: str
    reason_code: str
    evidence: tuple[str, ...]
    errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "reason_code": self.reason_code,
            "evidence": list(self.evidence),
            "errors": list(self.errors),
        }


def _load_document(path: Path) -> Any:
    if path.suffix == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _set_path(document: Any, path: list[str | int], value: Any) -> None:
    target = document
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def load_bundle(bundle_dir: Path, case_path: Path | None = None) -> dict[str, Any]:
    """Load a bundle and optionally apply an explicit in-memory fault case."""

    documents: dict[str, Any] = {}
    for name, relative in DOCUMENTS.items():
        path = bundle_dir / relative
        if not path.is_file():
            raise ValueError(f"required onboarding document missing: {relative}")
        documents[name] = _load_document(path)

    if case_path is not None:
        case = json.loads(case_path.read_text(encoding="utf-8"))
        for mutation in case.get("mutations", []):
            document_name = mutation["document"]
            if document_name not in documents:
                raise ValueError(f"case mutates unknown document: {document_name}")
            _set_path(documents[document_name], mutation["path"], mutation["value"])
        documents["_case"] = case
    else:
        documents["_case"] = {"case_id": "direct_bundle", "expected_status": None}
    return documents


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(child) for child in value.values())
    if isinstance(value, list):
        return all(_finite(child) for child in value)
    return True


def _false_claim_errors(value: Any, path: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if (key.startswith("claims_") or path.endswith(".claims")) and child is not False:
                errors.append(f"{child_path} must be false")
            errors.extend(_false_claim_errors(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(_false_claim_errors(child, f"{path}[{index}]"))
    return errors


def _result(
    gate: str,
    errors: Iterable[str],
    evidence: Iterable[str],
    reason_code: str = "none",
    failure_status: str = "invalid",
) -> GateResult:
    error_tuple = tuple(errors)
    return GateResult(
        gate=gate,
        status=failure_status if error_tuple else "pass",
        reason_code=reason_code if error_tuple else "none",
        evidence=tuple(evidence),
        errors=error_tuple,
    )


def _identity_gate(documents: dict[str, Any]) -> GateResult:
    identity = documents["policy_identity"]
    manifest = documents["artifact_manifest"]
    errors = []
    policy = identity.get("policy", {})
    required = ("policy_id", "family", "version", "checkpoint_sha256", "owner")
    errors.extend(f"policy.{key} is required" for key in required if not policy.get(key))
    artifacts = manifest.get("artifacts", [])
    checkpoint = next((item for item in artifacts if item.get("role") == "policy_checkpoint"), None)
    if checkpoint is None:
        errors.append("manifest policy_checkpoint is required")
    elif checkpoint.get("sha256") != policy.get("checkpoint_sha256"):
        errors.append("policy checkpoint SHA does not match manifest")
    return _result("G0_identity", errors, (DOCUMENTS["policy_identity"], DOCUMENTS["artifact_manifest"]), "contract_mismatch")


def _integrity_gate(bundle_dir: Path, documents: dict[str, Any]) -> GateResult:
    errors = []
    evidence = [DOCUMENTS["artifact_manifest"]]
    for item in documents["artifact_manifest"].get("artifacts", []):
        relative = item.get("path")
        if not isinstance(relative, str) or not relative:
            errors.append("artifact path is required")
            continue
        candidate = (bundle_dir / relative).resolve()
        try:
            candidate.relative_to(bundle_dir.resolve())
        except ValueError:
            errors.append(f"artifact escapes bundle: {relative}")
            continue
        if not candidate.is_file():
            errors.append(f"artifact missing: {relative}")
            continue
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest != item.get("sha256"):
            errors.append(f"SHA256 mismatch: {relative}")
        if item.get("bytes") != candidate.stat().st_size:
            errors.append(f"byte size mismatch: {relative}")
        evidence.append(relative)
    return _result("G1_integrity", errors, evidence, "contract_mismatch")


def _observation_gate(documents: dict[str, Any]) -> GateResult:
    schema = documents["observation_schema"]
    errors = []
    if not schema.get("schema_id"):
        errors.append("observation schema_id is required")
    features = schema.get("features")
    if not isinstance(features, list) or not features:
        errors.append("at least one observation feature is required")
    else:
        keys = [item.get("key") for item in features]
        if None in keys or len(keys) != len(set(keys)):
            errors.append("observation feature keys must be present and unique")
        for feature in features:
            shape = feature.get("shape")
            if not isinstance(shape, list) or not shape or any(not isinstance(dim, int) or dim <= 0 for dim in shape):
                errors.append(f"invalid shape for observation feature {feature.get('key')}")
    return _result("G2_observation", errors, (DOCUMENTS["observation_schema"],), "observation_invalid")


def _action_gate(documents: dict[str, Any]) -> GateResult:
    schema = documents["action_schema"]
    sample = documents["sample_action"]
    errors = []
    schema_id = schema.get("schema_id")
    dimension = schema.get("action", {}).get("dimension")
    expected = SUPPORTED_ACTION_DIMENSIONS.get(schema_id)
    if expected is None:
        errors.append(f"unsupported action schema: {schema_id}")
    elif dimension != expected:
        errors.append(f"schema {schema_id} requires dimension {expected}, got {dimension}")
    action = sample.get("action")
    if not isinstance(action, list) or len(action) != dimension:
        errors.append(f"sample action length must equal declared dimension {dimension}")
    if not _finite(action):
        errors.append("sample action contains NaN or Inf")
    return _result("G3_action", errors, (DOCUMENTS["action_schema"], DOCUMENTS["sample_action"]), "action_dimension_invalid")


def _runtime_gate(documents: dict[str, Any]) -> GateResult:
    runtime = documents["runtime_contract"]
    identity = documents["policy_identity"]
    observation = documents["observation_schema"]
    action = documents["action_schema"]
    errors = []
    if runtime.get("policy_id") != identity.get("policy", {}).get("policy_id"):
        errors.append("runtime policy_id does not match identity")
    if runtime.get("observation_schema_id") != observation.get("schema_id"):
        errors.append("runtime observation_schema_id does not match")
    if runtime.get("action_schema_id") != action.get("schema_id"):
        errors.append("runtime action_schema_id does not match")
    timing = runtime.get("timing", {})
    for key in ("command_ttl_ms", "inference_deadline_ms"):
        if not isinstance(timing.get(key), (int, float)) or timing[key] <= 0:
            errors.append(f"runtime timing.{key} must be positive")
    sequences = [row.get("command_sequence") for row in documents["commands"]]
    if any(not isinstance(value, int) for value in sequences):
        errors.append("command sequences must be integers")
    elif any(current <= previous for previous, current in zip(sequences, sequences[1:])):
        errors.append("command sequence must strictly increase")
    return _result(
        "G4_runtime",
        errors,
        (DOCUMENTS["runtime_contract"], DOCUMENTS["commands"]),
        "command_sequence_regression" if errors and any("sequence" in error for error in errors) else "contract_mismatch",
        failure_status="hold" if errors and all("sequence" in error for error in errors) else "invalid",
    )


def _adapter_gate(documents: dict[str, Any]) -> GateResult:
    adapter = documents["adapter_mapping"]
    observation_id = documents["observation_schema"].get("schema_id")
    action_id = documents["action_schema"].get("schema_id")
    errors = []
    if not adapter.get("adapter_id") or not adapter.get("owner"):
        errors.append("adapter id and owner are required")
    source = adapter.get("source_contract", {})
    if source.get("observation_schema_id") != observation_id:
        errors.append("adapter source observation schema does not match")
    if source.get("action_schema_id") != action_id:
        errors.append("adapter source action schema does not match")
    return _result("G5_adapter", errors, (DOCUMENTS["adapter_mapping"],), "contract_mismatch")


def _claims_gate(documents: dict[str, Any]) -> GateResult:
    errors = []
    for name, document in documents.items():
        if name.startswith("_"):
            continue
        errors.extend(f"{name}: {error}" for error in _false_claim_errors(document))
    required_false = (
        ("policy_identity", documents["policy_identity"].get("claims", {}), ("task_success", "sim2real", "online_autonomous_grasp")),
        ("runtime_contract", documents["runtime_contract"].get("claims", {}), ("task_success", "sim2real", "online_autonomous_grasp")),
        ("artifact_manifest", documents["artifact_manifest"], ("claims_task_success", "claims_sim2real", "claims_real_robot")),
    )
    for name, claims, keys in required_false:
        for key in keys:
            if claims.get(key) is not False:
                errors.append(f"{name}.{key} must explicitly be false")
    return _result("G6_claims", errors, tuple(DOCUMENTS.values()), "contract_mismatch")


def _evidence_gate(documents: dict[str, Any]) -> GateResult:
    errors = []
    if not documents["artifact_manifest"].get("bundle_id"):
        errors.append("bundle_id is required")
    if not documents["policy_identity"].get("policy", {}).get("owner"):
        errors.append("policy owner is required")
    return _result("G7_evidence", errors, (DOCUMENTS["artifact_manifest"], DOCUMENTS["policy_identity"]), "insufficient_samples", "hold")


def validate_bundle(bundle_dir: Path, case_path: Path | None = None) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    documents = load_bundle(bundle_dir, case_path)
    gates = (
        _identity_gate(documents),
        _integrity_gate(bundle_dir, documents),
        _observation_gate(documents),
        _action_gate(documents),
        _runtime_gate(documents),
        _adapter_gate(documents),
        _claims_gate(documents),
        _evidence_gate(documents),
    )
    statuses = {gate.status for gate in gates}
    overall = "invalid" if "invalid" in statuses else "hold" if "hold" in statuses else "pass"
    case = documents["_case"]
    return {
        "template_version": 1,
        "report_version": "solution_policy_preflight_v1",
        "bundle_id": documents["artifact_manifest"].get("bundle_id"),
        "case_id": case.get("case_id"),
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_bundle": str(bundle_dir),
        "case_source": str(case_path.resolve()) if case_path is not None else None,
        "status": overall,
        "allowed_statuses": list(ALLOWED_STATUSES),
        "next_allowed_stage": "offline_or_interface_evaluation" if overall == "pass" else "remediation_only",
        "checks": [gate.as_dict() for gate in gates],
        "claims_task_success": False,
        "claims_sim2real": False,
        "claims_online_autonomous_grasp": False,
        "authorized_simulation": False,
        "authorized_training": False,
        "authorized_real_robot": False,
    }
