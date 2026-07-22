# Gate V0.5：Panda 动作与数据契约审计

> **LingBot 执行路线状态：CLOSED / ARCHIVED**（决策日期 2026-07-21）  
> **本文档角色：模型无关基础设施**（由 LingBot 选型审计触发，**不**随 LingBot 关闭而废弃）。  
> **保留内容：** absolute EEF 方案 B、canonical channel selection、policy action semantics、execution adapter conversion、Go/No-Go 分栏。  
> **当前活动预训练候选：** SmolVLA（S2 Hold；见 [`SMOLVLA_GATE_S2_OPEN_LOOP.md`](SMOLVLA_GATE_S2_OPEN_LOOP.md)）。  
> **禁止：** 删除本契约；把 55-D 切片当作已验证的 Panda 执行映射；自动恢复 LingBot Gate V1。

**日期**：2026-07-21  
**状态**：只读审计完成；**不进入 LingBot Gate V1**；不下 LingBot 权重；不装 LingBot；不训练；不跑 Isaac。  
**当前活动候选（非 LingBot）**：见 [`SMOLVLA_GATE_S0_COMPATIBILITY_AUDIT.md`](SMOLVLA_GATE_S0_COMPATIBILITY_AUDIT.md) / [`SMOLVLA_GATE_S2_OPEN_LOOP.md`](SMOLVLA_GATE_S2_OPEN_LOOP.md)。  
**前置**：[`VLA_GATE_V0_COMPATIBILITY_AUDIT.md`](VLA_GATE_V0_COMPATIBILITY_AUDIT.md)  
**关联**：[`POLICY_ADAPTER_CONTRACT.md`](POLICY_ADAPTER_CONTRACT.md)、[`configs/robot_schemas/panda.yaml`](../configs/robot_schemas/panda.yaml)

## 0. 关键修正（相对 V0）

**禁止**把 LingBot 55-D canonical output → 本仓 `ee_delta_gripper[7]` 描述为「简单」或「可逆」的维度映射。

必须拆成三层：

| 层 | 含义 | 本仓现状 |
|---|---|---|
| **1. Canonical channel selection** | 55-D 中哪些维对单臂 Panda 有意义、其余如何 pad/mask | **未冻结**（本文件草案） |
| **2. Policy action semantics** | 选中维表示什么：绝对关节角 / 绝对 EE 位姿 / 相对 delta / gripper cmd vs state | 上游原生是 **绝对 EE 目标 + gripper cmd**；中游 ACT 训练常用 **派生 delta** |
| **3. Execution adapter conversion** | 语义目标 → 有界增量命令 → Isaac/控制器 | 现执行栈主要吃 **有界 `ee_delta_gripper`**；与 VLA 语义 **不是同一层** |

因此 V0 的 HOLD-2「55-D → ee_delta 可逆映射」应降级为：**错误问题陈述**。正确问题是：选定语义后，Execution Adapter 能否稳定、可测、可失败分栏地把目标变成有界命令——这不是 channel 切片可逆性。

---

## 1. 当前 Panda 数据字段审计

权威来源优先级：上游 recorder 代码 → 中游 schema/adapter/tests → release inspection 文档事实。

