# Policy Runtime Integration SPEC

**版本**：v0.1  
**状态**：M0–M6 implementation complete（2026-07-26）；M6 mock-policy ROS wiring Pass；authoritative SmolVLA cutover 未启用  
**日期**：2026-07-26  
**Canonical owner**：`robot-arm-episode-data-lab`（跨仓合同、schema、验收口径）  
**涉及仓库**：

- 上游：`ros2-arm-teleoperation-suite`
- 中游：`robot-arm-episode-data-lab`
- 下游：`ros2-moveit-pybullet-bridge`

**项目边界**：Not task success / Not Sim2Real / Not real robot。本文只定义如何把高层策略、上游实时执行与下游监控安全框架接成同一条可审计运行链；不授权训练、重训、扩 Isaac seed、真机或修改 `eval_gate_v3`。

关联合同：

- [Policy Adapter Contract](POLICY_ADAPTER_CONTRACT.md)
- [Panda Absolute EEF Contract](VLA_GATE_V05_PANDA_ACTION_CONTRACT.md)
- [SmolVLA v3 Evaluation SOP](SMOLVLA_V3_EVAL_SOP.md)
- [S4 Runtime Contract](../configs/smolvla_s3/s4_runtime_contract.yaml)
- [Future Work Roadmap](FUTURE_WORK_ROADMAP.md)
- [Policy Runtime × HOC Implementation Roadmap](POLICY_RUNTIME_HOC_IMPLEMENTATION_ROADMAP.md)

---

## 0. 一句话决策

> **建立一条模型无关的 Policy Runtime：大脑只产出带明确语义和生命周期的 `PolicyCommand`，小脑是唯一执行入口，Safety Supervisor 独立决定 Run / Hold / E-stop，同一份命令与执行报告可被下游复放和审计。**

这是目标架构，不受旧仓接口限制。结合当前三仓，Policy Runtime 与小脑落在上游、合同和验收口径落在中游、replay / risk 落在下游；这是职责匹配后的部署结果，不是设计起点。旧 `PolicyRunner` 和 `ee_delta_gripper[7]` 只作为兼容后端，不反向塑造新主线；risk 也不覆盖任务 GT。

### 0.1 最顺的讲述顺序

1. **输入**：机器人状态、末端状态、夹爪和图像被组装为策略自己的 observation。
2. **大脑**：SmolVLA / ACT / Oracle 只负责生成原生动作 chunk，不直接控制机器人。
3. **运行时**：Scheduler 把 chunk 变成逐控制周期、可追踪、可过期的 `PolicyCommand`。
4. **小脑**：唯一 Execution Adapter 完成动作语义转换、限幅、时效校验并下发控制器。
5. **安全闭环**：独立 Safety Supervisor 根据执行遥测和风险状态决定 Run / Hold / E-stop。
6. **证据闭环**：原始动作、实际执行动作、裁剪、时延与任务 GT 分开记录；相同记录可交给下游 replay。

面试主线可压缩成一句话：**我不是只训练一个策略，也不是只写一个控制器；我定义了连接策略智能与机器人执行的运行时合同，并让动作、安全和评测证据在同一条链上闭环。**

---

## 1. 背景与当前断点

### 1.1 已实现链 A：SmolVLA 上游在线执行

```text
/sim/encoder_state + /ee_pose + /gripper/state + scene RGB
  → compose_state15
  → SceneSmolVLARuntime.select_action
  → absolute_eef_gripper[8]
  → workspace / gripper clamp
  → /teleop/cmd_pose + /teleop/gripper_cmd
  → safety monitor / controller / Isaac
  → ContinuousTaskEvaluator task GT
```

代码入口：上游 `isaac_sim_adapter/smolvla_policy_inference_node.py`。

### 1.2 已实现链 B：下游 replay / monitor / risk

```text
bridge_handoff/predicted_actions.jsonl
  → JsonlActionReplayPolicy
  → ee_delta_gripper[7]
  → PandaActionAdapter
  → /bridge/command
  → PyBullet bridge
  → dist_monitor
  → risk_engine
  → /risk/status
```

代码入口：下游 `PolicyRunner`、`PandaActionAdapter`、`DistMonitorNode`、`RiskEngineNode`。

### 1.3 当前只有离线复用

中游已能把 SmolVLA open-loop `absolute_eef_gripper[8]` 序列转成 `ee_delta_gripper[7]` handoff，再交给下游 replay；该路径明确 `is_closed_loop=false`。

当前 unified report 只是将两条链的产物做事后聚合，并非在线 runtime bus。

### 1.4 四个结构性断点

| 断点 | 上游 SmolVLA | 下游旧框架 | 后果 |
|---|---|---|---|
| Observation | `state[15] + scene RGB + EE + gripper` | joint position / velocity 为主 | 下游不能直接托管当前 VLA 推理 |
| Action semantics | `absolute_eef_gripper[8]` | `ee_delta_gripper[7]` | 离线转换不能代表在线等价 |
| Command sink | `/teleop/cmd_pose` + `/teleop/gripper_cmd` | `/bridge/command` JointTrajectory | 两套执行状态机并行 |
| Safety / health | `/safety/status`、`/safety/estop`、policy JSON status | `/risk/status`、`/system_health` | 下游 risk 没有反馈到当前 SmolVLA 执行路径 |

