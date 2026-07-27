# Legacy KUKA / PyBullet isolation

This tree is **archive runtime**, not the Panda training / handoff mainline.

| Marker | Value |
| --- | --- |
| Directory | `core/`, `agents/` |
| Config | `configs/default.yaml` → `robot: kuka_iiwa` |
| CI job | `.github/workflows/ci.yml` → **`legacy-kuka-pybullet`** |
| Docs | `docs/legacy_pybullet/` |

Do not feed legacy episodes into `prepare_dataset_release.py` or SmolVLA / ACT Panda releases.
