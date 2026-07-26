# Policy Adapter Contract（模型无关薄适配层）

**状态（2026-07-21）**：契约、metadata schema、**策略注册表**与**薄 `PolicyAdapter` ABC**
（含 `FixturePolicyAdapter`）已在中游落地；上游运行时包装与 VLA **尚未**接入 Isaac。  
**一页速查**：[`POLICY_ADAPTER_QUICKSTART.md`](POLICY_ADAPTER_QUICKSTART.md)  
**范围**：本仓定义契约、注册表与离线 fixture；上游 Runtime Executor 落地薄包装；下游 `BasePolicy` 仅作 PyBullet 对照通道。  
**禁止**：为本契约大规模重构三仓；把 interface metadata 写成 task success；改写现有 evidence/checkpoint。

关联：

- 评测契约：[`EVALUATION_CONTRACT.md`](EVALUATION_CONTRACT.md)
- 日常 SOP：[`EMBODIED_POLICY_EVALUATION_SOP.md`](EMBODIED_POLICY_EVALUATION_SOP.md)
- Panda schema：[`../configs/robot_schemas/panda.yaml`](../configs/robot_schemas/panda.yaml)
- Metadata schema：[`../evaluation/schemas/policy_adapter_metadata.schema.json`](../evaluation/schemas/policy_adapter_metadata.schema.json)
- Absolute EEF / channel / execution adapter（**模型无关**；由 LingBot 审计触发并保留）：[`VLA_GATE_V05_PANDA_ACTION_CONTRACT.md`](VLA_GATE_V05_PANDA_ACTION_CONTRACT.md)
- LingBot Gate V0（**Closed / Archived**）：[`VLA_GATE_V0_COMPATIBILITY_AUDIT.md`](VLA_GATE_V0_COMPATIBILITY_AUDIT.md)
- SmolVLA（**当前活动候选，S3 Ready**）：[`SMOLVLA_GATE_S3_READY.md`](SMOLVLA_GATE_S3_READY.md) / [`SMOLVLA_GATE_S2_OPEN_LOOP.md`](SMOLVLA_GATE_S2_OPEN_LOOP.md)
- Benchmark 规范：[`SINGLE_BLOCK_GENERALIZATION_BENCHMARK.md`](SINGLE_BLOCK_GENERALIZATION_BENCHMARK.md)
- 统一在线接线目标：[`POLICY_RUNTIME_INTEGRATION_SPEC.md`](POLICY_RUNTIME_INTEGRATION_SPEC.md)（Proposed；v0 本合同在实施前继续作为离线兼容合同）

---

## 1. 目标

使 ACT、scripted oracle、规则/MoveIt 基线与未来 VLA 在**统一 Benchmark、统一数据契约、统一指标分栏**下比较，而不合仓、不推翻现有执行栈。

---

## 2. 最小方法集

| 方法 | 输入 | 输出 / 副作用 | 职责边界 |
|---|---|---|---|
| `load_policy(checkpoint_or_endpoint)` | 路径或服务端点 | 加载权重/客户端 | 中游定义身份字段；上游实际加载 ACT 等 |
| `reset(context)` | seed、suite_id、instruction、start_pose_mode | 清空 chunk/history | 必须在 episode reset 完成后调用 |
| `build_observation(raw_state)` | ROS/Isaac raw | model obs + `observation_schema_version` | 模型私有预处理留在 Adapter |
| `predict_action(observation, instruction)` | obs + 可选语言 | `raw_action`（可含 chunk）+ latency | instruction 可为 no-op（当前 ACT） |
| `validate_action(action)` | raw 或 postprocessed | PASS/FAIL（dim/finite/NaN/type） | 失败 → interface_fail，不得写 task success |
| `export_action(action)` | validated action | `ee_delta_gripper[7]` postprocessed | 统一映到 Panda 契约动作 |
| `report_metadata()` | — | 见 §3 字段 | 冻结身份卡；不替代 GT |
| `close()` | — | 释放 GPU/句柄 | 评测收尾必调 |

统一目标动作空间（已实现契约）：`ee_delta_gripper[7]` = `delta_xyz[3] + delta_rpy[3] + gripper_cmd[1]`。  
有界 clipping / workspace / E-stop / watchdog：**上游执行层**（例如 `bound_ee_delta_gripper`），不在 Adapter 内伪造安全。

---

## 3. 统一 metadata 字段

机器可读 schema：`evaluation/schemas/policy_adapter_metadata.schema.json`。  
Fixture：`evaluation/examples/policy_adapter_metadata_fixture.json`。

必填身份：

| 字段 | 含义 |
|---|---|
| `policy_name` | 如 `scene_act_lerobot` / `isaac_scripted_oracle` / `lingbot_vla` |
| `policy_version` | 策略实现版本字符串 |
| `checkpoint_hash` | SHA-256；oracle/无权重时用固定 sentinel |
| `dataset_version` | release_id 或 `n/a` |
| `benchmark_version` | Benchmark 规范版本 |
| `observation_schema_version` | 模型观测契约版本 |
| `action_schema_version` | 默认 `panda_ee_delta_gripper_v0` |
| `trace_run_id` | 与 `evaluation_run_id` 对齐 |