---

## 2. 目标与非目标

### 2.1 必须实现

1. 同一策略合同支持 `absolute_eef_gripper[8]` 与 `ee_delta_gripper[7]`，禁止静默切片或隐式重解释。
2. 策略推理、动作调度、执行适配、安全监督和任务 GT 分层。
3. SmolVLA、ACT、scripted oracle 可挂同一 `PolicyBackend`，但保留各自原生 observation/action 语义。
4. 上游实时执行路径消费单步 `PolicyCommand`，执行层统一负责 workspace、gripper、TTL、sequence 和安全检查。
5. 下游 dist/risk 能观测上游在线状态，并将 R2/R3 映射为 Hold/E-stop。
6. 保留下游 handoff replay，并允许记录后的 `PolicyCommand` 在 PyBullet 中复放。
7. 每一步都输出 `trace_run_id`、episode、sequence、latency、clip 和 failure lane。

### 2.2 明确不做

- 不把 PyBullet 下游改成 VLA 主评测宿主。
- 不把 risk R-level 当作 reach/grasp/lift/place 判定。
- 不改变 `eval_gate_v3` 或历史 Pass/Hold。
- 不为接线重训 SmolVLA、ACT 或采集新数据。
- 不新增 Isaac seeds，不把 wiring smoke 写成任务成功。
- 不自动恢复 LingBot 或下载 6B 权重。
- 不在实时 command path 传输完整图像；图像留在 Policy Runtime 进程内。

---

## 3. 设计原则

### P1：原生语义先于后端适配

策略输出必须先声明 `action_schema_version`，然后由执行后端显式适配。任何 `absolute → delta` 或 `task-space → joint-space` 转换都必须记录 adapter 名称、版本与输入状态。

### P2：唯一执行权威

上游 `PandaPolicyExecutionAdapter` 是实时命令的唯一发布者。PolicyBackend、下游 PolicyRunner 和 Risk Engine 都不得直接并发发布 `/teleop/cmd_pose`。

### P3：安全权威与任务权威分离

- Risk/Safety 可以 Hold、降速或 E-stop。
- 只有上游 ContinuousTaskEvaluator 可以判定物理 task GT。
- Risk 不得把 `failure_lane` 从 `task_gt` 改写为其它类别。

### P4：Fail closed

未知 action schema、NaN/Inf、过期 TTL、sequence 回退、observation stale、policy timeout 或 contract hash 不一致时，默认 Hold；严重错误触发 E-stop，绝不“尽量执行”。

### P5：先 shadow，后切流

新旧路径先并行计算但只允许旧路径执行；通过逐步命令一致性检查后，才切换新 adapter 为唯一命令源。

### P6：权威合同 + SHA 锁定镜像

中游保存 canonical schema 与 lock；上游、下游只保存 byte-identical runtime copy，并在启动时校验 SHA256。

---

## 4. 目标架构

```mermaid
flowchart LR
    OBS[上游 Observation Collector<br/>joint + EE + gripper + RGB] --> BACKEND[PolicyBackend<br/>SmolVLA / ACT / Oracle]
    BACKEND --> CHUNK[ActionChunkEnvelope<br/>native semantics]
    CHUNK --> SCHED[Chunk Scheduler<br/>sync / async double-buffer]
    SCHED --> CMD[PolicyCommand<br/>one command per control tick]
    CMD --> EXEC[上游 PandaPolicyExecutionAdapter<br/>TTL + seq + clamp + mapping]
    EXEC --> CTRL[teleop / Servo / controller / Isaac]
    EXEC --> REPORT[PolicyExecutionReport]

    CTRL --> GT[ContinuousTaskEvaluator<br/>task GT only]
    CTRL --> STATE[online joint / tracking telemetry]
    STATE --> DIST[下游 dist_monitor]
    REPORT --> HEALTH[Runtime health adapter]
    DIST --> RISK[下游 risk_engine]
    HEALTH --> RISK
    RISK --> RS[/risk/status]
    RS --> BRIDGE[下游 RiskToSafetyBridge]
    BRIDGE --> HOLD[/policy/runtime_hold]
    BRIDGE --> ESTOP[/safety/trigger_estop]
    HOLD --> EXEC
    ESTOP --> CTRL

    CMD -.recorded JSONL.-> REPLAY[下游 PolicyCommand replay]
    REPLAY --> PYB[PyBullet execution-validation]
```

关键点：**大脑输出 PolicyCommand；小脑执行和安全层决定是否、如何执行；任务 GT 独立旁路判定。**

---

## 5. 合同模型

### 5.1 版本与支持矩阵

| 项 | 值 |
|---|---|
| Runtime contract | `panda_policy_runtime_v1` |
| Observation schema | 策略身份卡声明，不强制统一维数 |
| Supported action schema A | `panda_absolute_eef_gripper_v0`，dim=8 |
| Supported action schema B | `panda_ee_delta_gripper_v0`，dim=7 |
| Runtime rate | 由 policy runtime contract 声明；Recovery v3 为 10 Hz |
| Control command rate | 上游执行层参数；与 inference rate 分离 |
| Task success claim | 恒为 false；GT 另行关联 |

