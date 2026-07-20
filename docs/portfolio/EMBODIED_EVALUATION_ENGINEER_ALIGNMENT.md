# 具身操作模型评测工程师岗位对齐与三仓复用方案

**日期**：2026-07-18  
**目标岗位**：具身操作模型评测工程师（Isaac Sim 方向）  
**项目范围**：Panda 机械臂的多仓数据、训练、离线评估与 Sim2Sim / Sim2Real-readiness 验证闭环  
**当前状态**：已具备 Isaac Sim PoC、统一 episode contract、离线评估、下游风险评测基础，以及
**ACT checkpoint → Isaac 有界 learned-policy smoke**（home / warmstart 分层诊断、判定标签与止损门）。
尚未形成完整 multi-seed 回归套件；上游 continuous GT（`panda_continuous_gt_v0` →
`episode_results.jsonl`）已有界落地，policy online 默认挂载与真机评测未开展。

**日常评测执行手册**：[`../EMBODIED_POLICY_EVALUATION_SOP.md`](../EMBODIED_POLICY_EVALUATION_SOP.md)

---

## 1. 直接结论

当前三仓项目与岗位的重合点已经不是“安装并打开 Isaac Sim”，而是以下工程基础：

1. MuJoCo、Isaac Sim、PyBullet 分工明确的多仿真器链路；
2. episode schema、release、handoff 和 provenance；
3. 上游物理成功门禁与中游 schema 门禁分离；
4. 模型离线指标、Sim2Sim 分布比较和下游风险监控；
5. JSON、Markdown、HTML、CSV 等结构化证据产物。

岗位对齐的主要缺口不是再增加一个模型，而是补齐：

> learned policy checkpoint → Isaac action execution → 固定 seed 场景矩阵 → 自动任务判定 → 失败归因 → 回归报告 → 数据增采建议。

因此，后续作品应定位为 **Isaac Sim Embodied Policy Evaluation Harness**，而不是“Isaac 数据生成项目”或“又一个训练仓库”。

---

## 2. 岗位要求与当前项目映射

| 岗位能力 | 当前直接证据 | 证据状态 | 需要补齐 |
|---|---|---|---|
| 仿真评测 | MuJoCo upstream、Isaac backend、ACT→Isaac 有界 rollout | 已实现（有界 smoke） | multi-seed suite + 连续接触/抬升 GT |
| 真机评测意识 | safety、gate、tracking、risk 与 handoff 边界 | 仅 readiness 设计/仿真证据 | 真实硬件与现场评测证据，不得虚构 |
| 评测流程设计 | batch gate、schema、release、**EMBODIED_POLICY_EVALUATION_SOP** | 已实现日常 SOP | 契约层 suite 自动化进 CI |
| 操作性能指标 | lift/place gate、tracking、behavior 标签（降Z/对准/闭合） | 分散+SOP 固化 | 统一 subgoal GT 与 Isaac evaluator |
| 泛化评测 | MuJoCo randomization、Sim2Sim distribution comparison | 最小证据 | object/visual/camera/dynamics 分层矩阵 |
| 稳定性评测 | seed、reset、watchdog、excursion 护栏分类 | 局部实现 | repeated seed、一致率、置信区间 |
| 数据分析与可视化 | EDA、汇总脚本、evidence 目录 | 已实现 | 多 checkpoint delta 仪表盘 |
| 问题闭环 | 失败归因树→平台/数据/模型建议；扩数据止损门 | 已有范例（SOP §6–7） | 自动生成增采工单 |
| Isaac 技能 | Panda ROS bridge、ACT online infer、home/warmstart 协议 | 已实测有界 rollout | 批量场景矩阵与 effort 模式对照 |

### 当前可以诚实声称

- 完成 Isaac Sim 6.0 Panda 最小场景与 ROS 2 bridge PoC；
- 打通 joint state、TF、object pose、reset、scene RGB、EE/FT 最小接口；
- 使用现有 recorder 产出 Isaac/MuJoCo raw episode，并通过中游 adapter/schema；
- 对 MuJoCo 与 Isaac matched episode 执行 W1、trajectory RMSE、RGB 与时序比较；
- **已跑 ACT checkpoint → Isaac 有界 learned-policy smoke**（home / warmstart），并固化分栏指标与判定标签（见 `EMBODIED_POLICY_EVALUATION_SOP.md`）；
- 能明确区分离线 loss、接口通过、行为诊断标签与任务成功率。

### 当前不能声称

- Isaac 已完成稳定抓取或批量统计显著成功率；
- 已完成 multi-seed 正式 suite 与 continuous lift GT evaluator 全量落地；
- P5 单 episode 已形成统计显著的泛化结论；
- 已完成真机部署或真实 Sim2Real；
- 离线 loss 改善等价于任务成功率改善；
- warmstart 闭合等价于 home 自主抓取成功。

---

## 3. 目标评测架构与仓库边界

```text
model checkpoint + feature contract
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 上游 ros2-arm-teleoperation-suite                       │
│ Isaac/MuJoCo runtime、policy action execution、reset、   │
│ privileged ground truth、task/subgoal 判定、raw episode │
└──────────────────────────┬──────────────────────────────┘
                           │ evaluation run artifacts
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 中游 robot-arm-episode-data-lab                         │
│ schema/release 校验、指标聚合、slice 对比、置信区间、   │
│ model delta、failure taxonomy、结构化报告               │
└──────────────────────────┬──────────────────────────────┘
                           │ optional handoff / risk input
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 下游 ros2-moveit-pybullet-bridge                        │
│ PyBullet replay、tracking/distribution/risk benchmark、 │
│ 独立 Sim2Sim 风险复核                                   │
└─────────────────────────────────────────────────────────┘
```

边界原则：

