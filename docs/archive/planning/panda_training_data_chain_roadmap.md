# Panda Training Data Chain Roadmap

> **归档**：路线图主要任务已经落地；当前执行入口以 `docs/TRAINING_PIPELINE.md` 和 canonical experiment 为准。

状态：开发路线图。本文档把 `panda_training_lab_spec.md` 拆成可以逐步提交、测试和对外解释的工程任务。

## 0. 当前判断

本仓库可以开始开发，但第一阶段要先做契约归一，而不是直接训练模型。

当前事实：

- 本仓库已有 PyBullet/KUKA iiwa 数据闭环、validator、LeRobot v2.1 export 和评测标签。
- 新主线文档已经把角色改成 Panda 数据、训练、离线评估和 replay 导出实验室。
- 上游 `ros2-arm-teleoperation-suite` 当前 recorder 输出 `observation.state[7]`、`observation.gripper[1]` 和 `action[8]`。
- 本仓库目标 schema 是 `observation.state[8]` 和默认 `ee_delta_gripper action[7]`。
- 下游 `ros2-moveit-pybullet-bridge` 已有 PolicyRunner 基线，但当前 replay 主要是 pkl joint trajectory；Panda JSONL replay 需要后续在 bridge 侧补 consumer 或在本仓库补额外导出器。

第一原则：

```text
raw episode -> declared Panda schema -> inspect -> dataset release -> smoke train
-> offline eval -> neutral replay -> bridge runtime validation
```

本仓库不启动 ROS 2 runtime，不做真机控制，不把 UR3/UR5 混进 Panda schema。

## 1. 分支和提交策略

当前开发分支：

```text
feature/panda-training-data-chain
```

建议保持小提交：

1. `docs: clarify Panda training data-chain roadmap`
2. `feat: add Panda robot schema`
3. `feat: inspect Panda datasets against schema`
4. `feat: add upstream Panda adapter`
5. `feat: add smoke training and offline eval`
6. `feat: export Panda replay jsonl`

每次提交前跑对应小测试，避免把旧 iiwa 链路和新 Panda 链路搅在一个大提交里。

## 2. 目标边界

### 本仓库负责

- Panda robot schema。
- 上游 episode import / adapter。
- Dataset inspection 和 release manifest。
- LeRobot/HuggingFace dataset export。
- CPU-only smoke training。
- Offline evaluation。
- Neutral replay JSONL export。
- 文档、面试口径和验收样例。

### 本仓库不负责

- ROS 2 runtime node。
- MoveIt execution。
- 真机 driver。
- bridge 风险引擎。
- GPU 大训练。
- UR3/UR5 schema 迁移。

## 3. 数据契约

### Canonical Panda Schema

文件：

```text
configs/robot_schemas/panda.yaml
```

第一版必需字段：

| 字段 | 维度 | 说明 |
|------|------|------|
| `observation.state` | `[8]` | 7 个 Panda 关节位置 + 1 个 gripper opening |
| `observation.ee_pose` | `[7]` | `[x, y, z, qx, qy, qz, qw]` |
| `action` | `[7]` | 默认 `ee_delta_gripper`: delta xyz, delta rpy, gripper command |
| `timestamp` | scalar | 同步帧时间 |
| `frame_index` | scalar | episode 内帧号 |
| `episode_index` | scalar | episode id |
| `task` | string | 任务标签或语言指令 |

可选字段：

- `observation.object_pose[7]`
- `observation.ft[6]`
- `observation.images.scene`
- `observation.images.wrist`
- `observation.images.tactile_left`
- `observation.images.tactile_right`

### 上游适配规则

上游当前帧通常是：

```text
observation.state[7]
observation.gripper[1]
action[8] = target pose xyzw + gripper
```

本仓库 adapter 要明确做两件事：

1. `observation.state[8] = concat(observation.state[7], observation.gripper[1])`
2. 对 action 标记真实类型：
   - 若是 pose + gripper，标为 `ee_pose_gripper`。
   - 若要训练 `ee_delta_gripper`，必须由相邻帧或记录的 command 计算 delta。

禁止把 `action[8]` 静默截断成 `action[7]`。

### 下游 replay 规则