### 5.2 `PolicyBackend` 方法集

中游定义方法语义，上游实现具体 backend：

```python
class PolicyBackend(Protocol):
    def load(self, artifact: PolicyArtifact) -> None: ...
    def reset(self, context: EpisodeContext) -> None: ...
    def build_observation(self, raw: RawObservation) -> ModelObservation: ...
    def predict_chunk(self, observation: ModelObservation) -> ActionChunkEnvelope: ...
    def health(self) -> PolicyHealth: ...
    def close(self) -> None: ...
```

相对现有 `PolicyAdapter` v0 的变化：

- `predict_action` 升级为 `predict_chunk`，明确 chunk 语义。
- `export_action` 不再固定转换为 `ee_delta_gripper[7]`。
- backend 返回 lossless native `ActionChunkEnvelope`。
- schema 转换移到具名 Execution Adapter。
- 旧 handoff 可继续使用显式 `AbsoluteEefToDeltaReplayAdapter`，但只用于离线 replay。

### 5.3 `ActionChunkEnvelope`

```yaml
contract_version: panda_policy_runtime_v1
trace_run_id: string
episode_id: string
observation_sequence: uint64
policy_name: string
policy_version: string
checkpoint_hash: sha256 | sentinel
observation_schema_version: string
action_schema_version: panda_absolute_eef_gripper_v0 | panda_ee_delta_gripper_v0
actions: float64[N][D]
chunk_size: uint32
execute_k: uint32
inference_started_monotonic_ns: uint64
inference_finished_monotonic_ns: uint64
inference_latency_ms: float64
claims_task_success: false
```

不变量：

- `N == chunk_size`；`1 <= execute_k <= chunk_size`。
- absolute schema 要求 `D=8`；delta schema 要求 `D=7`。
- 全部数值 finite。
- `observation_sequence` 不能倒退。

### 5.4 `PolicyCommand`

Scheduler 每个 control tick 只发一个单步命令：

```yaml
header.stamp: ROS time
contract_version: panda_policy_runtime_v1
trace_run_id: string
episode_id: string
command_sequence: uint64
source_observation_sequence: uint64
action_schema_version: string
action: float64[D]
chunk_index: uint32
chunk_size: uint32
from_prefetched_chunk: bool
inference_latency_ms: float64
valid_until: ROS time
claims_task_success: false
```

执行前必须检查：contract、dim、finite、sequence、TTL、hold、E-stop、workspace。

### 5.5 `PolicyExecutionReport`

```yaml
header.stamp: ROS time
trace_run_id: string
episode_id: string
command_sequence: uint64
accepted: bool
decision: executed | held | rejected | estopped
reason: string
source_action_schema_version: string
execution_action_schema_version: string
source_action: float64[]
bounded_action: float64[]
clipped: bool
clip_axes: string[]
hold_active: bool
estop_active: bool
adapter_name: string
adapter_version: string
```

### 5.6 Runtime health

使用 `diagnostic_msgs/DiagnosticArray`，至少包含：

- `policy_loaded`
- `observation_age_ms`
- `inference_busy`
- `inference_latency_ms_last/p50/p95`
- `queue_depth`
- `queue_underrun_count`
- `deadline_miss_count`
- `last_command_sequence`
- `last_successful_command_age_ms`
- `hold_active`
- `estop_active`
- `contract_sha256`
- `failure_lane`

健康状态不包含 task success。

---

## 6. ROS 2 接口

### 6.1 消息所有权

为避免重复定义：

- `PolicyCommand.msg`、`PolicyExecutionReport.msg` 放入上游现有 `teleop_interfaces`，因为实时执行接口归上游。
- `RiskStatus.msg` 继续由下游 `bridge_monitor_msgs` 所有。
- 中游保存对应 JSON Schema 与 SHA lock，不编译 ROS package。
- 下游 `RiskToSafetyBridge` 依赖 `teleop_interfaces`；上游不依赖 `bridge_monitor_msgs`，避免构建环。

### 6.2 Topic / service

| 接口 | 类型 | Producer | Consumer | 语义 |
|---|---|---|---|---|
| `/policy/command` | `teleop_interfaces/PolicyCommand` | 上游 Policy Runtime | 上游 Execution Adapter；可选下游 recorder | 单步原生动作 |
| `/policy/execution_report` | `teleop_interfaces/PolicyExecutionReport` | 上游 Execution Adapter | health adapter / evidence recorder | 执行裁决 |
| `/policy/runtime_health` | `DiagnosticArray` | 上游 Policy Runtime | 下游 Risk adapter / recorder | 推理与 queue 健康 |
| `/policy/runtime_hold` | `std_msgs/Bool` | 下游 RiskToSafetyBridge | 上游 Execution Adapter | R2 Hold 状态 |
| `/risk/status` | `bridge_monitor_msgs/RiskStatus` | 下游 risk_engine | 下游 RiskToSafetyBridge | R0–R3 风险 |
| `/safety/trigger_estop` | `teleop_interfaces/TriggerEstop` | 下游 RiskToSafetyBridge client | 上游 safety_monitor | R3 单向 E-stop 请求 |
| `/teleop/cmd_pose` | `PoseStamped` | 上游 Execution Adapter | safety_monitor / controller | 现有执行接口，保持不变 |
| `/teleop/gripper_cmd` | `Float64` | 上游 Execution Adapter | gripper path | 现有执行接口，保持不变 |