- Isaac USD、PhysX、Replicator 和 ROS bridge 细节留在上游；
- raw episode 的训练适配、统计分析和模型报告留在中游；
- PyBullet IK、runtime risk engine 与下游 benchmark 留在下游；
- 三仓共享 contract 和结果 schema，不共享仿真器内部 API；
- 不把下游 `PandaActionAdapter(pybullet_ik)` 搬进 Isaac；
- 不让中游重新从 object pose 推导已经由上游确认的采集成功门禁。

---

## 4. 上游可复用能力

仓库：`ros2-arm-teleoperation-suite`

| 可复用模块 | 代码位置/符号 | 复用方式 | 当前限制 |
|---|---|---|---|
| backend 选择 | `src/teleop_bringup/launch/full_system.launch.py`，`sim_backend` | 直接作为 MuJoCo/Isaac 评测入口 | Isaac capability 仍少于 MuJoCo |
| backend launch 隔离 | `src/teleop_bringup/launch/backends/{mujoco,isaac}.launch.py` | 每个 suite 使用相同顶层入口 | backend 内部配置不能强行统一 |
| ROS simulator contract | `docs/SIMULATOR_BACKEND_CONTRACT.md` | 作为 evaluator 与 backend 的稳定边界 | E1 已补齐 effort command 基础链路，learned-policy 闭环尚未接入 |
| Isaac raw→canonical adapter | `src/isaac_sim_adapter/isaac_sim_adapter/adapter_node.py::IsaacSimAdapter` | 复用 joint/object/EE/FT/RGB/reset 与 `/sim/joint_effort_cmd` 映射 | 当前仅完成固定 effort sequence 实跑，不代表 policy rollout |
| Isaac Panda 场景 | `src/isaac_sim_adapter/scripts/isaac_panda_backend.py` | 扩展 scenario manifest、seed 与 randomization | 当前仅单 Panda/红箱 PoC |
| batch FSM | `src/synth_data_gen/synth_data_gen/batch_generator.py::BatchGenerator.run_batch` | 复用任务阶段定义与 scripted expert | 不能让 teacher FSM 代替被测 policy |
| 物理门禁语义 | `BatchGenerator._validate_episode` | 提取/复用 lift、place、tracking 等判定语义 | 当前逻辑与 batch 内部状态耦合，宜封装 evaluator，不宜跨仓复制 |
| reset 与 episode 边界 | `/sim/reset_scene`、`/lerobot_recorder/end_episode` | 直接用于每次 rollout 的事务边界 | reset 后 determinism 仍需多次验证 |
| raw episode recorder | `src/lerobot_recorder/lerobot_recorder/recorder_node.py`、`lerobot_v21_dataset.py` | 直接记录 action/state/pose/FT/RGB/meta | 评测结果字段尚未进入独立 result schema |
| 多模态同步 | `lerobot_recorder/time_sync.py::MultiModalSync` | 复用 missing/stale/reused 诊断 | 高负载 Isaac 需重新测同步窗口 |
| 系统 telemetry | `lerobot_recorder/system_telemetry.py::SystemTelemetryNode` | 复用 CPU、RSS、affinity、recorder Hz | 当前未自动持久化进 episode/report |
| provenance | recorder 的 `simulator_backend/version/scene_id` | 直接用于 run 可追溯性 | adapted 数据对 provenance 继承仍不完整 |
| safety/Servo/control | `safety_monitor`、MoveIt Servo、ros2_control | 作为 action execution 与异常事件来源 | Isaac effort adapter 已完成 E1 基础验收；Servo/policy 闭环和公平对比仍未完成 |
| MuJoCo randomization | MuJoCo backend/domain randomizer | 作为现有分布基线 | 不应复制 MuJoCo API 到 Isaac；Isaac 用 Replicator/PhysX 实现同语义范围 |
| grasp monitor | `/grasp/status` 辅轨 | 可作为 subgoal/failure signal | batch `_validate_episode` 仍是训练采集主门禁 |

### 上游最值得直接复用的部分

1. `sim_backend` 入口和 backend-neutral ROS contract；
2. recorder、EndEpisode、reset 与 provenance；
3. batch FSM 的阶段命名和 `_validate_episode` 的物理判定语义；
4. telemetry、tracking、safety 与故障事件；
5. MuJoCo 作为快速 reference backend。

### 上游不应直接复用的部分

- MuJoCo XML、renderer、contact debug 和 grasp assist；
- Isaac USD/PhysX/OmniGraph 具体实现；
- teacher 的运动命令作为模型评测动作；
- 把一个 backend 的 FT 数值阈值无校准地用于另一个 backend。

---

## 5. 中游可复用能力

仓库：`robot-arm-episode-data-lab`

| 可复用模块 | 代码位置/符号 | 复用方式 | 当前限制 |
|---|---|---|---|
| upstream adapter | `training/adapters/upstream_m6.py` | 将 raw `action[8]` 显式派生为 `ee_delta_gripper[7]` | provenance 继承需补全 |
| dataset loader | `training/scripts/inspect_dataset.py::load_rows` | 统一读取 raw/adapted 评测数据 | 尚无 evaluation result 专用 loader |
| schema inspection | `inspect_dataset.py::inspect_dataset` | 直接作为评测输入 G0/G1 | 只证明数据合规，不证明任务成功 |
| immutable release | `prepare_dataset_release.py::prepare_release` | 固定被测数据、schema、split 和 release id | 评测 run 还需要 model/scenario manifest |
| low-dimensional EDA | `eda_low_dim_dataset.py::trajectory_metrics`、`quality_gate` | 复用轨迹步长、反转、质量分布指标 | 不是在线 rollout evaluator |
| policy offline evaluation | `evaluate_policy.py::evaluate_policy` | 复用 RMSE、smoothness 和 success metadata 汇总 | 离线指标不能当任务成功率 |
| ACT baseline | `train_act_lerobot.py::build_act_policy`、`evaluate` | 作为稳定被测 checkpoint | scene-only、language 非输入、尚无 canonical 完整 ACT run 证据 |
| Sim2Sim comparator | `compare_sim_backends.py::compare_datasets` | 直接复用 W1、trajectory RMSE、timing、RGB 比较 | 当前为 episode dataset 对比，不是多 checkpoint regression |
| P5 证据模板 | `docs/portfolio/SIM2SIM_ISAAC_P5_EVIDENCE.md` | 作为限制声明与问题→行动写法模板 | 每 backend 仅 1 episode |
| handoff builder | `prepare_bridge_handoff.py` | 保持模型输出到下游的静态契约 | 不承担 Isaac runtime action execution |
| canonical evidence | `CANONICAL_EXPERIMENT.md`、`EVIDENCE_INDEX.md` | 复用证据分级和可追溯写法 | 必须继续区分 current、design、legacy |
| feedback template | `docs/templates/upstream_feedback_report.yaml` | 扩展为 failure slice → 数据增采建议 | 当前不是 Isaac 自动生成结果 |

