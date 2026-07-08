# 闭环仿真智能体系统规范 (AGENTS.md) - V2.1

Canonical 三仓 Agent 总览。各仓实现映射见：

- 上游：`ros2-arm-teleoperation-suite/docs/AGENTS.md`
- 下游：`ros2-moveit-pybullet-bridge/docs/AGENTS.md`
- 闭环跑法：`docs/CLOSED_LOOP_RUNBOOK.md`

---

## 1. 三仓边界与 Agent 分布

| 仓库 | 实时 Agent | 离线 Agent |
|------|------------|------------|
| **上游** | Task / Motion / Evaluation | — |
| **中游（本仓）** | — | Data Adapter / Inspector / Training / Handoff |
| **下游** | Replay / Risk / Sensor Fusion | Handoff Loader |

**Legacy 分流**：本仓 `agents/`、`core/` 为 PyBullet/KUKA 历史 Agent，**不得**与 Panda training release 混用。索引见 [archive/README.md](../archive/README.md)。

---

## 2. 上游实时 Agent（摘要）

### Task Planning Agent
- **位置**：`batch_generator` 或 L0 `teleop_input`
- **FSM**：Hover → Descend → Close → Lift → Transport → Place → Release

### Motion Planning & Control Agent
- **位置**：L2 `moveit_servo` + L3 `cartesian_impedance_controller`
- **行为**：笛卡尔伺服 + 1kHz 阻抗力矩；**不含** RRT（RRT 在 legacy/下游）

### Evaluation Agent（双轨）
| 轨道 | 实现 | 批采默认 |
|------|------|----------|
| **主轨** | `batch_generator._validate_episode` → `discard` / `stop_success` | 启用 |
| **辅轨** | `grasp_monitor` → `/grasp/status` | `enable_grasp_monitor:=true` |

**硬约束**：训练数据必须 `grasp_assist_enabled:=false`。

---

## 3. 中游离线 Agent（本仓）

| Agent | 实现 | 职责 | 不做 |
|-------|------|------|------|
| **Data Adapter** | `training/adapters/upstream_m6.py` | state[7+1]、action 语义转换 | 物理 lift/place 判定 |
| **Dataset Inspector** | `training/scripts/inspect_dataset.py` | schema + training split | 重复 object_pose 物理判定 |
| **Release** | `prepare_dataset_release.py` | 不可变 release manifest | ROS 运行时 |
| **Training** | `train_act_smoke.py` / `train_act_lerobot.py` | smoke / ACT 训练 | 仿真控制 |
| **Handoff** | `prepare_bridge_handoff.py` | JSONL + manifest 打包 | PyBullet 执行 |

---

## 4. 下游运行时 Agent（摘要）

| Agent | 实现 | 职责 |
|-------|------|------|
| **Handoff Loader** | `learning/panda_handoff.py` | 静态校验 handoff bundle |
| **Replay / Policy** | `PolicyRunner` + `PandaActionAdapter` | JSONL → PyBullet 关节命令 |
| **Risk / Monitor** | `dist_monitor` + `risk_engine` | 漂移、E-stop、Hold |
| **Sensor Fusion** | `sensor_fusion_node` | 多源对齐、接触估计（Sim2Sim） |

---

## 5. Gate 协议（清洗边界）

### 上游 episode meta (`episode_*/meta.json`)
```yaml
upstream_gate: batch_generator | teleop
success: true
```

### 中游 adapted / release manifest
```yaml
upstream_gate: batch_generator
filter_scope: training_split_only   # 物理门禁已在上游
physical_validation_applied: true
action_type: ee_delta_gripper
```

**规则**：
- `filter_scope=training_split_only` 时，中游只校验 schema 与 `success`/`safety_estop`/`drive_fault` 训练 split。
- 中游**不得**从 `observation.object_pose` 重新推导 lift/place 成败。

---

## 6. 话题与交接（Panda 主线）

| 阶段 | 关键产物 |
|------|----------|
| 上游采集 | `episode_*/train/` + `meta.json` |
| 中游 release | `frames.jsonl` + `manifest.json` |
| 中游 handoff | `bridge_handoff/` + `predicted_actions.jsonl` |
| 下游 replay | `benchmark_summary.json` |

一键 midstream 链：`scripts/run_three_repo_closed_loop.sh`

---

## 7. 与 V2.0 的差异（V2.1 修订）

1. 明确 Evaluation **双轨**（batch_generator 主轨 + grasp_monitor 辅轨）
2. Motion Agent 去掉「Servo 做 RRT」表述
3. 新增中游 / 下游 Agent 表
4. 新增 `upstream_gate` / `filter_scope` 边界
5. Legacy PyBullet Agent 与 Panda 主线分离