兼容窗口内保留 `/policy/inference_status`，但标记 deprecated；新 consumer 使用结构化 command/report/health。

### 6.3 QoS

| 数据 | Reliability | History / depth | 说明 |
|---|---|---|---|
| `PolicyCommand` | reliable | keep_last=1 | 不执行陈旧队列；TTL 二次保护 |
| `PolicyExecutionReport` | reliable | keep_last=20 | 供审计，不进硬实时控制 |
| Runtime health | reliable | keep_last=10 | Risk 必须看到超时状态 |
| Hold | reliable + transient_local | keep_last=1 | 新启动节点立即看到当前 Hold |
| 图像 / joint sensor | best_effort | keep_last=1/10 | 沿用现有传感 QoS |

### 6.4 HOC 可观测性合同

当前 HOC 面向旧下游 replay：展示综合 R0–R3、五维 risk radar、KL/W1/MMD、tracking、资源和 grasp status。它没有订阅 `PolicyCommand`、`PolicyExecutionReport`、`/policy/runtime_health` 或上游 task GT，因此不能回答“是大脑没产出、scheduler 断粮、小脑拒绝执行，还是任务物理失败”。

目标 HOC 不建立“大脑风险分”和“小脑风险分”两个互相竞争的总分。**大脑与小脑输出可解释 health signals，Safety Supervisor 统一产生唯一 R0–R3 和 Run/Hold/E-stop 决策，Task GT 独立展示。**

#### 6.4.1 四个固定泳道

| 泳道 | 必显状态 | 核心指标 | 数据源 | 不得解释为 |
|---|---|---|---|---|
| **Brain / Policy** | `OK / WARN / ERROR / STALE` | policy/checkpoint、observation age/valid、inference p50/p95、deadline miss、queue depth/underrun、native action finite/schema | `/policy/runtime_health` + command metadata | task success、物理安全 |
| **Cerebellum / Execution** | `EXECUTED / HELD / REJECTED / ESTOPPED` | command seq/TTL、raw→bounded action、clip axes/rate、tracking RMSE、soft-limit、adapter version | `/policy/execution_report` + execution telemetry | 策略智能水平 |
| **Safety Supervisor** | `R0 / R1 / R2 / R3` + `RUN / HOLD / E_STOP` | primary driver、source validity、distribution/tracking/dynamics/comm/planning/resource、decision reason、latched state | `/risk/status` + Hold/E-stop state | reach/grasp/lift/place GT |
| **Task GT** | `RUNNING / PASS / FAIL / UNAVAILABLE` | phase、reach、grasp、lift、place、object Δ、GT source | 上游 evaluator 的结构化状态镜像 | risk readiness、offline loss |

#### 6.4.2 顶部必须一眼回答的问题

顶部状态条只展示一个最终执行裁决，并串出原因链，例如：

```text
HOLD ← policy.queue_underrun ← inference deadline miss
RUN  ← all required sources valid
E_STOP ← execution.soft_limit_triggered
```

任意数值还必须带 `VALID / WARMING_UP / STALE / UNAVAILABLE`；缺消息、baseline 未 ready 或样本不足时显示灰色不可用，禁止用绿色 `0 / 正常` 代替。

#### 6.4.3 HOC 最小改造面

1. 后端新增订阅 `/policy/runtime_health`、`/policy/execution_report` 和上游 task GT 状态镜像。
2. WebSocket 分别推送 `policy_health`、`execution_report`、`risk_status`、`task_gt`，禁止揉成一个无 provenance 的 score。
3. 前端新增 `BrainPanel`、`ExecutionPanel`、`SafetyDecisionBanner`、`TaskGtPanel`；旧 `DistributionPanel` 下沉到 Execution diagnostics。
4. 旧静态 `CanonicalRunPanel` 明确标记为历史 portfolio evidence，不得与本次 live run 混排。
5. report export 按四个泳道保存时间线，并用 `trace_run_id + episode_id + command_sequence` 串联。

---

## 7. 动作适配职责

### 7.1 上游 `PandaPolicyExecutionAdapter`

支持：

| 输入 schema | 映射 | 状态 |
|---|---|---|
| `panda_absolute_eef_gripper_v0` | position + quaternion + gripper → bounded PoseStamped / Float64 | Recovery v3 主线 |
| `panda_ee_delta_gripper_v0` | 基于最新 measured EE pose 合成绝对目标，再统一 bound | ACT/oracle 兼容 |

执行顺序固定：