本仓库第一版导出：

```text
training/reports/panda_act_smoke/predicted_actions.jsonl
```

每行：

```json
{"timestamp": 0.033, "robot": "panda", "action_type": "ee_delta_gripper", "action": [0.001, 0.0, -0.002, 0.0, 0.0, 0.01, 0.0]}
```

bridge 侧执行、限幅、碰撞检查、分布偏移和风险闭环都归 downstream。

## 4. 开发阶段

### Phase 0：仓库整理和契约冻结

状态：已落地。

目标：让开发不再漂在文档里。

任务：

- 建立 `feature/panda-training-data-chain` 分支。
- 新增 `configs/robot_schemas/panda.yaml`。
- 新增本路线图。
- 在 `docs/README.md` 和 README 导航中接入路线图。
- 更新 `.gitignore`，避免本地 dataset、export 和 training report 产物误入提交。
- 保留旧 KUKA/iiwa 文档为 legacy，不在本阶段删除。

验收：

- `python3 -m py_compile` 不需要覆盖文档。
- `python3 -c "import yaml; yaml.safe_load(open('configs/robot_schemas/panda.yaml', encoding='utf-8'))"` 通过。
- 旧 validator/joint-name 测试仍通过。

### Phase 1：Dataset inspection 最小闭环

状态：已落地第一版，支持 `frames.jsonl`、`frames.npz` 和可选 HuggingFace `datasets.load_from_disk()`。

目标：能对 mock Panda dataset 和上游导出的 HuggingFace dataset 给出 PASS/FAIL。

新增结构：

```text
training/
├── README_TRAINING.md
├── configs/
│   ├── train_act_smoke.yaml
│   └── evaluate_smoke.yaml
├── scripts/
│   ├── inspect_dataset.py
│   └── make_mock_panda_dataset.py
├── reports/.gitkeep
└── policies/__init__.py
```

任务：

- 写 `inspect_dataset.py`，支持 schema 参数。
- 支持两种输入：
  - HuggingFace `datasets.load_from_disk()` 目录。
  - 轻量 JSONL/NPZ mock 目录。
- 检查 required keys、维度、dtype、frame count、episode count。
- optional modalities 缺失只 warning，不 fail。
- 输出 text report 和可选 JSON report。

验收命令：

```bash
python3 training/scripts/make_mock_panda_dataset.py --output /tmp/panda_mock_dataset
python3 training/scripts/inspect_dataset.py \
  --dataset /tmp/panda_mock_dataset \
  --schema configs/robot_schemas/panda.yaml
```

验收标准：

- mock dataset PASS。
- 故意删掉 `observation.state` 后 FAIL。
- optional image 缺失只 warning。

### Phase 2：上游 Panda adapter

状态：已落地第一版，支持 `frames.jsonl`、`frames.npz` 和可选 HuggingFace dataset 输入。

目标：把 `ros2-arm-teleoperation-suite` 当前 M6 recorder 数据转成 canonical Panda schema。

新增建议：

```text
training/scripts/adapt_upstream_panda_dataset.py
training/adapters/
├── __init__.py
└── upstream_m6.py
```

任务：

- 读取上游 episode `train/` dataset。
- 合并 `observation.state[7]` 和 `observation.gripper[1]`。
- 保留 `observation.ee_pose`、`observation.ft`、RGB/tactile/depth 字段。
- 对 `action[8]` 标记为 `ee_pose_gripper`。
- 若用户要求 `--derive-ee-delta-action`，从连续 pose 估算 `ee_delta_gripper[7]`。
- 生成 `manifest.json`，记录 source repo、source path、schema id、action type、filter flags。

验收：

```bash
python3 training/scripts/adapt_upstream_panda_dataset.py \
  --input /path/to/upstream/episode_000000/train \
  --output data/exports/panda_demo \
  --schema configs/robot_schemas/panda.yaml

python training/scripts/inspect_dataset.py \
  --dataset data/exports/panda_demo \
  --schema configs/robot_schemas/panda.yaml
```

若要显式派生默认训练 action：

