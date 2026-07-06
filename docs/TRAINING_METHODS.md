# Training Methods

状态：P0/P1 训练方式说明文档。本文档把当前已实现、可选运行、未来可扩展的训练方式分开，避免把最小 baseline 夸大成复杂策略训练。

## 1. 总体分层

| 层级 | 方法 | 状态 | 目的 | 是否作为当前主线 |
|---|---|---|---|---|
| L0 | Dataset inspection only | 已实现 | 不训练，只验证 schema 和 release 可用 | 是 |
| L1 | Linear smoke policy | 已实现 | 最小 `state -> action` 闭环，产出 checkpoint / metrics / replay | 是 |
| L2 | PyTorch MLP BC | 已实现脚本，依赖 PyTorch | 展示神经网络 BC 训练入口 | 可选 |
| L3 | LeRobot / ACT / Diffusion-style training | 未在本仓库实现 | 未来可对接外部训练框架 | 否 |
| L4 | Runtime rollout / real robot training | 未实现 | 下游或真实机器人验证 | 否 |

当前作品集主线是 L0 + L1。L2 可以作为“我知道如何扩展到神经网络 BC”的补充，但不要把它包装成成熟策略。

## 2. L0: Dataset Inspection Only

用途：

- 验证 raw/adapted dataset 是否符合 `configs/robot_schemas/panda.yaml`。
- 检查 required fields、shape、action type、metadata。
- 把 optional modality 缺失记录成 warning。

命令：

```bash
python3 training/scripts/inspect_dataset.py \
  --dataset /tmp/panda_mock_dataset \
  --schema configs/robot_schemas/panda.yaml
```

适合展示：

- Required fields PASS。
- Optional images/tactile missing WARN。
- `Status: PASS` / `Status: FAIL`。

## 3. L1: Linear Smoke Policy

用途：

- 证明 dataset release 可以进入训练。
- 证明 checkpoint、metrics、normalization、eval、replay 可以串起来。
- 快速暴露 state/action 维度或 action_type 问题。

Policy：

```text
linear_smoke: observation.state -> action
```

实现：

```text
training/policies/linear_policy.py
training/scripts/train_act_smoke.py
```

输出：

```text
training/reports/panda_act_smoke/
├── checkpoint.npz
├── config_resolved.yaml
├── metrics.json
└── normalization.json
```

适合写进作品集的指标：

- `train_loss`
- `val_loss`
- `train_mae`
- `val_mae`
- `state_dim`
- `action_dim`
- `num_frames`
- `action_type`

边界：

- 可以说“最小训练闭环已跑通”。
- 不要说“训练出了可用抓取策略”。
- 不要说“可以直接上真机”。

## 4. L2: PyTorch MLP Behavioral Cloning

用途：

- 作为神经网络 BC 入口。
- 展示从线性 baseline 扩展到 MLP 的工程路径。
- 需要 PyTorch 环境，不作为最小 P0 demo 必须项。

命令：

```bash
python3 training/scripts/train_mlp_policy.py \
  --dataset data/exports/panda_demo_delta_release \
  --schema configs/robot_schemas/panda.yaml \
  --output training/reports/panda_mlp_bc \
  --epochs 100
```

输出：

```text
training/reports/panda_mlp_bc/
├── mlp_policy.pth
└── mlp_metrics.json
```

当前注意事项：

- 如果没有 PyTorch，脚本会提示安装 PyTorch 并退出。
- 当前 MLP BC 不接管 README P0 demo。
- 需要更真实的数据量和下游 rollout 才能评价策略质量。

面试表达：

> 我保留了 MLP BC 入口，但当前不把它作为主线，因为项目核心是数据闭环和接口契约。模型复杂度应该在数据质量、schema 和下游验证稳定后再增加。

## 5. L3: LeRobot / ACT / Diffusion-Style Training

当前状态：

- 本仓库提供数据整理和 export path。
- 不在本仓库内实现 ACT / Diffusion Policy。
- 可以通过 `scripts/export_to_lerobot.py` 导出 HuggingFace datasets layout，作为未来外部训练框架输入。

边界：

```text
export-compatible != trained ACT policy
```

可以说：

- 数据结构预留了 LeRobot/HF dataset 对接路径。
- 当前没有在本仓库内训练 ACT 或 Diffusion Policy。
- 如果后续要做，优先复用 release/manifest/schema，而不是绕过中游数据契约。

## 6. L4: Runtime Rollout / Real Robot Training

当前不做：

- 不在本仓库启动 ROS 2 runtime。
- 不直接控制真实机械臂。
- 不做在线 RL。
- 不把下游 PyBullet replay 结果等价成真实机器人成功率。

下游职责：

- `ros2-moveit-pybullet-bridge` 消费 replay JSONL。
- MoveIt / PyBullet 负责执行验证、接触稳定性和 Sim2Real-readiness risk。
- 真机迁移需要硬件接口、夹爪驱动、传感器、安全层和标定。

## 7. 推荐作品集表述

推荐：

> 当前训练模块分三层：inspection-only、linear smoke baseline、可选 MLP BC。主线是 linear smoke，因为它能快速证明 dataset -> training -> evaluation -> replay handoff 的工程闭环。复杂模型和真实 rollout 不在当前阶段夸大。

避免：

- “我训练了机械臂大模型。”
- “MLP 已经能稳定抓取。”
- “LeRobot export 后就能直接部署。”
- “offline loss 低说明真实机械臂会成功。”
