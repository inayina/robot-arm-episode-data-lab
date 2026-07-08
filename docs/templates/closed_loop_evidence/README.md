# Closed Loop Evidence Bundle

Fill this directory after a successful G0–G3 run. Generated automatically by
`scripts/run_three_repo_closed_loop.sh` under `evidence/` when the midstream
pipeline passes.

## Required files

| Path | Source |
|------|--------|
| `upstream/validate_dataset.json` | `python3 scripts/validate_dataset.py <raw> --json` (upstream repo) |
| `middle/release_manifest.json` | `prepare_dataset_release.py` output |
| `middle/handoff_manifest.json` | `prepare_bridge_handoff.py` output |
| `middle/metrics.json` | `train_act_smoke.py` output |
| `downstream/benchmark_summary.json` | `benchmark_system.py --strategy panda_jsonl_replay` (optional) |
| `meta/three_repo_commits.txt` | git rev-parse in each repo |
| `meta/paths.env` | auto-written by closed-loop script |

## Reproduce

```bash
# G0 upstream
bash /path/to/ros2-arm-teleoperation-suite/scripts/run_batch_preflight_smoke.sh

# G1 midstream (+ optional G2 downstream)
UPSTREAM_RAW=/tmp/batch_out WITH_DOWNSTREAM=1 \
  ./scripts/run_three_repo_closed_loop.sh
```