### 中游最值得新增的薄层

只新增离线评测聚合，不复制 runtime：

```text
evaluation/
├── schemas/
│   ├── run_manifest.schema.json
│   └── episode_result.schema.json
├── scripts/
│   ├── aggregate_policy_eval.py
│   ├── compare_checkpoints.py
│   └── render_evaluation_report.py
└── reports/<evaluation_run_id>/
```

建议复用现有 `load_rows`、统计 summary、release manifest 和报告风格，不把 Isaac Python 依赖安装进中游训练环境。

---

## 6. 下游可复用能力

仓库：`ros2-moveit-pybullet-bridge`

| 可复用模块 | 代码位置/符号 | 复用方式 | 当前限制 |
|---|---|---|---|
| policy runner 工程模式 | `pybullet_bridge/learning/policy_runner.py::PolicyRunner` | 复用 configure/activate/reset/watchdog/latency/health 的设计 | 当前输出 `JointTrajectory` 到 PyBullet bridge，不是 Isaac runner |
| static handoff validator | `learning/panda_handoff.py::load_handoff_bundle` | 直接校验 schema/action dim/timestamp/replay check | 只消费 handoff，不加载 ACT checkpoint |
| Panda action validation | `learning/panda_action_adapter.py::PandaActionAdapter` | 复用 delta/gripper/限幅检查语义 | `pybullet_ik` 只属于下游；Isaac 不应直接调用 |
| distribution monitor | `dist_monitor` | 复用 KL/W1/MMD、baseline/reset 和 anomaly 思路 | 阈值需要用 Isaac 多 episode baseline 重新校准 |
| time alignment | `dist_monitor/time_aligner.py::TimeAligner` | 复用异频窗口对齐算法 | 需要适配上游 topic/result schema |
| dynamics anomaly | `dist_monitor/dynamics_anomaly.py` | 复用速度跳变与 tracking spike 指标 | 不等价于任务失败判定 |
| risk aggregation | `risk_engine/aggregator.py::RiskAggregator` | 复用多维风险和改进建议映射 | 当前权重是下游 runtime 口径，不能直接作为 Isaac go/no-go |
| risk runtime | `risk_engine/risk_node.py::RiskEngineNode` | 复用 telemetry/tracking/planning failure 接入方式 | 不应迁到中游；Isaac 可通过结果文件离线复核 |
| sensor fusion | `pybullet_bridge/sensor_fusion_node.py` | 复用异频传感器、接触/滑落估计思路 | 当前项目文档仍有规划口径，需以代码测试为准且未接入 Isaac |
| benchmark harness | `scripts/benchmark_system.py` | 复用 bounded run、timeseries、summary、report 组织方式 | launch stack 与 PyBullet 绑定，需要新 adapter 而非硬改原脚本 |
| NFR checker | `scripts/check_performance_nfr.py` | 复用频率、延迟、P95 和 readiness 检查 | Isaac 的 FPS/GPU 指标需要新增数据源 |
| report generators | `scripts/generate_*_report.py`、`docs/samples/` | 复用 HTML/CSV/图表输出模式 | 样例数字不能冒充新 Isaac 实验结果 |
| grasp protocol | `docs/GRASP_EVALUATION_PROTOCOL.md` | 复用评测协议结构和 sweep 思路 | 其中真机准入口径不能写成已完成真机验证 |

### 下游复用判断

- **直接复用**：handoff 静态校验、统计算法、报告结构、bounded benchmark 模式；
- **通过 adapter 复用**：PolicyRunner lifecycle、distribution/risk 输入；
- **仅参考，不搬代码**：PyBullet IK、bridge launch、PyBullet domain randomizer；
- **保持不动**：现有 PyBullet replay/risk 主线，避免为 Isaac 破坏下游职责。

---

## 7. 统一 Evaluation Contract 建议

### 7.1 `run_manifest.json`

```json
{
  "evaluation_run_id": "act_v0_isaac_nominal_20260718",
  "model_id": "act_scene_v0",
  "model_commit": "<git sha>",
  "dataset_release_id": "<release id>",
  "simulator_backend": "isaac",
  "simulator_version": "6.0.0.0",
  "scene_id": "panda_pick_place_v1",
  "suite": "nominal",
  "seeds": [0, 1, 2],
  "scenario_config_sha256": "<sha256>",
  "action_type": "ee_delta_gripper",
  "action_dim": 7
}
```

### 7.2 `episode_results.jsonl`

每行至少包含：

- identity：run/model/backend/scene/suite/seed/episode；
- outcome：success、failure_stage、failure_reason、timeout；
- subgoals：reach、grasp、lift、transport、place、release；
- motion：completion time、EE tracking RMSE/P95/max、path length、smoothness；
- contact/safety：collision count、drop/slip、peak FT、joint limit、E-stop；
- data health：missing/stale/reused frames、recorder Hz；
- system：physics FPS/RTF、CPU/RSS、GPU/VRAM、frame time；
- evidence：raw episode path、video path、log path。