1. contract / sequence / TTL
2. finite / dimension
3. schema-specific conversion
4. workspace / gripper clamp
5. joint / EE excursion guard
6. Hold / E-stop arbitration
7. publish existing teleop topics
8. emit `PolicyExecutionReport`

禁止 backend 自己做最终安全裁剪后再隐瞒 raw action。

### 7.2 下游 replay adapter

- 保留 `PandaActionAdapter` 的 `ee_delta_gripper[7]` 支持。
- 新增独立 `PandaAbsoluteEefReplayAdapter`，不要把 absolute 逻辑塞入现有 delta 类。
- replay 输入必须带 `action_schema_version`。
- `PolicyCommand` JSONL replay 始终 `is_closed_loop=false`，除非下游未来实现真实 observation feedback；当前 SPEC 不包含该升级。

---

## 8. Risk → Hold / E-stop 状态机

### 8.1 映射

| Risk | Runtime 动作 | 自动恢复 |
|---|---|---|
| R0 | RUN | — |
| R1 | RUN + warning | 是 |
| R2 或 `degraded_mode=true` | HOLD：停止消费新 command，保持 measured EE 与当前 gripper | 连续健康 N 次后允许；N 可配置，默认 5 |
| R3 或 `e_stop_active=true` | 调 `/safety/trigger_estop`；保持 HOLD | **否**；必须走现有人工 reset/ack 流程 |

### 8.2 单向依赖

`RiskToSafetyBridge` 放在下游：

```text
bridge_monitor_msgs/RiskStatus
  ├─ publish std_msgs/Bool /policy/runtime_hold
  └─ call teleop_interfaces/TriggerEstop /safety/trigger_estop
```

上游只依赖标准 Bool 和自己的 `teleop_interfaces`，不反向依赖下游消息包，因此 package build graph 不成环。

### 8.3 Hold 语义

- Hold 不重放最后一个运动目标。
- 进入 Hold 时，以最新 measured EE pose 生成零运动目标。
- 夹爪保持最新 measured gripper state，避免自动张开导致掉落。
- Hold 期间丢弃过期 command；恢复后必须基于新 observation 重新规划。
- R3 后不允许自动恢复。

### 8.4 KL 的保留边界

下游现有 KL **保留，但只定义为执行域分布漂移诊断**：比较健康基线窗口中的逐关节双源跟踪误差分布 (P) 与当前窗口误差分布 (Q)。它回答“当前执行残差是否偏离已标定健康状态”，不回答“VLA 是否理解图像”“动作是否正确”或“任务是否成功”。

启用 KL 前必须同时满足：

1. 两路数据代表同一机器人、同一关节顺序、同一任务阶段，并已完成时间对齐。
2. 健康 baseline 已采满并带 calibration id；阈值来自相同 Panda 场景的标定，不复用 legacy / synthetic 常数。
3. `metric_valid=true`、`baseline_ready=true`、样本数达到 `min_samples`。
4. Risk Engine 只把有效 KL 作为 `distribution_shift` 的一个输入，并与 W1、MMD、tracking error 分栏解释。

任一条件不满足时，KL 必须报告 `unavailable`，不得写成 `0.0 / no shift`。当前 `DistributionMetrics.msg` 尚无 `metric_valid` 和 `baseline_ready`，而 monitor 在样本或基线未就绪时会发布默认零值；M3 必须先补这两个字段并让 benchmark/offline readiness 传播有效性，再允许 KL 驱动 Hold。

本 SPEC 不用 KL 衡量 `state[15] + RGB` 的策略输入漂移。未来若要监控 VLA observation drift，应另定义视觉 embedding / state distribution 合同，不能复用逐关节误差 KL 的名称和阈值。

---

## 9. Chunk 与异步调度

Recovery v3 合同保持 `chunk_size=10`、`execute_k=5`、10 Hz、replan 0.5 s。

### 9.1 所有权

- PolicyBackend：生成完整 chunk。
- Scheduler：消费 K、预取下一 chunk、管理 reset/underrun。
- Execution Adapter：只看单步 PolicyCommand，不知道模型内部 chunk。

### 9.2 Async double-buffer

offline benchmark 已验证调度器时序收益，但上游在线尚未接线。本 SPEC 要求：

1. 先以 `sync` 作为 parity baseline。
2. async 只在 shadow tests 通过后启用。
3. swap 只发生在当前 K 消费完后，不中途截断。
4. observation sequence 必须随 prefetched chunk 记录。
5. Hold、reset、E-stop 必须清空 active/prefetch 两个 buffer。

---

## 10. 分阶段实施

### M0 — 合同冻结（中游；无运行时行为变化）

**状态**：✅ 已完成。冻结证据为 `configs/policy_runtime/panda_policy_runtime_v1.lock.json`；CPU 合同测试位于 `tests/test_policy_runtime_contract.py`。这不表示 ROS messages、在线 Policy Runtime、Safety bridge 或 HOC 四流已经实现。

改动：

