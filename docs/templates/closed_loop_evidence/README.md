# Closed Loop Evidence Bundle

Filled automatically by `scripts/run_three_repo_closed_loop.sh` and archived to
`evidence/` when `CLOSED_LOOP_ARCHIVE_EVIDENCE=1` (default).

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
| `meta/run_summary.json` | gate status summary |

## Reproduce

```bash
# G0 daily collection (upstream persistent archive)
cd /home/ina/dev/ros2-arm-teleoperation-suite
./scripts/collect_daily_episodes.sh

# G1 + G2 + G3 (midstream; defaults to upstream data/episodes/)
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab
WITH_DOWNSTREAM=1 CLOSED_LOOP_ARCHIVE_EVIDENCE=1 \
  ./scripts/run_three_repo_closed_loop.sh
```