```bash
python3 training/scripts/adapt_upstream_panda_dataset.py \
  --input /path/to/upstream/episode_000000/train \
  --output data/exports/panda_demo_delta \
  --schema configs/robot_schemas/panda.yaml \
  --derive-ee-delta-action
```

默认输出 `action_type=ee_pose_gripper`，只有传入
`--derive-ee-delta-action` 时才输出 `action_type=ee_delta_gripper`。
这能避免把上游 `action[8]` 静默截断成训练用 `action[7]`。

### Phase 3：Dataset release 和 LeRobot export 对齐

状态：已落地第一版，支持从已 inspect PASS 的 `frames.jsonl` / `frames.npz`
数据集生成 release 目录、`manifest.json` 和 `inspection_report.json`。

目标：让训练不直接指向临时 episode 目录，而指向不可变 dataset release。

任务：

- 新增 `data/exports/README.md` 或 docs 说明大数据不入 Git。
- 生成 `manifest.json`：
  - `schema_id`
  - `robot`
  - `action_type`
  - `num_episodes`
  - `num_frames`
  - `source_paths`
  - `created_at`
  - `filter_rules`
- 更新 `scripts/export_to_lerobot.py` 或新增 training export wrapper，让输出声明 schema。
- 明确 legacy PyBullet/KUKA export 与 Panda export 分开。

验收：

- release manifest 可被 inspect/training 读取。
- 混入 KUKA `robot=kuka_iiwa` 时 fail-fast。

验收命令：

```bash
python3 training/scripts/prepare_dataset_release.py \
  --input data/exports/panda_demo_delta \
  --output data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --release-id panda_demo_delta_v0
```

Release 目录包含：

```text
frames.jsonl 或 frames.npz
manifest.json
inspection_report.json
```

`manifest.json` 是后续 smoke training / offline evaluation / replay export 的入口。

### Phase 4：CPU-only smoke training

状态：已落地第一版，使用 NumPy 线性 baseline，保存 `checkpoint.npz`、
`metrics.json`、`normalization.json` 和 `config_resolved.yaml`。

目标：不追求模型质量，先证明训练接口通。

新增：

```text
training/policies/
├── __init__.py
├── base_policy.py
└── mlp_policy.py
training/scripts/train_act_smoke.py
training/configs/train_act_smoke.yaml
```

建议第一版：

- 用 NumPy 实现线性/小 MLP baseline，或在有 torch 时可选 torch。
- 默认 CPU。
- 输入 `observation.state[8]`，输出 `action[7]`。
- 保存 normalization stats。
- 保存 checkpoint、metrics、resolved config。

验收：

```bash
python3 training/scripts/train_act_smoke.py \
  --dataset data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke
```

产物：

```text
training/reports/panda_act_smoke/
├── checkpoint.npz
├── config_resolved.yaml
├── metrics.json
└── normalization.json
```

### Phase 5：Offline evaluation

状态：已落地第一版，输出 `eval.json`，包含整体误差、per-dim 误差、
smoothness proxy 和可选 success label summary。

目标：给出离线指标，不假装已经完成真实 rollout。

新增：

```text
training/scripts/evaluate_policy.py
training/configs/evaluate_smoke.yaml
```

指标：

- mean absolute action error。
- RMSE action error。
- smoothness proxy。
- per-dim action error。
- success label summary，如果 dataset 有标签。

验收：

```bash
python3 training/scripts/evaluate_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/eval.json
```

### Phase 6：Replay JSONL export

状态：已完成首版。

目标：向 bridge 交付中立动作流。

新增：

```text
training/scripts/replay_policy.py
```

任务：

- 加载 checkpoint 和 dataset seed frames。
- 输出 `predicted_actions.jsonl`。
- 每行包含 `timestamp`、`robot`、`schema_id`、`action_type`、`action`。
- 同时包含 `episode_index`、`frame_index`、`task`、`release_id`，方便下游对齐 episode 轨迹。
- 校验 action dim 与 schema 一致。
- 校验 checkpoint / dataset / schema 的 `schema_id` 与 `action_type` 一致。

验收：

```bash
python3 training/scripts/replay_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --checkpoint training/reports/panda_act_smoke/checkpoint.npz \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/predicted_actions.jsonl
```

### Phase 7：Downstream bridge handoff