- 新增 `evaluation/schemas/policy_runtime_contract.schema.json`
- 新增 `evaluation/examples/policy_runtime_contract_fixture.json`
- 新增 lock：schema、合同 descriptor、六类 fixture 与 diagnostic graph SHA256
- 将 `PolicyAdapter` v0 的固定 `export_action → ee_delta[7]` 标记为 replay compatibility
- 新增 schema/fixture/禁止 claims 的 CPU tests

验收：✅ Draft 2020-12 schema valid；fixture/DAG pass；unknown schema、错误动作维度、HOC payload 错配与非法 lifecycle/task claim fail；`claims_task_success` 只能为 false。

### M1 — ROS messages 与上游 adapter 拆分（不切流）

**状态**：✅ 已完成 shadow 实现。上游编译和 mock ROS transport 已验证；`policy_runtime_shadow_enabled` 默认 false，未跑 Isaac。

改动：

- 上游 `teleop_interfaces/msg/PolicyCommand.msg`
- 上游 `teleop_interfaces/msg/PolicyExecutionReport.msg`
- 上游 `teleop_interfaces/msg/TaskEvaluationStatus.msg`
- 新增 `PolicyBackend` protocol 与 `SmolVlaPolicyBackend`
- 新增可测试 `PolicyRuntimeStateMachine`、`ShadowCommandScheduler` 与结构化 health ROS 映射
- 旧 `smolvla_policy_inference_node` 增加可关闭的 compatibility/shadow mode

运行方式：旧路径仍是唯一执行者；新路径只生成 shadow command/health，不新增 teleop command publisher。`PolicyExecutionReport` 在 M1 只完成接口生成；由 M2 `PandaPolicyExecutionAdapter` 开始发布。

历史限制：M1 的 SmolVLA wrapper 只调用 `select_action()`，因此当时只发布 singleton envelope，且没有通过重复推理伪造 native chunk。M2 已改用 LeRobot `predict_action_chunk()`；当前 shadow backend 输出 native chunk10、执行 K=5。

### M2 — Shadow parity

**状态**：✅ 已完成 shadow 实现。新增 `PandaPolicyExecutionAdapter`，消费 `PolicyCommand` 并发布 shadow `PolicyExecutionReport`，但不取得执行权威；节点强制要求 `policy_runtime_shadow_enabled=true` 时同时 `dry_run=true`。

对同一 observation 同时计算：

- legacy：当前 `bound_absolute_eef_gripper → target pose`
- new：`PolicyCommand → PandaPolicyExecutionAdapter → target pose`

M2 不执行任何一条新路径；它记录 legacy 与 adapter 的逐步差异：position、quaternion、gripper、clip flags、sequence、TTL。实际 legacy 执行语义保持冻结，M2 测试使用同一现有转换函数做 differential parity。

证据：CPU/ROS 合同套件 53 tests pass；canonical S4 relight 5-seed 已有 telemetry 中 750 个动作的 bounded action 与 clip decision 全一致；ROS `PolicyExecutionReport` mock round-trip、两包 colcon build 通过。未跑新 Isaac seed、未训练。

当前限制：在线异步 double buffer 尚未接入；`EXECUTED` 在 adapter 名称带 `_shadow` 的报告中仅表示 would-execute，不能解释为真实执行或任务成功。

### M3 — 接下游在线 monitor / risk

**状态**：✅ 已完成只读 Observable 实现。无效分布指标显式 fail-closed，Risk 只聚合 valid sources，HOC 已接入 Brain / Execution / Safety / Task GT 四通道；canonical continuous evaluator 已发布 live Task GT，但没有取得控制权限。

改动：

- 下游新增 `policy_runtime_monitoring.launch.py`
- dist_monitor 使用 topic remap 消费上游匹配的双源 joint telemetry；只使用同场景已标定的健康 residual baseline，不直接把现有 LeRobot release 当 KL baseline
- `DistributionMetrics` 增加 `metric_valid`、`baseline_ready`、`calibration_id`；benchmark / offline readiness 对无效指标记录 `unavailable`，禁止默认零分
- 将 `/policy/runtime_health` 映射到 risk resource/comm health 输入
- HOC backend 接入 policy health / execution report / task GT；前端先实现四泳道只读状态，不增加新的控制权限
- 增加 validity、聚合、断流、乱序、trace correlation 与五态前端测试

此阶段仍不切换主命令源。`RiskToSafetyBridge` 明确留在 M4 dry-run，不属于 M3。

### M4 — 切换唯一命令源

**状态**：✅ 安全反馈与 authoritative 代码路径已实现，默认不切流。下游 bridge 默认 `dry_run=true`；上游默认 `execution_adapter_mode=legacy`。本次只完成 CPU/ROS mock 与构建验证，没有启动 Isaac 或改变现有命令权威。

前置：M0–M3 全部 Pass，且人工批准切流。

- 新 `PandaPolicyExecutionAdapter` 成为 `/teleop/cmd_pose` 和 `/teleop/gripper_cmd` 唯一 publisher。
- compatibility direct publish 关闭。
- 启动时断言 command topic publisher count / source identity。
- 当前 scheduler 保持同步 replan；在线 async double-buffer 仍未实现，留待后续版本。
- R2 清空 active queue 但保持 command sequence 单调；健康恢复后必须重新规划。
- R3 请求单次触发并锁存，只有观察到 safety latch 的人工 reset 下降沿后才能重新武装。

