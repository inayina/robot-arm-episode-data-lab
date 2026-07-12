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

**Legacy 分流**：本仓 `agents/`、`core/` 为 PyBullet/KUKA 历史 Agent，**不得**与 Panda training release 混用。索引见 [archive/README.md](archive/README.md)。

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

---

## 8. Codex / AI 项目事实检索规则

### 8.1 基本原则

涉及本项目实际实现、三仓数据流、接口协议、训练流程、评估、handoff 或故障排查的问题时，不得仅依据通用机器人、机器学习或软件工程经验回答。

回答前必须优先检索当前项目中的代码、配置、测试和文档。

项目事实的证据优先级如下：

1. 自动化测试及实际运行产物
2. 当前代码实现
3. 配置文件与数据 schema
4. 当前版本技术文档
5. README 与作品集描述
6. 行业通用经验

当代码、测试与文档不一致时，应优先采用测试和代码，并明确指出冲突。

### 8.2 RAG 调用条件

当用户问题涉及以下内容时，回答前必须调用项目 RAG：

- 三仓之间的数据流与职责边界
- Panda episode、state、observation、action 的真实字段
- Data Adapter、Inspector、Release、Training、Replay、Handoff
- MLP BC、ACT、离线评估与模型输出
- Gate、schema、manifest 和训练数据筛选
- 上游采集、中游训练、下游执行之间的接口
- 当前项目是否已经实现某项功能
- 故障排查、接口不一致或文档与代码冲突

调用方式：

```bash
python3 scripts/rag_assistant.py --query "<用户原始问题>"
```

也可以使用：

```bash
bin/ask-project "<用户原始问题>"
```

### 8.3 检索范围

项目 RAG 应覆盖以下三个仓库：

- `../ros2-arm-teleoperation-suite`
- `.`
- `../ros2-moveit-pybullet-bridge`

优先检索：

- `README.md`
- `AGENTS.md`
- `docs/**/*.md`
- `scripts/**/*.py`
- `training/**/*.py`
- `configs/**/*.yaml`
- `tests/**/*.py`
- 相关 ROS 2 launch、节点和接口定义

不得索引或引用：

- `.git/`
- `.venv/`
- `build/`
- `install/`
- `log/`
- `node_modules/`
- `dataset/`
- `checkpoints/`
- 二进制文件及大型生成产物

### 8.4 回答格式

回答项目问题时，必须明确区分以下四类内容：

#### 已实现

存在直接代码、配置或测试证据，可以确认当前仓库已经实现。

#### 文档声明，代码未确认

文档中提到或规划了该能力，但当前检索结果未能找到充分的代码或测试证据。

#### 基于证据的推断

可以根据调用关系或数据流作出合理判断，但不存在直接实现证据。

#### 通用背景知识

属于机器人、机器学习或软件工程的一般规律，不代表当前项目已经采用。

每次回答至少包含：

- 直接结论
- 仓库名
- 相对文件路径
- 相关函数、类、配置字段或章节
- 行号或代码位置
- 当前证据是否充分

如果证据不足，应明确回答：

> 当前项目证据不足，无法确认。

禁止通过行业惯例补全项目现状。

### 8.5 修改代码前的要求

修改涉及三仓接口、schema、action 语义、release、handoff 或训练流程的代码前，必须：

1. 检索三个仓库中的相关实现；
2. 确认当前调用链和数据格式；
3. 检查对应测试；
4. 说明将修改哪个仓库以及为什么；
5. 避免在多个仓库重复实现同一职责；
6. 不得破坏以下既定边界：

- 上游负责遥操作、仿真交互、任务执行和数据采集；
- 中游负责数据适配、检查、release、训练、评估和 handoff；
- 下游负责 handoff 加载、回放执行和风险验证。

### 8.6 项目范围约束

当前项目应描述为：

> Panda 机械臂的多仓数据、训练、离线评估与 Sim2Sim / Sim2Real-readiness 验证闭环。

当前不得默认声称：

- 已完成真实机械臂部署；
- 已完成真实 Sim2Real；
- 已实现稳定在线自主抓取；
- 离线 loss 提升等同于任务成功率提升；
- 文档中出现的规划功能已经全部实现。

Legacy PyBullet/KUKA 实现不得与 Panda 主线混用。
