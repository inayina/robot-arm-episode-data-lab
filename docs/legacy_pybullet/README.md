# Legacy PyBullet / KUKA Archive

这些文档记录本仓库早期 PyBullet / KUKA 阶段的设计、路线图和排障记录。它们保留为历史能力证据，不再作为当前 README 主线。

当前主线是：

```text
Panda episode schema
-> dataset inspection / release
-> baseline training / offline evaluation
-> replay JSONL / bridge handoff
```

## 保留价值

| 文档 | 价值 |
|---|---|
| [baseline_plan.md](baseline_plan.md) | 最早的 image-state-action episode 数据闭环 |
| [hal_ik_roadmap.md](hal_ik_roadmap.md) | HAL、IK、笛卡尔插补的工程拆解 |
| [rrt_roadmap.md](rrt_roadmap.md) | 双向 RRT 与 PyBullet 碰撞检测 |
| [day1_grasp_spec.md](day1_grasp_spec.md) | constraint grasp、gripper URDF、抓取评测排障 |
| [design_10day.md](design_10day.md) | 早期 10 天增强栈设计 |
| [portfolio_roadmap.md](portfolio_roadmap.md) | 早期投递路线和作品集拆解 |
| [pybullet_audit.md](pybullet_audit.md) | PyBullet 控制调用审计 |

## 使用边界

- 可以作为 legacy demo、控制栈基础、排障过程和工程演进证据。
- 不应把这些文档描述成当前主线。
- 不应把 PyBullet / KUKA demo 包装成 Panda training pipeline。
- 不应把仿真成功包装成真实机械臂 Sim2Real 成功。

当前入口请优先看：

- [../PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)
- [../DATA_FLOW.md](../DATA_FLOW.md)
- [../TRAINING_PIPELINE.md](../TRAINING_PIPELINE.md)
- [../DEMO_GUIDE.md](../DEMO_GUIDE.md)
- [../THREE_REPO_ARCHITECTURE.md](../THREE_REPO_ARCHITECTURE.md)
