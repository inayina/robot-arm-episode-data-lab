# Dataset Exports

This directory is for local Panda dataset releases produced by training scripts.

Generated release contents, such as `frames.jsonl`, `frames.npz`, `manifest.json`,
and `inspection_report.json`, should stay out of Git. Commit only documentation or
small fixtures that are intentionally added for tests.

Typical flow:

```bash
python3 training/scripts/make_mock_panda_dataset.py --output /tmp/panda_mock_dataset
python3 training/scripts/prepare_dataset_release.py \
  --input /tmp/panda_mock_dataset \
  --output data/exports/panda_mock_v0 \
  --schema configs/robot_schemas/panda.yaml \
  --release-id panda_mock_v0
```