### M5 — 下游 PolicyCommand replay

**状态**：✅ 纯离线实现完成；没有启动 PyBullet/Isaac、没有 authoritative cutover。

- 中游冻结 `panda_policy_trace_bundle_v1` schema、fixture 与独立 SHA lock；manifest 索引 command、health、execution、risk、task GT 五个 JSONL。
- 下游新增严格 bundle loader 与 `PolicyCommandReplayPolicy`，逐 command 校验 hash、trace/episode、sequence 和 execution parent correlation。
- 新增独立 `PandaAbsoluteEefReplayAdapter`；absolute EEF8 不经过也不污染旧 delta EEF7 adapter。
- HOC JSON/HTML 导出 command correlation；`trace_bundle` 格式仅在完整关联时写出，否则拒绝。
- 所有 M5 产物固定 `is_closed_loop=false`、`claims_task_success=false`。

### M6 — 有界 wiring smoke（已批准并完成）

只有获得显式人工批准后才执行：

- 不扩 seeds；最多使用已有授权范围内的单次 wiring smoke。
- 只验证 contract、Hold/E-stop、topic、latency、cleanup。
- 不用该 smoke 改写 S4 task Gate，不声称抓取成功。

2026-07-26 验收结果：真实 DDS 多进程接线 Pass，使用 mock PolicyBackend；command QoS、contract/latency/queue/TTL、R2 Hold、R3 TriggerEstop、HOC 四泳道与 trace bundle 均通过。未启动仿真或模型，Task GT 如实为 UNAVAILABLE。见 [M6 Wiring Results](portfolio/POLICY_RUNTIME_M6_WIRING_RESULTS.md)。

---

## 11. 仓库改动清单

### 11.1 中游：合同与证据

| 路径 | 动作 |
|---|---|
| `docs/POLICY_RUNTIME_INTEGRATION_SPEC.md` | canonical SPEC |
| `docs/POLICY_ADAPTER_CONTRACT.md` | 升级到 native action envelope；保留 v0 replay compatibility |
| `evaluation/schemas/policy_runtime_contract.schema.json` | 新增 |
| `evaluation/examples/policy_runtime_contract_fixture.json` | 新增 |
| `configs/policy_runtime/panda_policy_runtime_v1.lock.json` | 新增 SHA lock |
| `tests/test_policy_runtime_contract.py` | 新增 |
| `evaluation/unified_report.py` | 可选挂 runtime health appendix；不得改 task lane |

### 11.2 上游：在线策略与执行

| 路径 | 动作 |
|---|---|
| `src/teleop_interfaces/msg/PolicyCommand.msg` | 新增 |
| `src/teleop_interfaces/msg/PolicyExecutionReport.msg` | 新增 |
| `src/isaac_sim_adapter/.../policy_runtime.py` | `PolicyBackend` / scheduler |
| `src/isaac_sim_adapter/.../smolvla_policy_backend.py` | 从现有 node 提取模型逻辑 |
| `src/isaac_sim_adapter/.../policy_execution_adapter.py` | schema dispatch、安全适配、report |
| `src/isaac_sim_adapter/.../smolvla_policy_inference_node.py` | compatibility → runtime publisher |
| `src/isaac_sim_adapter/launch/policy_runtime.launch.py` | 新增组合 launch |
| `tests/test_policy_execution_adapter.py` | parity / TTL / Hold / schema tests |

### 11.3 下游：monitor、安全反馈与 replay

| 路径 | 动作 |
|---|---|
| `risk_engine/risk_engine/risk_to_safety_bridge.py` | 新增 R0–R3 映射 |
| `pybullet_bridge/launch/policy_runtime_monitoring.launch.py` | 新增 remap/monitor launch |
| `pybullet_bridge/.../policy_command_replay_policy.py` | M5 新增 |
| `pybullet_bridge/.../panda_absolute_eef_replay_adapter.py` | M5 新增，禁止污染 delta adapter |
| `risk_engine/test/test_risk_to_safety_bridge.py` | 新增 |
| `pybullet_bridge/test/test_policy_command_replay.py` | M5 新增 |

---

## 12. 验收标准

### 12.1 合同

- 三仓 runtime schema SHA256 一致。
- 不支持的 schema、维数、NaN/Inf 必须 fail closed。
- action conversion 必须记录 adapter name/version。
- `claims_task_success=false` 在 schema 与运行产物中固定。

### 12.2 Shadow parity

- absolute position max error ≤ `1e-6 m`。
- quaternion angular error ≤ `1e-6 rad`。
- gripper max error ≤ `1e-6`。
- legacy/new clip decision 逐步一致。
- command sequence 单调，无重复执行。

### 12.3 Runtime

- `/teleop/cmd_pose` 权威模式下只有一个 policy command publisher。
- TTL 过期、queue underrun、observation stale 均进入 Hold。
- R2 到 Hold 的 p95 ≤ `250 ms`（仿真系统目标，不宣称 hard real-time）。
- R3 只调用一次 E-stop；不得自动 clear。
- Hold 恢复必须清 queue 并重新 infer。