### 7.3 `summary.json` 与报告

- overall 与 per-suite 成功率；
- subgoal conversion funnel；
- Wilson/bootstrap confidence interval；
- baseline checkpoint delta；
- failure reason Pareto；
- metrics by seed 与 flaky/repeatability；
- top failure videos；
- 数据增采、模型修改、仿真校准三类建议；
- 证据限制和 go/no-go 状态。

---

## 8. 第一版场景矩阵与指标

建议先使用单任务 ACT baseline，每个 suite 20 个固定 seed：

| Suite | 变化轴 | 主要指标 | 失败后建议方向 |
|---|---|---|---|
| nominal | 训练分布内位置 | overall/subgoal success | 模型或控制基本能力 |
| object_pose | x/y/yaw、边缘位置 | success by pose bin | 增采困难初态 |
| visual | light/material/background | grasp alignment failure | 视觉随机化/数据增强 |
| camera | extrinsic/FOV 小扰动 | reach/grasp drop | 标定鲁棒数据或视觉架构 |
| dynamics | mass/friction/damping | slip/drop/FT/tracking | 动力学随机化或控制增益 |

第一轮共 100 rollouts。阈值不应先拍脑袋设置；先产生 baseline 分布和置信区间，再定义 regression gate。

核心指标分六组：

1. **任务**：overall、pick、lift、place、timeout；
2. **阶段**：reach→grasp→lift→transport→place funnel；
3. **运动**：tracking、time、path、smoothness、joint margin；
4. **接触安全**：collision、drop/slip、peak FT、E-stop；
5. **泛化稳定性**：suite delta、seed variance、repeatability、CI；
6. **系统性能**：FPS/RTF、CPU/GPU/RAM/VRAM、frame drop、recorder Hz。

---

## 9. 底层内核、通信与控制实施约束

这部分不是后期性能优化，而是评测结果可重复、控制链不误动作的前置条件。当前项目已经具备部分基础，但还没有形成完整的 Isaac evaluation NFR gate。

### 9.1 当前已有代码事实

| 层 | 当前实现 | 证据与边界 |
|---|---|---|
| 控制周期 | `control_rate_sim.yaml`=`500`、`control_rate_real.yaml`=`1000`；`controllers.yaml` 仅默认值 | 仿真主线为 500 Hz 谐波候选；真机路径保留 1 kHz。配置了 update_rate ≠ 普通内核硬实时保证 |
| safety 周期 | `safety_monitor_node.cpp` 使用 4 ms wall timer，即 250 Hz | 已有 heartbeat/watchdog、limit、E-Stop 与 diagnostics |
| 仿真 backplane QoS | CANopen sim hardware 对 `/sim/joint_effort_cmd`、`/sim/encoder_state` 使用 `rclcpp::SensorDataQoS()` | 高频流选择最新数据、允许丢旧帧；Isaac 必须保持兼容 QoS |
| 状态/相机 QoS | MuJoCo、recorder sync 和 safety joint state 使用 sensor-data QoS | 需要在 Isaac publisher/subscriber 两侧做 compatibility preflight |
| 安全 QoS | `/safety/estop` 使用 reliable + transient-local；status/diagnostics 使用 reliable | 安全状态与高频传感器流不能使用同一 QoS 口径 |
| deadline | batch generator 和 Isaac adapter 多处使用 `time.monotonic()` | 已避免 wall clock 跳变影响 timeout；数据 header 仍使用 ROS clock |
| executor | Isaac adapter 使用 3-thread `MultiThreadedExecutor`；CANopen hardware 内部节点使用独立 executor thread | reset 等待、状态回调和诊断已有并发基础，但 callback group/锁竞争仍需专项验证 |
| telemetry | `SystemTelemetryNode` 以 1 Hz 发布整机/进程 CPU、RSS、affinity 与 recorder Hz | 已有采样能力，尚未自动写入 evaluation artifacts |
| 下游可靠性 | PolicyRunner health/watchdog、bridge command watchdog、comm health 与 latency benchmark | 可复用故障语义与验收形式，不能直接复制 PyBullet 阈值到 Isaac |

### 9.2 内核与调度边界

必须把两种运行模式分开：

1. **纯仿真评测**：普通 Ubuntu 内核可以运行，但只能声称测得的 latency/jitter/FPS；不能声称 hard real-time。重点是隔离 renderer、video encoder、DDS 与控制线程的资源竞争。
2. **真实机械臂或严格 HIL**：进入硬件准入前再要求 low-latency/PREEMPT_RT、realtime group、`SCHED_FIFO`、memory locking、CPU/IRQ affinity 与 `cyclictest` 证据。当前项目没有这些实测证据。

Isaac 本地/远程评测的最低约束：

- control/physics、policy inference、camera/encoding、ROS/DDS 分别记录线程/进程 CPU；
- 先观测后决定 affinity，不静态拍脑袋绑核；
- 控制线程不能执行视频编码、报告生成、磁盘 flush 或阻塞网络 I/O；
- 记录 scheduler policy、CPU affinity、kernel version、CPU governor 与容器权限；
- renderer/encoder 压力下仍需测 control update jitter、state age 和 command age。

### 9.3 控制环所有权与频率分层

```text
ACT inference / action chunk       低频（数据采样频率量级）
        ↓ latest valid command + timestamp
MoveIt Servo / command adapter     中频插值与限幅
        ↓ joint target / effort
ros2_control impedance loop        仿真 500 Hz / 真机 1 kHz
        ↓
MuJoCo or Isaac physics step       backend 自有 physics clock
```

硬规则：

