# 数据集 v1

面向作品集与 LeRobot 导出的 PyBullet pick-lift episode 批量采集结果。

## 概览

- 任务：`pick_and_lift`
- Episode 数量：20
- 每 episode 步数：80
- 成功次数：20
- 成功率：100.0%
- 基础随机种子：42
- 生成时间：2026-06-18T06:29:59.752998+00:00

## 目录结构

每个子目录符合 `docs/data_schema.md` 约定：

```text
episode_000001/
├── images/
├── states.npy
├── actions.npy
├── ee_poses.npy
├── object_poses.npy
└── metadata.json
```

## metadata 扩展字段

- `success`、`failure_reason`、`object_z_lift`
- `language_instruction`（pick-lift 任务）
- `gripper_states`、`task_phases`

## Episode 索引

| Episode | 种子 | 成功 | 物体 Z 抬升 (m) |
| --- | ---: | --- | ---: |
| `episode_000001` | 42 | True | 0.1177 |
| `episode_000002` | 43 | True | 0.1179 |
| `episode_000003` | 44 | True | 0.1179 |
| `episode_000004` | 45 | True | 0.1178 |
| `episode_000005` | 46 | True | 0.1178 |
| `episode_000006` | 47 | True | 0.1178 |
| `episode_000007` | 48 | True | 0.1179 |
| `episode_000008` | 49 | True | 0.1179 |
| `episode_000009` | 50 | True | 0.1178 |
| `episode_000010` | 51 | True | 0.1178 |
| `episode_000011` | 52 | True | 0.1178 |
| `episode_000012` | 53 | True | 0.1180 |
| `episode_000013` | 54 | True | 0.1179 |
| `episode_000014` | 55 | True | 0.1178 |
| `episode_000015` | 56 | True | 0.1178 |
| `episode_000016` | 57 | True | 0.1178 |
| `episode_000017` | 58 | True | 0.1179 |
| `episode_000018` | 59 | True | 0.1178 |
| `episode_000019` | 60 | True | 0.1180 |
| `episode_000020` | 61 | True | 0.1179 |

## 常用命令

```bash
python scripts/validate_dataset.py dataset/v1
python scripts/export_lerobot_style.py dataset/v1 --output dataset/v1/lerobot_export
```
