"""M5 policy trace bundle schema, hash, and correlation contract tests."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'evaluation/examples/policy_trace_bundle_fixture'


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_no_task_claim(value) -> None:
    if isinstance(value, dict):
        assert value.get('claims_task_success', False) is False
        for child in value.values():
            _assert_no_task_claim(child)
    elif isinstance(value, list):
        for child in value:
            _assert_no_task_claim(child)


def test_manifest_schema_and_frozen_hashes_match() -> None:
    schema = _json(
        ROOT / 'evaluation/schemas/policy_trace_bundle.schema.json'
    )
    manifest = _json(BUNDLE / 'manifest.json')
    Draft202012Validator(schema).validate(manifest)

    lock = _json(
        ROOT / 'configs/policy_runtime/panda_policy_trace_bundle_v1.lock.json'
    )
    for relative, expected in lock['artifact_sha256'].items():
        assert _sha256(ROOT / relative) == expected


def test_fixture_files_are_hash_bound_and_trace_consistent() -> None:
    manifest = _json(BUNDLE / 'manifest.json')
    sequences = []
    for record in manifest['files'].values():
        path = BUNDLE / record['path']
        rows = _jsonl(path)
        assert _sha256(path) == record['sha256']
        assert len(rows) == record['record_count']
        for row in rows:
            assert row['trace_run_id'] == manifest['trace_run_id']
            assert row['episode_id'] == manifest['episode_id']
            _assert_no_task_claim(row)
        sequences.extend(
            row['command_sequence']
            for row in rows
            if row.get('artifact_type') == 'policy_command'
        )
    assert sequences == sorted(set(sequences))
    assert manifest['sequence_bounds'] == {
        'first': sequences[0], 'last': sequences[-1]
    }


@pytest.mark.parametrize('field,value', [
    ('is_closed_loop', True),
    ('claims_task_success', True),
])
def test_manifest_rejects_expanded_claims(field: str, value: bool) -> None:
    schema = _json(
        ROOT / 'evaluation/schemas/policy_trace_bundle.schema.json'
    )
    manifest = deepcopy(_json(BUNDLE / 'manifest.json'))
    manifest[field] = value
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(manifest)


def test_command_fixture_remains_valid_under_m0_runtime_schema() -> None:
    schema = _json(
        ROOT / 'evaluation/schemas/policy_runtime_contract.schema.json'
    )
    command = _jsonl(BUNDLE / 'policy_commands.jsonl')[0]
    report = _jsonl(BUNDLE / 'execution_reports.jsonl')[0]
    Draft202012Validator(schema).validate(command)
    Draft202012Validator(schema).validate(report)