- learned policy 不直接承担底层阻抗环（仿真 500 Hz / 真机 1 kHz）；
- action adapter 必须定义 sample-and-hold、插值、限幅和 chunk 中断语义；
- 新 command 超时后进入 HOLD/zero-effort/abort 中的已声明安全状态，不能无限重放旧 action；
- state 超龄、仿真 pause、reset 进行中或 QoS 未匹配时禁止下发新动作；
- reset 必须清理 policy chunk、adapter history、controller setpoint、watchdog 与时间基准；
- Isaac physics step 与 ROS publish rate 分开记录，不能用 camera FPS 代替控制频率。

### 9.4 ROS 2 QoS contract

| 数据面 | 建议 QoS | 原因 |
|---|---|---|
| `/sim/joint_effort_cmd` | 保持 SensorDataQoS / best effort / bounded depth | 高频命令宁可丢旧帧，不允许 reliable backlog 追发陈旧 effort；必须配 command watchdog |
| `/sim/encoder_state`、`/joint_states`、EE/FT/object pose | SensorDataQoS / best effort | 最新状态优先，统计 gap、age、jitter |
| camera topics | SensorDataQoS / best effort / 小队列 | 避免 renderer 或网络慢时反压控制链 |
| `/safety/estop` | reliable + transient local | 新加入节点必须立即获得当前 latch 状态 |
| diagnostics、health、evaluation events | reliable / bounded depth | 低频、不可静默丢失的状态与结论 |
| `/sim/reset_scene`、`EndEpisode` | reliable service + volatile | 事务操作需要请求/响应；避免服务重启后收到陈旧副作用请求 |
| static TF | transient local | late joiner 需要静态变换 |

每次 run 的 preflight 必须保存 `ros2 topic info -v` 输出并检查 offered/requested QoS。项目下游已经出现过 BEST_EFFORT publisher 与 RELIABLE subscriber 不兼容的历史问题，因此 QoS compatibility 不是理论项。

### 9.5 三类时钟与确定性

必须同时记录：

1. **simulation time/step**：物理推进与 seed 重现；
2. **ROS timestamp**：跨 topic 对齐、state/action age；
3. **monotonic host time**：timeout、wall latency、性能基准。

约束：

- duration/timeout 不使用可跳变的系统 wall clock；
- episode row 必须保留 simulation timestamp 与 observation/action 对齐关系；
- `use_sim_time`、`/clock` 是否启用要进入 run manifest；当前全链还没有完成 `/clock` 统一验证；
- 固定 seed 不代表 GPU physics bitwise deterministic，报告应保存 simulator/driver/hardware 和重复运行方差；
- reset 后首个有效 state 必须晚于 reset completion event，防止上一 episode 缓存污染。

### 9.6 单机与远程通信拓扑

正式远程 Isaac 评测不得把底层控制闭环（仿真 500 Hz / 真机 1 kHz）跨公网：

```text
远程 GPU 主机/同一低延迟局域网：Isaac + action adapter + policy + safety
                         │
                         ├─ 本地闭合控制与仿真回路
                         │
开发机：低频 orchestration、状态查看、artifact 下载、报告分析
```

多机运行必须固定：

- ROS 2 Jazzy/RMW implementation；
- 相同 `ROS_DOMAIN_ID` 与 Fast DDS profile；
- discovery/unicast/允许网卡，不依赖不可控公网 multicast；
- NTP/Chrony 状态；严格 HIL/真机才进一步要求 PTP；
- latency、jitter、packet loss、topic age 和 disconnect recovery；
- 每个并行 run 使用独立 domain/namespace，避免旧 participant 和缓存串线。

同机可利用 Fast DDS shared-memory transport 降低大消息开销，但必须通过实际 transport 配置和 benchmark 证明，不能因为“节点在同一台机器”就默认声称 zero-copy。跨主机后需要重新测 UDP 数据面，尤其是 RGB；控制关键路径应留在远端本机。

### 9.7 线程、队列与反压

- control/state callback 与 reset/service、camera、recorder callback 分组隔离；
- 图像队列保持有界，过载时丢旧帧并累计 dropped/stale 指标；
- video encode 与 episode flush 放到非控制线程，EndEpisode 等待有界；
- action/state 使用 latest-value 语义，不用无界 FIFO；
- 所有锁竞争和 callback duration 需要用 trace/performance samples 验证；
- policy inference 超时、异常或 NaN 必须触发 HOLD/abort 并记录 failure reason。

### 9.8 底层 NFR 验收证据

E0/E1 至少定义并在实际 run 中逐步产出：

```bash
uname -a
ps -eLo pid,tid,psr,cls,rtprio,pri,pcpu,comm --sort=-pcpu
taskset -pc <PID>
chrt -p <PID>
ros2 doctor --report
ros2 topic info -v /sim/encoder_state
ros2 topic info -v /sim/joint_effort_cmd
ros2 topic hz /joint_states
ros2 topic hz /camera/color/image_raw
ros2 topic echo /system/telemetry --once
pidstat -p ALL 1 60
nvidia-smi dmon -s pucvmt -d 1 -c 60
```

验收报告至少包含：command/state age P50/P95/max、control/state frequency、gap count、watchdog latency、reset recovery、CPU/GPU/RSS/VRAM、physics FPS/RTF，以及 QoS mismatch/disconnect 故障注入结果。

官方依据：

