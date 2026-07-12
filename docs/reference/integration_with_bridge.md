# 与 ros2-moveit-pybullet-bridge 集成

本仓库与 **`ros2-moveit-pybullet-bridge`** 的新边界是：本仓库负责数据、训练、离线评估和 replay 文件导出；bridge 负责消费 policy/replay actions，并做 Sim2Real 双源验证、分布偏移监控和风险闭环。

更完整的仓库边界见 [TRAINING_TO_SIM2REAL.md](../TRAINING_TO_SIM2REAL.md)。

## 当前主线

| 项 | 约定 |
|----|------|
| 主线机器人 | **Franka Panda** |
| 本仓库职责 | dataset inspection、LeRobot export、smoke training、offline evaluation、policy replay export |
| bridge 职责 | PolicyRunner、MoveIt/PyBullet 验证、distribution shift monitor、risk engine |
| replay 文件 | `training/reports/panda_act_smoke/predicted_actions.jsonl` |
| action type | `ee_delta_gripper` |

UR3 / UR5 适配是后续真实工业机械臂方向，应通过新增 robot schema 文件实现，不直接修改 Panda schema。

## Replay Contract

`training/scripts/replay_policy.py` 导出中立 JSONL：

```json
{
  "timestamp": 0.033,
  "episode_index": 0,
  "frame_index": 1,
  "task": "pick_lift",
  "robot": "panda",
  "schema_id": "panda_ee_delta_gripper_v0",
  "release_id": "panda_demo_delta_v0",
  "action_type": "ee_delta_gripper",
  "action": [0.001, 0.0, -0.002, 0.0, 0.0, 0.01, 0.0]
}
```

bridge 侧只消费已经声明 schema 的 action stream。本仓库不直接启动 ROS 2 runtime，不承担真机执行职责。

## Handoff Bundle

`training/scripts/prepare_bridge_handoff.py` 将 replay 和检查结果打包给 bridge：

```text
bridge_handoff/
├── predicted_actions.jsonl
├── dataset_manifest.json
├── dataset_inspection_report.json
├── replay_check.json
└── handoff_manifest.json
```

`replay_check.json` 包含 action dim、per-dim min/max、frame count、schema/action type 一致性和有限值检查。当前 bridge 仓库的 `ReplayPolicy` 仍是 pkl joint-position replay；Panda JSONL 的实际 runtime consumer 应在 bridge 侧新增 `JsonlActionReplayPolicy`，并负责限幅、碰撞检查、分布偏移监控和风险闭环。

## 相关文档

- [panda_training_lab_spec.md](../archive/planning/panda_training_lab_spec.md) - 已归档的训练与统一 Panda schema 改造 SPEC
- [panda_training_data_chain_roadmap.md](../archive/planning/panda_training_data_chain_roadmap.md) - 已归档的分阶段开发路线图
- [TRAINING_TO_SIM2REAL.md](../TRAINING_TO_SIM2REAL.md) - 三个仓库之间的边界
- [upstream_downstream_contracts.md](../dev/upstream_downstream_contracts.md) - 上下游数据与 replay 契约