| 字段 | 判定 | 证据 |
|---|---|---|
| **7 维 joint position** | **已原生记录** | 上游 `recorder_node._on_frame`：`observation.state = _pad(js.position, 7)`（[`recorder_node.py`](file:///home/ina/dev/ros2-arm-teleoperation-suite/src/lerobot_recorder/lerobot_recorder/recorder_node.py) ~L342）；中游合并为 `state[8]`（[`upstream_m6.adapt_state`](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/training/adapters/upstream_m6.py)）；schema [`panda.yaml`](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/configs/robot_schemas/panda.yaml) `joint_position[7]`；fixture [`tests/test_upstream_m6_adapter.py`](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/tests/test_upstream_m6_adapter.py) `upstream_rows` |
| **gripper measured state** | **已原生记录** | `/gripper/state` → `observation.gripper[1]`（recorder L346）；与 `action[-1]` gripper **cmd** 分离（测试 `test_frame_separates_gripper_observation_and_command`）；schema `gripper_opening`；**禁止**把 cmd 当 measured（E3 INVALID_EVALUATOR_V0 教训） |
| **absolute EE xyz** | **已原生记录** | `observation.ee_pose[0:3]`；`_pose_vec` 写 position（recorder L313–316, L343）；schema `ee_pose.position_xyz[3]` |
| **absolute EE quaternion** | **已原生记录** | `observation.ee_pose[3:7]` = **xyzw**（`o.x,o.y,o.z,o.w`）；schema `orientation_xyzw[4]` |
| **当前训练用 delta xyz/rpy 动作** | **可可靠推导**（非原生 action） | 上游原生 `action` 是 **绝对 EE 目标 + gripper_cmd**（`action_type=ee_pose_gripper`，L201–202, L347）；中游 `derive_ee_delta_action=True` 时：`delta = target_pose − ee_pose` + quat→rpy（[`adapt_action`](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/training/adapters/upstream_m6.py) L98–106）。**不得**把 delta 当作 LingBot EE pose 同义词 |
| **scene RGB** | **条件性原生** | `capture_mode=="portfolio"` 时写 `observation.images.scene`（recorder L358–359）；schema `images.required: false`；canonical 事实：部分 release 有 **images missing warning**（[`THREE_REPO_CANONICAL_FACTS.md`](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/docs/portfolio/THREE_REPO_CANONICAL_FACTS.md)）。ACT scene 路径需要图；VLA 更需要。→ 对无图 episode：**当前不可获得**（除非重采/补链） |
| **language_instruction** | **已原生记录** | recorder 参数写入每帧（L353）；adapter 保留独立键（upstream_m6 L48–49）；校验要求非空（上游 `validate_dataset` / lerobot_v21）。ACT **推理不消费**语言；VLA **需要** |
| **图像 / state / action 时间戳** | **部分原生** | 每帧 **单一** `timestamp`（优先 color stamp，否则 joint）（L348）；`frame_index`/`episode_index` 原生。→ 帧级同步戳：**已原生记录**。分模态独立 stamp（image_ts / state_ts / action_ts）：**当前不可获得** |
| **action chunk 对应关系** | **当前不可获得（episode 内）** | raw episode 是逐步 `action[8]`，无 chunk 字段。ACT 在 `SceneACTDataset` 训练时按 `chunk_size` 切连续帧（[`train_act_lerobot.py`](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/training/scripts/train_act_lerobot.py)）。VLA horizon：**需要新增转换**（打包层构造），且 **未验证** 与 LingBot `--use_length` 语义一致 |

### 1.1 语义对照（极易混用）

```text
observation.ee_pose[7]     = 测量得到的绝对 EE（xyzw）
action[0:7] (upstream)     = 命令的绝对 EE 目标（同布局）
action[7]                  = gripper_cmd ∈ [0,1]（0=闭，1=开；见 panda.yaml）
observation.gripper[0]     = gripper measured
ee_delta_gripper[7]        = 由 (action_pose − ee_pose) 派生的相对增量 + gripper_cmd
```

下游 PyBullet [`PandaActionAdapter`](file:///home/ina/ros2_ws/src/ros2-moveit-pybullet-bridge/pybullet_bridge/pybullet_bridge/learning/panda_action_adapter.py) 消费的是 **delta 语义**，不是绝对 EE。

---

## 2. 两种 Panda VLA 动作方案比较

**前提**：LingBot 公开 55-D 含臂关节与 EE pose（xyz+quat）通道；**未在本仓验证**官方 Franka/Panda robot config 的精确切片。下列比较基于本仓数据事实 + V0 公开声明。

### 方案 A：joint-space

- **state**：`arm.position[7] + effector.position[1]`（= 本仓 `state[8]`）
- **action**：`arm.position[7] + effector.position[1]`（绝对关节目标 + gripper）

| 维度 | 分析 |
|---|---|
| 与现有数据兼容性 | state **原生兼容**；action **无原生关节目标命令**。要从 `ee_pose_gripper` 反解关节目标 → IK，或改采集写 joint cmd（**需要新增转换 / 可能需重采**） |
| 与 LingBot robot config | 55-D 含 14-D 臂关节位（公开）；单臂用 7 维 + pad 另 7：**原则可对齐，未验证** |
| 转换复杂度 | 高：离线需批量 IK；失败奇异位；与专家 EE 轨迹一致性难保证 |
| open-loop 评测 | 关节 MAE/RMSE 直观；但标签若由 IK 生成，评测混入 IK 误差 |
| Isaac Execution Adapter | 中：可发 joint target；但现有 ACT/bound 路径偏笛卡尔 delta，需新分支 |
| 可解释性 | 关节空间对「抓取几何」不如 EE 直观 |
| 安全风险 | 大关节跳变；限位依赖 joint excursion watchdog（上游已有部分能力，**未对 VLA 标定**） |

### 方案 B：absolute EEF

- **state**：`arm.position[7] + effector.position[1]`
- **action**：`end.position[7]`（xyz + **xyzw** quat）+ `effector.position[1]`

| 维度 | 分析 |
|---|---|
| 与现有数据兼容性 | state 原生；action **与上游 `ee_pose_gripper[8]` 同构**（已原生记录）。**最佳数据对齐** |
| 与 LingBot robot config | 公开 EE 为 XYZ+quaternion、55-D 含 14-D EE pose；单臂取 7 + pad：**原则可对齐，未验证**（含 quat 约定、双臂布局） |
| 转换复杂度 | 中低：channel selection + pad；**不要**先转成 delta 再假装是 LingBot EE |
| open-loop 评测 | 对专家绝对 EE / quat 角误差 / gripper 直接比；与 ACT delta 指标 **分栏**，不可混口径 |
| Isaac Execution Adapter | 中高：绝对目标 → **lookup 当前测量** → 有界增量（或 IK）→ 现有 safety；语义层与执行层必须拆开 |
| 可解释性 | 与抓取几何、oracle FSM 目标一致；便于对照 HOME_NO_CLOSE |
| 安全风险 | 绝对大步长若未 bound 会冲撞；必须强制「目标→有界增量」；quat 非单位/跳变需校验 |

### 方案比较结论（推荐）

**推荐方案 B（absolute EEF）作为 Panda↔LingBot 契约主方案。**

理由（已实现证据）：

1. 上游 action **本来就是**绝对 EE 目标 + gripper_cmd，无需 IK 造标签。  
2. 与公开 LingBot EE pose 描述同族（仍 **未验证** 精确布局）。  
3. 中游 ACT 的 `ee_delta` 是 **另一训练语义**，可保留为 ACT diagnostic，**不得**默认等于 VLA action。  
4. Execution 仍可落到现有有界笛卡尔栈，但那是 **第 3 层转换**，不是 channel 映射。

方案 A 仅当：官方 robot config 强制 joint action，或绝对 EE 执行不可用时再评估——当前 **证据不足** 到必须选 A。

---

## 3. Canonical active-channel spec（草案）

机器可读草案：[`evaluation/schemas/vla_panda_active_channel_spec.schema.json`](../evaluation/schemas/vla_panda_active_channel_spec.schema.json)  
示例：[`evaluation/examples/vla_panda_active_channel_spec_fixture.json`](../evaluation/examples/vla_panda_active_channel_spec_fixture.json)

### 3.1 55-D 布局（来自 LingBot 公开 README；本仓未实测）

公开分段（合计 55）：

| 段 | 维数 | Panda 单臂用法（草案） |
|---|---:|---|
| arm joint position | 14 | 用 **前 7** = Panda joints；后 7 = **0 pad** |
| end-effector pose | 14 | 用 **前 7** = xyz(3)+xyzw(4)；后 7 = **0 pad** |
| gripper position | 2 | 用 **维 0**；维 1 = **0 pad**（或 mirror，需 V1 后确认） |
| hand joints | 12 | 全 **0 pad** |
| waist | 4 | 全 **0 pad** |
| head | 2 | 全 **0 pad** |
| mobility | 3 | 全 **0 pad** |
| reserved | 4 | 全 **0 pad** |

> **未验证**：官方是否左臂/右臂顺序、gripper 双通道含义、pose 是否 wxyz。草案假定与本仓一致的 **xyzw**；若 V1 发现冲突，以官方 config 为准并修订本 fixture（不改旧 evidence）。
>
> **V0 补强（2026-07-21）**：公开 `configs/robot_configs/` **只有** `robotwin.yaml` / `agilex_cobot_magic.yaml`，**无** Franka/Panda。两者均映射 **关节**（robotwin 绝对关节；agilex 臂 `subtract_state: true`）。这与方案 B（absolute EEF）并存为张力，不推翻本仓推荐，但 Gate V1 必须显式决定是否自研 EE robot_config。详见 [`VLA_GATE_V0_COMPATIBILITY_AUDIT.md`](VLA_GATE_V0_COMPATIBILITY_AUDIT.md) §6。

### 3.2 Mask 与 normalization

- **需要 mask**（或等价 `active_dims` 列表）：训练/norm **忽略 padding 维**，避免假方差。  
- Norm stats 只在 active channels 上累计；pad 维 mean=0、std=1 哨兵，且 loss 权重 0。  
- State vs action active 集合：  
  - **State active**：arm joints[7] + gripper_measured[1]（EE 测量可另作辅助，是否进 VLA state **未验证**）  
  - **Action active（方案 B）**：EE target xyz+xyzw[7] + gripper_cmd[1]

### 3.3 Gripper / quaternion

- Gripper：**[0,1]**，0=closed，1=open（[`panda.yaml`](file:///home/ina/robot-sim-lab/robot-arm-episode-data-lab/configs/robot_schemas/panda.yaml)）。  
- Quat：**xyzw**，导出前 **L2 归一化**；拒绝范数≈0。  
- Cmd vs state 分栏记录，禁止互换。

### 3.4 版本绑定

每次 VLA 相关产物必须绑定：

```text
active_channel_spec_version
robot_config_id          # 未来官方/自研 yaml
norm_stats_sha256
checkpoint_sha256        # Gate V1+ 才有
dataset_release_id
panda_schema_id          # panda_ee_delta_gripper_v0 等
policy_action_semantics  # absolute_eef_gripper_v0 | joint_abs_gripper_v0 | ...
```

---

## 4. Execution Adapter 契约（只设计）

```text
VLA raw output (55-D, possibly normalized)
  → select active channels (+ mask check / padding anomaly)
  → semantic validation (finite, quat unit, gripper range)
  → denormalized absolute target  (方案B: EE+grip 或 方案A: joint+grip)
  → current robot state lookup    (measured joints / ee_pose / gripper)
  → conversion to bounded incremental command
        (绝对目标 − 当前测量 → clip；或 IK → joint delta；禁止无界大步)
  → workspace / joint / gripper limits
  → watchdog / E-stop
  → Isaac execution
  → measured state feedback (for GT & open-loop logs)
```

### 4.1 必须区分的五类张量

| 名称 | 定义 | 失败 lane |
|---|---|---|
| `vla_raw_output` | 模型原始 55-D（可含 norm） | interface_fail |
| `selected_active_channels` | 切片后的有意义维 | interface_fail / data_fail |
| `denormalized_target` | 物理单位下的绝对目标 | interface_fail |
| `bounded_command` | 发给控制栈的有界增量或有界 joint step | interface_fail / system_fail |
| `measured_state` | 仿真反馈（joint/ee/grip） | system_fail；**不得**当 success |

**硬规则**：不得把 `bounded_command` 或 interface PASS 写成 task success；task 仅 continuous GT。

草案 schema：[`evaluation/schemas/vla_execution_adapter_contract.schema.json`](../evaluation/schemas/vla_execution_adapter_contract.schema.json)

---

## 5. Gate V2 open-loop 指标（设计）

在 **不控 Isaac** 的前提下，用现有 episode 构 obs，跑官方/本地推理（V1 通过后）时至少记录：

| 指标 | 说明 |
|---|---|
| active-channel MAE/RMSE | 仅 active dims；pad 维单独报 anomaly |
| joint 或 EE 位置误差 | 按所选方案；方案 B 用 EE xyz RMSE |
| quaternion angular error | `2*atan2(||v||, |w|)` 类角距离；单位 rad |
| gripper accuracy / close timing | 阈值分类 + 首次闭合帧偏差 |
| action smoothness | 相邻目标 jerk / 角速度峰值 |
| action saturation 比例 | 命中 bound 的步数占比 |
| padding channel 异常 | pad 维 \|value\| > ε 的比例 |
| inference latency | P50/P95 ms；显存 |
| 与 expert / ACT / oracle 阶段对齐 | 按 stage（approach/close/lift）分桶误差；**分栏**，不合并成功率 |
| HOME_NO_CLOSE 类行为 | grip_min、z_span、near-zero delta 检测（复用 E3.6 诊断标签语义） |

Fixture 测试计划见 [`tests/test_vla_gate_v05_contracts.py`](../tests/test_vla_gate_v05_contracts.py)（只校验 schema/fixture，不跑模型）。

---

## 6. Go / No-Go

### 6.1 推荐

| 项 | 结论 |
|---|---|
| Panda↔VLA 动作方案 | **方案 B：absolute EEF + gripper_cmd** |
| 选择理由 | 与上游原生 `ee_pose_gripper` 对齐；避免 IK 造标；与公开 EE pose 描述同族；执行层单独做有界转换 |
| 对 `ee_delta_gripper` | **保留给 ACT/下游 replay**；**不是** LingBot 默认语义 |

### 6.2 仍未验证

- 官方 55-D 左右臂/quat 顺序/gripper 双通道精确布局  
- 官方是否存在可直接用的 Franka/Panda `robot_configs`  
- Norm / mask API 是否支持 ignore pad  
- 本机显存能否跑 6B（HOLD-1）  
- 权重附加许可逐文件（HOLD-3）  
- 绝对 EE → 有界增量在 Isaac 上的数值稳定性（属 V2/V3）

### 6.3 Gate V1 前必须人工确认

1. 有足够 GPU（公开示例偏 4090 级）且批准下载依赖/权重。  
2. 接受「V1 只做官方任务复现，不接 Panda」。  
3. 确认 LICENSE/权重条款。  
4. 确认本文件方案 B 为默认契约（若官方强制 joint，再回头评估 A）。

### 6.4 Gate V2 前必须完成的数据转换 fixture

1. `absolute_eef` 帧级导出：从 adapted/upstream 行写出 active-channel state/action（无 delta 冒充）。  
2. pad/mask 金样例 + norm 忽略 pad 的单测。  
3. quat xyzw 归一化与角误差参考实现（纯 numpy fixture）。  
4. 分栏指标 JSON schema（open-loop report），`claims_task_success=false`。  
5. 与 ACT delta 指标 **禁止同表混比** 的测试断言。

**实现状态（2026-07-21）**：**已完成（中游离线 fixture + 真实 episode 样例导出）**

| 产物 | 路径 |
|---|---|
| 导出库 | `evaluation/vla_contract/absolute_eef.py` |
| CLI | `training/scripts/export_absolute_eef_fixture.py`（`--input-jsonl` / `--input-parquet`） |
| 上游样例行 | `evaluation/examples/absolute_eef_upstream_rows_fixture.jsonl` |
| 导出金样 | `evaluation/examples/absolute_eef_frames_fixture.jsonl` |
| 真实 episode 样例 | `evaluation/examples/absolute_eef_from_episode52_sample.jsonl`（seed52 parquet，含 cmd≠measured） |
| open-loop report schema | `evaluation/schemas/vla_open_loop_report.schema.json` |
| 测试 | `tests/test_absolute_eef_export.py`、`tests/test_absolute_eef_episode_and_home_diag.py` |

```bash
python3 training/scripts/export_absolute_eef_fixture.py \
  --input-jsonl evaluation/examples/absolute_eef_upstream_rows_fixture.jsonl \
  --output-jsonl /tmp/absolute_eef.jsonl

python3 training/scripts/export_absolute_eef_fixture.py \
  --input-parquet /path/to/episode_000000.parquet \
  --prefer-cmd-neq-measured --max-frames 5 \
  --output-jsonl /tmp/absolute_eef_ep.jsonl \
  --provenance-json /tmp/absolute_eef_ep.provenance.json

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_absolute_eef_export.py \
  tests/test_absolute_eef_episode_and_home_diag.py
```

仍未做：真实 VLA open-loop 填数、Gate V1 权重、Isaac 执行。中游 release 的 `ee_delta_gripper[7]` **不得**冒充 absolute action；需上游 parquet / `ee_pose_gripper[8]`。

### 6.5 本轮建议新增/更新的文件

| 文件 | 作用 |
|---|---|
| `docs/VLA_GATE_V05_PANDA_ACTION_CONTRACT.md` | **本文** |
| `docs/VLA_GATE_V0_COMPATIBILITY_AUDIT.md` | 修正 HOLD-2 / §3 错误「可逆 delta 映射」表述 |
| `evaluation/schemas/vla_panda_active_channel_spec.schema.json` | active-channel 草案 |
| `evaluation/examples/vla_panda_active_channel_spec_fixture.json` | 方案 B fixture |
| `evaluation/schemas/vla_execution_adapter_contract.schema.json` | 执行层契约草案 |
| `evaluation/examples/vla_execution_adapter_contract_fixture.json` | 执行层 fixture |
| `evaluation/vla_contract/absolute_eef.py` | 方案 B 帧级导出、quat、active-channel norm |
| `training/scripts/export_absolute_eef_fixture.py` | CLI：upstream JSONL → absolute_eef fixture |
| `evaluation/schemas/vla_open_loop_report.schema.json` | Gate V2 open-loop 指标契约（禁止混 ACT delta） |
| `tests/test_absolute_eef_export.py` | 导出/拒绝 delta/pad norm/report schema 测试 |

**明确不做**：改 evidence、改 checkpoint、下载 VLA、跑 Isaac VLA、把 interface PASS 写成 task success。