状态：已完成本仓库交付打包；下游 JSONL consumer 仍由 bridge 仓库后续实现。

目标：本仓库完成交付，bridge 侧再消费。

本仓库只需要提供：

- `predicted_actions.jsonl`
- `handoff_manifest.json`
- `dataset_manifest.json`
- `replay_check.json`
- `schema_id`
- action range / dim 检查结果

bridge 侧后续二选一：

- 新增 `JsonlActionReplayPolicy` 消费 `ee_delta_gripper`。
- 本仓库额外导出 bridge 当前可吃的 pkl joint replay，作为过渡。

本仓库不在这一阶段启动 ROS 2。

验收：

```bash
python3 training/scripts/prepare_bridge_handoff.py \
  --dataset data/exports/panda_demo_delta_release \
  --replay training/reports/panda_act_smoke/predicted_actions.jsonl \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_act_smoke/bridge_handoff \
  --handoff-id panda_demo_delta_bridge_v0
```

输出目录：

```text
bridge_handoff/
├── predicted_actions.jsonl
├── dataset_manifest.json
├── dataset_inspection_report.json
├── replay_check.json
└── handoff_manifest.json
```

## 5. 推荐任务顺序

第一天：

- 合并 Phase 0。
- 写 `inspect_dataset.py` 和 mock dataset。
- 让 mock dataset inspect PASS/FAIL 都有测试。

第二天：

- 写 upstream adapter。
- 拿一个上游 episode 目录跑 inspect。
- 出 `data/exports/panda_demo/manifest.json`。

第三天：

- 写 smoke train。
- 写 evaluate。
- 输出 metrics/eval。

第四天：

- 写 replay JSONL。
- 补 replay schema test。
- 更新 bridge handoff 文档。
- 写 bridge handoff bundle 脚本。

## 6. 测试矩阵

| 层级 | 命令 | 目的 |
|------|------|------|
| schema | `python3 -c "import yaml; yaml.safe_load(open('configs/robot_schemas/panda.yaml'))"` | YAML 可解析 |
| existing unit | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests/test_validate_dataset.py tests/test_joint_names.py -q` | 旧数据链路不被破坏 |
| inspect unit | `pytest tests/test_panda_dataset_inspection.py -q` | 新 inspector 行为稳定 |
| training smoke | `python3 training/scripts/train_act_smoke.py ...` | CPU 训练能跑 |
| eval smoke | `python3 training/scripts/evaluate_policy.py ...` | 离线评估能产 JSON |
| replay smoke | `python3 training/scripts/replay_policy.py ...` | JSONL action dim 正确 |
| bridge handoff | `python3 training/scripts/prepare_bridge_handoff.py ...` | handoff bundle 和 replay check 可生成 |

## 7. 风险和处理

| 风险 | 表现 | 处理 |
|------|------|------|
| 上游 action 语义不等于 `ee_delta_gripper` | action dim 是 8，且是 pose + gripper | adapter 中显式标记 `ee_pose_gripper`，禁止静默截断 |
| 旧 KUKA dataset 混入 Panda 训练 | robot/schema 不一致 | inspect 阶段 fail-fast |
| optional 多模态缺失导致无法起步 | 小样本没有 wrist/tactile | optional 只 warning，先训 state-only baseline |
| bridge 当前不消费 JSONL | replay 不能直接跑 | 本仓库先稳定 JSONL；bridge 侧再加 consumer 或 pkl 过渡 |
| 大数据误入 Git | dataset 目录变脏 | manifest 入 Git，大数据路径和 release 说明入 docs |

## 8. 面试表达

完成 Phase 6 后可以这样讲：

> 我把运行时、数据实验室和 Sim2Real 验证拆开：上游 ROS 2/MuJoCo 负责采集 Panda episode，本仓库把原始数据适配成明确的 Panda observation/action schema，并完成 inspection、dataset release、smoke training、offline evaluation 和 replay JSONL 导出。下游 MoveIt/PyBullet bridge 只消费声明过 schema 的动作流，负责执行验证、分布偏移监控和风险闭环。这样训练和机器人运行时互不污染，后续接 UR3/UR5 也只需要新增 schema 和 adapter。