### 12.4 Downstream

- dist_monitor 能读取 remapped online joint state。
- baseline 未 ready、样本不足或 calibration 不匹配时，KL 显式 `unavailable`，Risk 不得按 `0.0` 聚合。
- 只有同场景 Panda calibration 通过后，KL 才能参与 R-level；旧 synthetic / legacy 阈值只作 fixture。
- RiskStatus 能驱动 mock Hold/E-stop integration test。
- replay 同时拒绝 schema mismatch 和 silent absolute→delta。
- PolicyCommand replay 报告保持 `is_closed_loop=false`。
- HOC 能区分 Brain health、Execution decision、Safety R-level 与 Task GT；任一来源缺失时显示 `UNAVAILABLE/STALE`，不得默认绿色零值。
- 顶部只显示一个 Run/Hold/E-stop 裁决，并能定位到 source + reason + command sequence。

### 12.5 证据边界

- task GT 仍只来自上游 evaluator。
- risk appendix 不覆盖 `failure_lane`。
- wiring smoke 不改变 Recovery v3 open-loop Pass / S4 Hold。

---

## 13. 故障与降级矩阵

| 故障 | Lane | 默认动作 | 可恢复 |
|---|---|---|---|
| contract hash mismatch | `interface_fail` | 启动失败 | 修配置后重启 |
| unknown action schema | `interface_fail` | Hold + reject | 新 command 可恢复 |
| action NaN/Inf | `interface_fail` | Hold；连续出现可 E-stop | 配置化 |
| observation stale | `system_fail` | Hold | 新鲜 observation 后重新 infer |
| inference timeout | `system_fail` | Hold + health ERROR | backend 恢复后 reset |
| queue underrun | `behavior_tag/system_fail` | Hold | 清 queue + replan |
| R2 degraded | `system_fail` | Hold | 连续健康 N 次 |
| R3 / E-stop | `system_fail` | E-stop | 仅人工 reset |
| adapter clipping | `interface` 诊断 | 执行 bounded action并记录 | 是；高比例升级 Hold |
| task lift 失败 | `task_gt` | evaluator 判定 | 不由 risk 改写 |

---

## 14. 测试策略

### T0：纯 CPU 合同测试

- JSON Schema / fixture
- action schema dispatch
- TTL / sequence / finite
- Hold / E-stop 状态机
- chunk reset / async buffer cancellation

### T1：录制 telemetry replay

使用已有 S4 `observations.jsonl` 和 `actions`，离线跑 legacy/new adapter parity；不启动 Isaac。

### T2：ROS mock integration

假 PolicyBackend + mock joint/EE/image + mock RiskStatus：

- RUN → command
- R2 → Hold
- R3 → TriggerEstop
- reset → clear queue → fresh infer

所有 launch 必须带 timeout，并在结束前执行项目规定的进程清理。

### T3：可选 wiring smoke

需要显式人工批准；只验证接线，不做新 task claim。

---

## 15. 提交顺序与回滚

建议原子提交：

1. `docs(contract): freeze panda policy runtime v1 spec`
2. `feat(contract): add policy runtime schema fixtures and lock`
3. `feat(upstream): add policy command messages and shadow adapter`
4. `test(upstream): prove legacy/new command parity`
5. `feat(downstream): bridge risk status to policy hold and safety estop`
6. `feat(upstream): switch policy execution to single authoritative adapter`
7. `feat(downstream): add versioned policy command replay`

回滚原则：

- M1–M3 不改变旧执行路径，可直接关闭新 launch。
- M4 保留 `execution_adapter_mode:=legacy|shadow|authoritative` 一个发布周期。
- 发生 contract、latency 或 safety 回归时切回 `legacy`，保留 evidence，不删除失败产物。
- 不使用 `git reset --hard` 或删除历史 S4 evidence。

---

## 16. Definition of Done

只有同时满足以下条件，才能写“统一 Policy Runtime 已接通”：

- [ ] 中游 `panda_policy_runtime_v1` schema + lock 已冻结。
- [ ] SmolVLA 通过 `PolicyBackend` 输出 native absolute action chunk。
- [ ] 上游 Execution Adapter 是唯一 policy command executor。
- [ ] sync/async queue 在 reset/Hold/E-stop 下行为可测。
- [ ] 下游 dist/risk 消费上游在线 telemetry。
- [ ] R2 Hold 与 R3 E-stop mock integration Pass。
- [ ] PolicyCommand 可被下游 versioned replay，且保持 `is_closed_loop=false`。
- [ ] task GT、risk、interface 三类结论在报告中分栏。
- [ ] CPU / ROS mock tests Pass，所有链接与合同 SHA 一致。
- [x] M6 wiring smoke 已获人工批准并完成，未扩大 seed/训练范围；使用 mock PolicyBackend，未执行 authoritative SmolVLA cutover。

在此之前，正确口径仍是：

> 已实现 SmolVLA 上游在线执行和下游 replay/risk 独立验证；统一在线大脑—小脑 Policy Runtime 尚在实施阶段。