- [ROS 2 Domain ID](https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Domain-ID.html)：不同 logical network 隔离；
- [Fast DDS shared-memory transport](https://fast-dds.docs.eprosima.com/en/stable/fastdds/transport/shared_memory/shared_memory.html)：同机 SHM 的适用范围和限制；
- [Isaac ROS 2 Bridge](https://docs.isaacsim.omniverse.nvidia.com/latest/py/source/extensions/isaacsim.ros2.bridge/docs/index.html)：bridge 只在 simulation playback 时激活；
- [Isaac ROS 2 multi-machine FAQ](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/ros2_tutorials/ros2_faq.html)：RMW、Fast DDS profile 与 domain 必须一致。

---

## 10. 分阶段交付计划

### E0：评测契约文档

状态（2026-07-18）：**已实现并通过自动校验**。契约说明见
[`../EVALUATION_CONTRACT.md`](../EVALUATION_CONTRACT.md)，机器可读 schema 与不含实测值的
nominal fixture 见 `evaluation/schemas/`、`evaluation/examples/nominal_contract_fixture/`。

- 固定 run/episode/summary schema；
- 固定 suite、seed、provenance 和 evidence 路径；
- 明确物理成功只由 runtime ground truth evaluator 判定。
- 固定 QoS matrix、三类时钟、control/data plane 与线程所有权；
- 定义 stale command/state、DDS mismatch、reset timeout 和 policy timeout 的 fail-safe 语义；
- 定义 kernel/scheduler/transport/NFR 证据字段，但不虚构实时结果。

验收：JSON schema 示例可验证，三仓 ownership 无冲突，不改变运行行为。

### E1：Isaac action execution

状态（2026-07-18）：**action execution infrastructure 已实现并完成真实 Isaac 5-repeat
验收**。上游证据：`ros2-arm-teleoperation-suite/docs/ISAAC_E1_ACTION_EXECUTION.md` 与
`evidence/isaac_e1_action_execution_20260718_final/`。这不是 learned-policy rollout；相同
open-loop effort sequence 的 trajectory RMSE 最大 0.360 rad、终态 L2 最大 1.337 rad，
repeatability 风险已保留为后续闭环控制与 reset 完整性问题。

- 补齐 Isaac 对 policy action 的消费；
- 固定 action、reset、timeout、health 与 recorder 边界；
- 同一 action sequence 重复 5 次，记录终态和 tracking 差异。
- 实现有界 command watchdog、latest-command 语义与 reset history 清理；
- 验证 QoS compatibility、state/command age、callback 隔离和 renderer 压力下的 control jitter。

验收：真实 Isaac 日志、5 次结果、无后台残留；不声称 learned-policy success。

### E2：ACT 被测基线

- MuJoCo scene-only 采集约 50 条 accepted episode；
- 生成 immutable release；
- 训练单任务 ACT checkpoint；
- 保留离线 loss/RMSE 与限制声明。

验收：dataset inspection PASS、release manifest、checkpoint、episode-level validation；离线指标不外推任务成功率。

### E3：Isaac nominal rollout

- ACT checkpoint → Isaac action adapter；
- nominal 20 seeds；
- 自动 subgoal/outcome 结果与失败视频。
- 同时保存 transport、QoS、clock、CPU/GPU 与 command/state age 指标。

验收：**已完成（diagnostic）** — `evidence/e3_nominal20_home_30ep_gt_v1_20260719/`：
20×`episode_results.jsonl`、`summary.json`、失败视频；GT v1 与 `report state[7]` 对齐。
`go_no_go=no_go`（0/20 place）。旧 `invalid_evaluator_v0` 不计成功率。

### E3.5：Isaac scripted oracle（物理链门禁）

状态（2026-07-20）：**物理链门禁已通过（v2b）**。权威证据：
`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/` — lift **5/5**，
`oracle_gate.json` → `gate_pass=true` / `physics_chain_ok_focus_on_policy`。

完整实验过程（动机 → v1 失败 → 归因 → 修复 → v2b → 面试口述）见中游
[`E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md`](../E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md)。

- 上游入口：`scripts/run_isaac_scripted_oracle.sh` + `scripts/isaac_scripted_oracle.py`
- 控制面：`/teleop/cmd_pose` + gripper PD `apply_action` + heartbeat（**不**跑 ACT）
- FSM：approach_xy → hover → descend → close → grasp_pause → lift → hold
- 关键参数：`pick_z_offset=0.010`、`gripper_close_target=0.40`、红方块摩擦 2.0/1.5、
  GT `--gripper-close-max 0.70`（方块侧夹）
- v1 失败证据保留：`e3p5_isaac_scripted_oracle_5x_lift_20260720/`（lift 0/5）

验收：**已通过**。下一动作是补「对准→闭合→抬升」阶段数据 + 新模型 5-seed smoke；  
不声称 learned-policy 成功；暂不优先加 `observation.ft`；完整 E4 仍等小回归达标。

### E4：泛化与稳定性矩阵

状态：**文档规划为主；E3.5 已通过，但完整 100+ 仍等「对准→闭合→抬升」小回归达标后执行。**

- object/visual/camera/dynamics 四个额外 suite；
- 每 suite 20 seeds；
- 重复部分 seeds 检查稳定性；
- 生成 checkpoint delta 和 failure Pareto。

验收：100+ bounded rollouts、完整 provenance、CI、报告和增采建议。  
本机先每 suite 2–5 次 smoke；完整矩阵建议远程。

### E5：跨后端与下游复核

- 同一 model/scenario contract 比较 MuJoCo 与 Isaac；
- 选取代表 action stream 交下游 PyBullet replay/risk；
- 区分 task success、Sim2Sim shift 与 runtime risk。

验收：三份结果不混口径；下游保持 PyBullet 主线，无 Isaac API 入侵。

---

## 11. 本地与远程运行建议

本地 6 GB VRAM 设备用于：

- 单场景、单 episode 调试；
- 每 suite 2–5 次 smoke；
- ROS contract、reset、action adapter 与报告联调；
- MuJoCo 批量采集和本地 ACT 小 batch 训练。

远程 24 GB VRAM 级设备用于：

- Isaac 100+ rollouts；
- Replicator 多场景随机化；
- 同时保存视频、FT、系统 benchmark；
- 多 checkpoint、多 seed 回归。

远程 Isaac runtime 与普通 ROS 2 工作区继续解耦；数据通过 episode/evaluation contract 交接，而不是复制整个开发环境。

Isaac 官方可复用能力：

- [Replicator domain randomization](https://docs.isaacsim.omniverse.nvidia.com/5.0.0/py/source/extensions/isaacsim.replicator.domain_randomization/docs/index.html)：reset/interval 触发的物理与场景随机化；
- [Benchmark Services](https://docs.isaacsim.omniverse.nvidia.com/6.0.0/py/source/extensions/isaacsim.benchmark.services/docs/index.html)：CPU、GPU、内存和 frame time 的阶段化 benchmark；
- [Isaac Sim requirements](https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html)：当前最低 VRAM 规格高于本地 6 GB，因此正式批量运行优先远程。

---

## 12. 与真实工业评测平台的剩余差距

下面的差距按“当前仓库是否已有代码/证据”判断，不按文档中是否出现相关名词判断。工业界要求也因企业、机器人类型和应用风险等级而不同，本节不声称项目需要或已经通过任何认证。

### 12.1 评测可信度差距

| 缺口 | 当前项目状态 | 工业平台通常要求 | 本项目可执行补强 |
|---|---|---|---|
| 测量基准与不确定度 | P5 已发现 joint/object/camera/FT 不对齐，但尚无 calibrated golden scene | TCP、相机内外参、hand-eye、FT bias/frame、物体真值和误差预算可追溯 | 新增 calibration manifest、golden scene、重复测量和 drift check |
| 仿真有效性 | 有 MuJoCo/Isaac/PyBullet 对比，但缺少真值校准 | 用实测或可信基准校准质量、摩擦、阻尼、传感器噪声，并记录适用域 | 先做 cross-backend consistency；无真机时明确“未校准到真实硬件” |
| 统计设计 | 规划每 suite 20 seeds，但未做样本量/检验力设计 | 预注册指标、样本量、置信区间、multiple comparison、rare-event 口径 | baseline 后按观察方差计算样本量；报告 Wilson/bootstrap CI |
| 场景覆盖追踪 | 有 suite 设计，尚无 requirement→case→metric→gate traceability | 每项需求映射测试、风险、责任人、版本和缺陷单 | 新增 coverage matrix 与唯一 test-case ID |
| 评测器自身验证 | evaluator 尚未实现 | oracle、label、metric 也要单测、负对照、人工抽检和双实现核对 | 为 task/subgoal evaluator 准备合成正负样例与 golden results |
| 数据泄漏与污染 | episode split 已有基础 | 禁止同 seed/近重复轨迹跨 train/eval，保留 hidden test 和去重证据 | 按 scene/seed/object pose 分组切分，增加 hash/near-duplicate audit |

### 12.2 模型生命周期与回归差距

| 缺口 | 当前项目状态 | 工业平台通常要求 | 本项目可执行补强 |
|---|---|---|---|
| 模型注册与签名 | checkpoint 有文件但没有统一 registry | model id、commit、训练配置、dataset lineage、checksum、审批状态 | 将 model card/checksum 写入 run manifest |
| 自动回归 | 尚无 checkpoint A/B 的 Isaac rollout | 每次模型、数据、仿真器或驱动升级触发固定 suite | `compare_checkpoints.py` 输出 per-slice delta 与 regression list |
| 准入与回滚 | 只有设计中的 go/no-go | 明确 hard gate、warning、waiver、canary 和上一稳定版本回滚 | baseline 后再校准阈值；保留 signed decision record |
| shadow/canary | 无真实 runtime | 新模型先 shadow、限速、低风险工位或少量设备验证 | 仿真中先做 shadow action comparison；不冒充真实 canary |
| 兼容性矩阵 | provenance 已有部分字段 | OS/kernel/driver/CUDA/Isaac/ROS/RMW/model 组合可查询 | 保存 environment lock、GPU/driver 和 RMW profile hash |

### 12.3 可靠性、恢复与运维差距

| 缺口 | 当前项目状态 | 工业平台通常要求 | 本项目可执行补强 |
|---|---|---|---|
| 长稳与资源泄漏 | 当前主要是秒/分钟级 bounded smoke | 2h/8h/24h soak、RSS/VRAM/file descriptor/disk trend | 先做 2h headless soak，再决定是否远程扩展 |
| supervisor 与自动恢复 | 有退出清理和 watchdog，跨进程 supervisor 证据不足 | 进程崩溃检测、受控重启、次数限制、状态恢复、避免重启动作 | 注入 kill/hang/OOM/disk-full，验证 HOLD 与幂等 reset |
| 故障矩阵 | 有部分 safety/risk fault tests | 网络延迟/丢包、相机断流、state stale、NaN action、GPU/renderer 卡顿、写盘失败 | 建立 fault campaign manifest 与 recovery time 指标 |
| 可观测性 | ROS diagnostics、JSON/HTML 报告已存在 | 统一 run id、结构化日志、trace、指标留存、告警和跨机时间关联 | run id 注入所有日志/episode；保存 rosbag/trace 的索引和保留策略 |
| 容量规划 | 有单机 CPU/GPU telemetry | 最大并发、吞吐、存储增长、编码带宽、远程成本与队列容量 | 输出 episodes/hour、GB/hour、GPU-hours 和失败重试成本 |
| 发布工程 | 三仓仍以本地工作区为主 | immutable image、依赖/SBOM、artifact registry、灰度和回退 | 固定 Isaac runtime image/venv lock 与三仓 commit manifest |

### 12.4 功能安全、网络安全与现场流程差距

| 缺口 | 当前项目状态 | 工业平台通常要求 | 求职作品边界 |
|---|---|---|---|
| 独立功能安全链 | 软件 E-Stop、DS402 Quick Stop、limits 已有实现/仿真证据 | 风险评估后由 safety PLC、STO、双通道急停、防护门等独立于 AI/普通 ROS 实现 | 说明 AI、ROS risk score 不是认证安全功能；不声称 PL/SIL |
| 安全等级与验证 | 无 PLr/PL/SIL 计算和硬件证据 | 依据应用做 ISO 12100 hazard analysis、ISO 10218 集成、ISO 13849 SRP/CS 验证 | 可以做 hazard log/FMEA 映射，不个人伪造认证 |
| 网络安全 | 当前主要依赖 domain/profile 隔离 | 身份认证、最小 topic/service 权限、加密、密钥轮换、远程访问审计 | 规划 SROS2 enclave、signed artifacts、secret 管理与 audit log |
| 供应链安全 | 未形成 SBOM/漏洞扫描 | 锁定依赖、镜像签名、CVE/SBOM、第三方 USD/模型许可 | 为 demo 生成 dependency lock、checksum 和 asset license manifest |
| 操作员与现场 SOP | 有部分 runbook/报告模板 | 上电/复位/换型/急停/故障恢复/人工接管/培训与权限分级 | 新增 operator checklist；明确哪些动作必须人工确认 |
| 事件与缺陷闭环 | 有结构化建议模板 | severity、owner、SLA、复现包、root cause、CAPA、关闭证据 | failure cluster 自动生成 issue-ready bundle，不连接外部工单也可展示 |

机器人安全要求不仅是“代码里有 E-Stop”。ISO 10218-1:2025 面向工业机器人本体，ISO 10218-2:2025 面向集成和机器人单元；ISO 13849-1:2023给出 safety-related control system 的设计与验证方法。当前项目没有做上述认证，也不应在简历中暗示已认证。

### 12.5 对求职的优先级

#### 必须补，直接决定评测岗位说服力

1. 一个真正可执行的 Isaac policy rollout；
2. golden scene/calibration manifest 与 evaluator 正负样例；
3. 100 次左右分层 rollout、置信区间和 failure slice；
4. checkpoint A/B regression 与结构化改进建议；
5. 至少一轮通信/传感器/policy timeout 故障注入；
6. 2 小时 headless soak 和资源趋势报告。

#### 建议补，体现工程成熟度

1. model/dataset/simulator/environment checksum；
2. requirement→test→metric→gate coverage matrix；
3. run id、结构化日志、失败视频和复现包；
4. 容量/成本指标；
5. shadow action comparison 和回滚记录。

#### 理解并能讲清，不要求个人完成

1. ISO 10218、ISO 12100、ISO 13849 与 PL/SIL 的边界；
2. safety PLC/STO/防护门等独立安全链；
3. SROS2/IEC 62443、PKI、密钥和远程访问审计；
4. 真机计量标定、第三方认证和工厂验收；
5. 企业级模型仓库、工单、审批和 fleet canary。

### 12.6 工业化完成定义

作品集不需要冒充量产系统。对该岗位，一个可信的完成定义是：

> 在固定 model/dataset/simulator/environment 身份下，用已验证 evaluator 对可复现场景矩阵执行 learned-policy rollout；报告置信区间、失败切片、系统性能和恢复行为，并能把问题转成可追溯的数据增采、模型修改或平台修复建议。

这符合 NIST TEVV 对 objective、repeatable、documented measurement 的方向；但它仍是仿真评测工程证据，不是工业机器人安全认证。

官方参考：

- [ISO 10218-1:2025](https://www.iso.org/standard/73933.html)：工业机器人安全要求；
- [ISO 13849-1:2023](https://www.iso.org/standard/73481.html)：安全相关控制系统设计与验证；
- [ISO 12100:2010](https://www.iso.org/standard/51528.html)：机械风险评估与风险降低方法；
- [ISO 9283:1998](https://www.iso.org/fr/standard/22244.html)：工业机器人性能指标与测试方法；
- [NIST AI RMF Measure/TEVV](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)：客观、可重复、可扩展且有记录的评测流程；
- [ROS 2 SROS2 keystore](https://docs.ros.org/en/ros2_documentation/jazzy/Tutorials/Advanced/Security/The-Keystore.html)：DDS security identity、permissions 与 enclave。

---

## 13. 面试叙事

### 当前版本

> 我在三仓架构中保留 MuJoCo 作为快速采集与回归后端，新增 Isaac Sim 6.0 Panda 高保真 PoC，并通过 backend-neutral ROS contract 复用 recorder 和中游 schema。随后用 matched episode 比较 joint、EE、object、FT、RGB 与时序分布，发现相同 scene_id 下初态、传感器语义和相机外观并未真正对齐，并把问题转化为 joint/object/camera/FT 的校准顺序。当前结论只标记为 Sim2Sim evidence，不冒充任务成功或 Sim2Real。

### 完成 E1–E4 后

> 我设计了 Isaac Sim 具身操作模型评测平台，以 model/dataset/scene/seed manifest 保证可追溯，用 object、visual、camera、dynamics 四类扰动形成分层场景矩阵；系统自动执行 ACT rollout，统计 overall/subgoal success、tracking、contact safety、repeatability 和系统性能，并输出 checkpoint regression、failure Pareto、失败视频及数据增采建议。

该叙事直接对应岗位的“可重复、可比较、可量化、结构化报告、问题闭环”，同时不虚构真机经验。

---

## 14. E0 历史范围与当前下一步

E0 最小 PR 的历史完成范围如下：

1. 新增 evaluation run/episode/summary contract 文档与 JSON schema；
2. 给出 nominal suite 示例和 3 个固定 seed；
3. 明确上游 runtime、中游 aggregation、下游 risk 的 ownership；
4. 固定 QoS、clock、thread/control ownership 与 fail-safe NFR contract；
5. 为未来 Isaac action execution 预留字段，但不声称已经执行模型；
6. 不改 recorder raw schema、不改 ACT 主线、不改 PyBullet replay 主线。

E0/E1 已完成；下一阶段进入 E2 的 ACT 被测基线，E3 才把 checkpoint 接入 Isaac nominal
rollout 和 runtime ground-truth task evaluator。