逐步报告（可 null，不得用其推断 task success）：

| 字段 | 含义 |
|---|---|
| `inference_latency_ms` | 单次 predict 墙钟 |
| `raw_action` | 模型原生输出（可截断记录） |
| `postprocessed_action` | export 后的 `ee_delta_gripper[7]` |
| `safety_clipping` | 是否 clip、哪些轴、阈值引用 |
| `failure_lane` | `data_fail` / `interface_fail` / `behavior_tag` / `task_gt` / `system_fail` / `none` |

---

## 4. 现有实现映射（薄包装，不重写）

| 策略 | 仓库 · 符号 | Adapter 映射 | 状态 |
|---|---|---|---|
| 当前 ACT | 上游 `SceneACTRuntime` + `IsaacPolicyInferenceNode` | `load/predict/export` ≈ `infer` + `bound_ee_delta_gripper` | **已实现运行时**；未挂本契约 ABC |
| scripted oracle | 上游 `isaac_sim_adapter.scripted_oracle` | `predict` = FSM 目标；跳过 NN | **已实现**；物理对照，非 policy 成功 |
| MoveIt / 规则基线 | 上游 teleop/servo 路径 | 有界笛卡尔目标 → export | **文档声明，E3 对照套件未固化** |
| 下游 JSONL replay | 下游 `BasePolicy` / `JsonlActionReplayPolicy` | open-loop 对照 | **已实现** PyBullet；非 Isaac 主评测宿主 |
| 未来 LingBot-VLA | 新 `LingBotVlaAdapter`（仅未来复审） | 执行路线 **Closed / Archived**；禁止自动恢复 V1 / 下 6B | **未实现**；审计见 V0（archived） |
| SmolVLA | 未来 `SmolVlaAdapter` | Recovery v3 已完成 LoRA 与 open-loop **Pass**；有界 Isaac S4 已跑并 **Hold**（lift 0/5）；再跑 Isaac / 扩种子 / 重训须另行人工批准；禁止把 6-D 当 absolute EEF / ee_delta | S1–S2 离线证据 + Recovery v3 gate_v3 Pass + 有界 S4 Hold；**本 Adapter ABC 运行时仍未挂 Isaac**（S4 走 `smolvla_policy_inference_node`） |

当前 ACT 硬事实（不得在 Adapter 设计中忽略）：

- 观测：`state[8]` + scene RGB→224；`n_obs_steps=1`
- **不消费** `language_instruction`（字段可保留在数据，但不进 `input_features`）
- `chunk_size` 默认 50；部署必须走 chunk 队列（`select_action`），禁止每拍只取 chunk[0]

---

## 5. 失败分栏（防止混淆）

| `failure_lane` | 含义 | 权威判定 |
|---|---|---|
| `data_fail` | schema/缺失/泄漏/不同步 | 中游 inspect / Data 层 |
| `interface_fail` | 加载失败、维数错误、NaN、timeout | Adapter validate + 上游 report |
| `behavior_tag` | HOME_NO_CLOSE 等诊断标签 | 中游 summarizer / 行为诊断 |
| `task_gt` | reach/grasp/lift/place | **仅**上游 continuous GT |
| `system_fail` | QoS、TF、清理、资源 | run_manifest / system_performance |
| `none` | 本步无失败标签 | — |

**硬规则**：`interface` PASS 或 offline loss 改善 **不得** 写 `outcome.success=true`。

---

## 6. 三仓 ownership（与 E0 一致）

| 仓库 | Adapter 相关职责 | 禁止 |
|---|---|---|
| 中游 | 契约、metadata schema、离线对比、Benchmark 规范、V0 矩阵 | 启动 ROS/Isaac；从 object_pose 重推物理成功 |
| 上游 | Runtime 加载、有界执行、GT、oracle/规则执行 | 中游 release/聚合；用 loss 替代 GT |
| 下游 | handoff replay / risk 对照 | 覆盖上游 `outcome.success`；成为 VLA 主评测宿主 |

---

## 7. 验收（本契约文档轮）

- [x] 方法集与 metadata 字段成文
- [x] JSON Schema + fixture 可被 `tests/test_evaluation_contract.py` 校验
- [x] 中游薄 `PolicyAdapter` ABC + `FixturePolicyAdapter` + 三策略注册表
- [x] Benchmark spec schema 覆盖 baseline / id / ood_position
- [ ] 上游运行时包装类挂载（ACT/oracle/规则）— 后续迭代
- [ ] SmolVLA / 任意 VLA 的 Isaac `export`（S3+ 另批；禁止因 S2 接口 Pass 自动进入）
- [x] LingBot Gate V1 本机路径：**Closed / Archived**（不得自动恢复 / 下载 6B）
