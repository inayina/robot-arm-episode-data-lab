# Troubleshooting

状态：P0 数据链路排障表。本文档聚焦中游最容易破坏可信度的问题：schema、action 语义、release、checkpoint 和 handoff。

## 1. Quick Triage

| 现象 | 优先检查 |
|---|---|
| `inspect_dataset.py` FAIL | required 字段、shape、manifest `action_type` |
| training 拒绝运行 | dataset inspection 是否 PASS，action 是否为 `ee_delta_gripper` |
| replay 输出不可用 | checkpoint 路径、schema_id、action dim |
| bridge handoff FAIL | replay JSONL 字段、dataset manifest、release_id |
| 面试时被问“是不是 Sim2Real” | 回答 Sim-to-Sim / Sim2Real-readiness，不说已完成真机验证 |

## 2. Common Issues

| 问题现象 | 可能原因 | 如何验证 | 修复方式 | 验收标准 |
|---|---|---|---|---|
| `observation.state` shape mismatch | 上游只有 joint state `[7]`，未合并 gripper | 跑 `inspect_dataset.py` 看 observed shape | adapter 合并 `observation.gripper[1]` 到 state | `observation.state` observed `[8]` |
| `action` shape mismatch | 上游 action 是 `ee_pose_gripper[8]`，训练期望 `ee_delta_gripper[7]` | 检查 `manifest.json` 的 `action_type` | 保留为 `ee_pose_gripper`，或显式使用 delta action adapter | manifest action_type 与脚本一致 |
| training 报 action_type 错误 | 未把上游 action 转成默认训练 action | 看错误中的 expected / got | 用 adapter 推导 `ee_delta_gripper`，或不要训练该 release | `train_act_smoke.py` PASS |
| optional images missing | mock dataset 没有图像 | `inspect_dataset.py` warnings | 接受 warning；不要把 optional 改成 required | inspection `Status: PASS` |
| release 创建失败 | 输出目录非空 | 看 `release output is not empty` | 换新目录，或人工确认后清理旧目录 | `prepare_dataset_release.py` PASS |
| checkpoint 文档不一致 | 老文档使用过不符合当前实现的 checkpoint 后缀，代码实际写 `checkpoint.npz` | 搜索 checkpoint 相关文档和训练脚本 | 文档统一为 `checkpoint.npz` | README / training docs / contracts 一致 |
| replay 缺少字段 | 旧 replay 或手工 JSONL 不符合 contract | 检查每行是否含 `schema_id` / `release_id` / `action_type` | 重新运行 `replay_policy.py` | `prepare_bridge_handoff.py` PASS |
| 下游执行不稳定 | 接触参数、坐标系、轨迹接口或 action scale 不匹配 | 在 bridge 侧做固定场景 replay | 下游排查 PyBullet / MoveIt / frame transform | 本仓库只保证 handoff contract |

## 3. Action Semantics Guardrails

不要做：

- 不要把 `action[8]` 直接切成 `action[7]`。
- 不要把 quaternion 的 4 维删成 rpy 的 3 维却不记录转换。
- 不要把 gripper command 丢掉。
- 不要把 `ee_pose_gripper` 伪装成 `ee_delta_gripper`。

应该做：

- 在 manifest 中写清 `action_type`。
- 在 adapter 中显式转换 action 语义。
- 在训练前用 `inspect_dataset.py` fail fast。
- 在 handoff 中保留 `schema_id`、`release_id` 和 `action_type`。

## 4. Sim2Real Wording

当前正确表述：

```text
This repository exports validated datasets and replay handoff bundles for downstream Sim-to-Sim / Sim2Real-readiness evaluation.
```

不建议表述：

```text
This repository completes Sim2Real transfer.
```

原因：

- 当前没有真实机械臂验证。
- MuJoCo / PyBullet 接触模型不能直接等价真实世界。
- 真实部署还需要硬件驱动、夹爪驱动、传感器输入、安全层、标定和坐标变换。
