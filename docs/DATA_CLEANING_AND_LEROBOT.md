# Data Cleaning, Curation, and LeRobot Export

状态：P0/P1 数据工程说明文档。本文档说明本仓库如何把上游 raw episode 整理成可检查、可发布、可训练、可导出的数据，而不是只“跑一个 demo”。

## 1. 目标

中游数据链路要解决四件事：

1. 把上游 MuJoCo / ROS 2 recorder 或本地 legacy PyBullet episode 转成明确的数据契约。
2. 通过 schema inspection 尽早发现字段缺失、维度不一致、action 语义不清等问题。
3. 把通过检查的数据固定成 dataset release，避免训练直接依赖临时目录。
4. 根据用途导出不同格式：Panda training release、LeRobot v2.1 layout、HuggingFace datasets format、bridge replay handoff。

## 2. 数据整理链路

```text
raw episode
-> adapter / field mapping
-> schema inspection
-> dataset release
-> training / evaluation
-> replay JSONL / bridge handoff
-> optional LeRobot / HF dataset export
```

当前主线是 Panda schema：

```text
configs/robot_schemas/panda.yaml
```

legacy PyBullet / KUKA 数据仍可保留为历史样例，但不能直接混入 Panda training release。

## 3. 清洗与校验内容

| 类别 | 检查项 | 处理方式 |
|---|---|---|
| Required fields | `observation.state`, `observation.ee_pose`, `action`, `timestamp`, `frame_index`, `episode_index`, `task` | 缺失即 FAIL |
| Shape | state/action/pose 是否符合 schema | 不一致即 FAIL |
| Action semantics | `action_type` 是否声明清楚 | 不允许静默截断 |
| Optional modalities | images / tactile / ft / object pose | 缺失记录 WARN |
| Episode indexing | `episode_index`, `frame_index` 是否可统计 | 不可解析即 FAIL |
| Metadata | `schema_id`, `robot`, `release_id`, `source`, `upstream_gate` | release manifest 中保留 |
| Safety/filter policy | e-stop、drive fault、异常 episode | release manifest 中记录过滤规则 |

### 3.1 上游 / 中游清洗边界

| 层级 | 负责 | 不负责 |
|---|---|---|
| 上游 `batch_generator` + grasp monitor | 物理抓取/抬升/放置判定；失败 episode `discard`；accepted episode 写入 `success=true` | schema 适配、training split、release manifest |
| 上游 `lerobot_recorder` | 在 `episode_*/meta.json` 写入 `upstream_gate`（如 `batch_generator` / `teleop`） | 训练侧过滤规则 |
| 中游 adapter / inspection | schema/shape/action 语义校验；`success` / `safety_estop` / `drive_fault` 训练 split 过滤 | 重新做 lift_delta / object_pose 物理判定 |

当 manifest 中 `filter_scope=training_split_only` 且 `upstream_gate=batch_generator` 时，中游 inspection 只确认字段与训练 split 标签，不再重复物理语义检查。

典型 fail-fast 场景：

- 上游 `action[8]` 是 `ee_pose_gripper`，却被当成 `ee_delta_gripper[7]` 训练。
- `observation.state[7]` 没有合并 gripper opening，直接进入 Panda schema。
- dataset manifest 写 `robot=kuka_iiwa`，却尝试进入 Panda training release。
- inspection 未 PASS 就运行 training 或 handoff。

## 4. Release 结构

训练输入应固定为 release 目录：

```text
panda_demo_delta_release/
├── frames.jsonl
├── inspection_report.json
└── manifest.json
```

`manifest.json` 记录：

- `dataset_format`
- `release_id`
- `schema_id`
- `schema_version`
- `robot`
- `action_type`
- `num_episodes`
- `num_frames`
- `source`
- `filter_rules`
- `training_contract`

Release 的意义是把“临时采集目录”变成“可追踪训练输入”。训练脚本、评估脚本和 handoff 脚本都应指向 release，而不是随手指向 raw episode。

## 5. LeRobot / HF Export 边界

本仓库有两类 LeRobot 相关导出，语义不同：

| 脚本 | 输出 | 适用场景 | 当前定位 |
|---|---|---|---|
| `scripts/export_lerobot_style.py` | LeRobot v2.1 style layout: parquet + mp4 + meta JSON | legacy PyBullet/KUKA episode 展示、上传或格式对齐 | legacy export evidence |
| `scripts/export_to_lerobot.py` | HuggingFace `datasets.save_to_disk()` Arrow layout | 给 recorder / ACT / Diffusion-style pipeline 做数据接口 | optional export path |
| `training/scripts/replay_policy.py` | `predicted_actions.jsonl` | 下游 bridge replay validation | 当前 Panda handoff 主线 |

不要混淆：

- LeRobot export 是数据格式对齐，不等于已经训练了 LeRobot policy。
- HF dataset export 是训练框架输入格式，不等于已经完成 ACT / Diffusion Policy。
- Bridge handoff 是下游执行验证输入，不是实机执行许可。

## 6. 推荐展示方式

面试时可以这样讲：

> 我把数据整理分成 raw import、schema inspection、dataset release 和 export/handoff 四步。inspection 负责 fail-fast，release 负责可追踪训练输入，LeRobot/HF export 负责格式兼容，bridge handoff 负责下游执行验证接口。这样数据、训练和机器人 runtime 不混在一起。

适合展示的证据：

- `inspection_report.json`
- `manifest.json`
- `metrics.json`
- `eval.json`
- `predicted_actions.jsonl`
- `handoff_manifest.json`
- LeRobot `meta/info.json` 或 parquet schema 截图

不建议夸大的内容：

- 不说“数据清洗后已经可直接上真机”。
- 不说“LeRobot export 就等于训练了 LeRobot 模型”。
- 不说“mock dataset 的指标代表真实抓取效果”。
