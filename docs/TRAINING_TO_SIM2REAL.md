# Training to Sim2Real Boundary

This repository is not a robot runtime. It is the data, training, and evaluation lab. Robot execution belongs to `ros2-arm-teleoperation-suite` or `ros2-moveit-pybullet-bridge`.

## Repository Roles

```text
ros2-arm-teleoperation-suite
→ 负责 MuJoCo / teleop / grasping，产生 Panda 机器人 episode

robot-arm-episode-data-lab
→ 负责数据检查、LeRobot 导出、训练、评估、policy replay 文件导出

ros2-moveit-pybullet-bridge
→ 负责消费 replay / policy actions，做 Sim2Real 双源验证、分布偏移监控和风险闭环
```

## Current Robot Boundary

当前主线 robot schema 是 Franka Panda。UR3 / UR5 适配是后续工作，未来应通过新增 robot schema 文件实现，而不是直接修改现有 Panda schema。

本仓库内的训练模块应以 `configs/robot_schemas/panda.yaml` 为统一 observation/action 契约。第一版 policy replay 输出中立 JSONL 文件，而不是直接启动 ROS 2 runtime。

## Replay Handoff

`training/scripts/replay_policy.py` 导出：

```text
training/reports/panda_act_smoke/predicted_actions.jsonl
```

每行是一条 Panda action：

```json
{
  "timestamp": 0.033,
  "episode_index": 0,
  "frame_index": 1,
  "robot": "panda",
  "schema_id": "panda_ee_delta_gripper_v0",
  "action_type": "ee_delta_gripper",
  "action": [0.001, 0.0, -0.002, 0.0, 0.0, 0.01, 0.0]
}
```

`training/scripts/prepare_bridge_handoff.py` 将 replay、dataset manifest、inspection report 和 replay check 打包成 `bridge_handoff/` 目录，供 bridge 后续实现 JSONL consumer 时直接使用。

`ros2-moveit-pybullet-bridge` 的 PolicyRunner 后续消费该文件，并负责 Sim2Real 双源验证、分布偏移监控和风险闭环。

## Planning Source

历史改造计划见 [archive/planning/panda_training_lab_spec.md](archive/planning/panda_training_lab_spec.md)。
分阶段开发、验收命令和上下游适配顺序见
[archive/planning/panda_training_data_chain_roadmap.md](archive/planning/panda_training_data_chain_roadmap.md)。
