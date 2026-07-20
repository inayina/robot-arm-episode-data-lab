# E0 Evaluation Contract

状态：**E0 契约与校验夹具已实现；E1 固定动作序列已在 Isaac 实跑，learned-policy
rollout 尚未执行。**

本文件固定 Panda 评测的 run、episode 和 summary 三层协议。E0 只新增离线契约，
不修改上游 recorder raw schema、ACT 训练主线或下游 PyBullet replay。后续 E1 已在上游
补齐 Isaac action execution infrastructure，但没有改变本契约的三仓职责边界。

## 1. 机器可读产物

| 产物 | Schema | 生产者 | 作用 |
|---|---|---|---|
| `run_manifest.json` | `evaluation/schemas/run_manifest.schema.json` | 运行编排器 | 固定 model/dataset/repository/simulator/suite/seed provenance，以及 QoS、时钟、线程、fail-safe 和 NFR 证据要求 |
| `episode_results.jsonl` | `evaluation/schemas/episode_result.schema.json` | 上游 runtime evaluator | 每行记录一个 seed 的 runtime ground-truth outcome、subgoal、运动、接触、数据健康、系统性能和证据路径 |
| `summary.json` | `evaluation/schemas/summary.schema.json` | 中游离线聚合器 | 只聚合 episode labels，输出成功率、置信区间、failure Pareto、repeatability、baseline delta 和建议 |

Schema 使用 JSON Schema Draft 2020-12，并默认 `additionalProperties: false`。当前 nominal
示例位于 `evaluation/examples/nominal_contract_fixture/`，固定 seeds 为 `101, 202, 303`。
它的 `evidence_level=contract_fixture`、`execution_status=not_executed/planned`，所有 runtime
结果和性能值均为 `null`，不能作为已运行证据。

## 2. 三仓 ownership

| 仓库 | E0 职责 | 禁止越界 |
|---|---|---|
| `ros2-arm-teleoperation-suite`（上游） | runtime simulator、action execution、ground-truth task/subgoal evaluator、episode evidence | 不负责中游 release/training/aggregation；不得用离线 loss 替代 runtime success |
| `robot-arm-episode-data-lab`（本仓） | schema 校验、离线聚合、checkpoint/suite 对比、报告 | 不从 `observation.object_pose` 重新推导 lift/place；不启动 ROS/Isaac runtime |
| `ros2-moveit-pybullet-bridge`（下游） | replay、tracking/distribution/risk review | risk score 不覆盖上游 runtime ground-truth success；PyBullet IK 不复制到 Isaac adapter |

物理成功的唯一权威字段是 episode row 的 `outcome.success`，且只在以下条件同时满足时
有效：

1. `execution_status=completed`；
2. `evidence_level=runtime_observed`；
3. `outcome.runtime_evaluated=true`；
4. evaluator owner 是 `ros2-arm-teleoperation-suite`，ground-truth source 是
   `runtime_ground_truth`；
5. raw episode、runtime log、event log 与 NFR sample 路径非空。

中游 summary 的 numerator/denominator 必须来自上述有效 episode，不能根据轨迹、
object pose、offline loss 或 PyBullet risk 补标签。

## 3. Suite、seed 与 provenance

每次执行前必须将以下字段从 `null` 解析为实际值并保存：

- model id、Git commit、checkpoint path 与 SHA-256；
- dataset release id、manifest path 与 SHA-256；
- 三仓 Git commit；
- suite config path/version/SHA-256 和固定 seed list；
- simulator version/build、GPU driver 与 hardware id；
- policy/adapter/controller rate、`use_sim_time`；
- stale command/state、reset 与 policy timeout 阈值。

seed 只固定随机输入，不代表 GPU physics bitwise deterministic。稳定性声明仍需重复 seed
并在 summary 的 `repeatability` 中报告方差或不一致。

## 4. QoS、三类时钟和 control/data plane

`run_manifest.qos_matrix` 固定通道类别，而不是把所有 topic 设成同一 QoS：

- joint command、robot state、camera：best effort、volatile、bounded keep-last；
- safety E-stop：reliable + transient local；
- health/evaluation event：reliable + bounded keep-last；
- reset/EndEpisode transaction：reliable + volatile；
- static TF：reliable + transient local。

每个 runtime run 必须在动作开始前保存 offered/requested QoS preflight。mismatch 直接
`fail_preflight`，不得带不兼容 endpoint 继续运行。

三类时钟必须同时保存：

- simulation time/step：physics 推进和 seed 重现；
- ROS timestamp：跨 topic 对齐及 command/state age；
- monotonic host time：timeout、watchdog 与 wall latency。

timeout 禁止使用可跳变 wall clock。reset completion 后必须清理 policy chunk、adapter
history、setpoint、watchdog 和时间基准；首个有效 state 的 monotonic timestamp 必须晚于
reset completion event。

控制面必须留在 simulator host 或低延迟局域网，禁止把底层控制 loop（仿真 500 Hz / 真机 1 kHz）跨公网。控制 callback
不执行视频编码、artifact flush、报告生成或阻塞网络 I/O。数据面使用 bounded queue，
过载时丢旧帧并记录 dropped/stale count。`thread_ownership` 明确 control/state、policy、
reset、camera 和 flush 的 worker/callback-group 边界。

## 5. Fail-safe 语义

| 条件 | 检测 | 强制响应 | episode 终态 |
|---|---|---|---|
| stale command | monotonic command age 超过运行配置阈值 | `HOLD`，随后有界 abort；禁止无限重放旧 action | `timeout` |
| stale state | ROS/state age 超过运行配置阈值 | `HOLD`，随后有界 abort；禁止发新 command | `timeout` |
| DDS QoS mismatch | preflight 存在 incompatible offered/requested QoS | 动作前 `fail_preflight` | `infrastructure_failure` |
| reset timeout | monotonic reset deadline 到期 | abort，并清理 chunk/history/setpoint/watchdog/time epoch | `timeout` |
| policy timeout / exception / NaN | bounded inference deadline 到期或输出无效 | `HOLD`，随后 abort | `timeout` |

每次触发必须写 `fail_safe_events` 和 event log，不允许只在控制台打印。

## 6. NFR 证据（不是预设结果）

`nfr_evidence_contract` 只定义必交证据及路径，不预填测量数字。runtime episode 应记录：

- command/state age P50、P95、max；control/state frequency 和 gap；
- watchdog latency、reset recovery；
- CPU/GPU/RSS/VRAM、physics FPS/RTF 和 frame time；
- kernel、scheduler、affinity、transport/QoS snapshot；
- QoS mismatch/disconnect fault-injection event。

普通 Ubuntu 仿真只能报告实测 latency/jitter/FPS，不能据此声称 hard real-time。
E0 示例中的 NFR 值全部为 `null`；E1 之后只有带 runtime logs 的字段才可进入报告。

## 7. 校验

安装基础依赖后运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_evaluation_contract.py
```

测试会检查三份 schema 自身有效、nominal 示例逐项有效、三个 seed 一致、ownership 不冲突，
并验证 contract fixture 不能伪造 success 或 completed summary。

## 8. E0 / E1 状态与边界

### 已实现

- run / episode / summary schema；
- nominal suite 与 3 个固定 seed 的 contract-only 示例；
- provenance/evidence 路径、ownership、QoS、时钟、plane/thread、fail-safe、NFR 字段；
- 自动 schema 与跨文件一致性测试。
- 上游 `ros2-arm-teleoperation-suite` 已完成 E1 `/sim/joint_effort_cmd` → Isaac articulation
  execution、adapter/backend 双 watchdog、reset history 清理、SensorDataQoS 与 callback
  isolation；实现说明见上游 `docs/ISAAC_E1_ACTION_EXECUTION.md`。
- 上游 canonical E1 证据位于
  `evidence/isaac_e1_action_execution_20260718_final/`：5/5 固定 effort sequence、运行中
  health OK、双端 BEST_EFFORT/VOLATILE QoS、104.080 ms 断连 watchdog→zero-effort。

### 已实现（上游 continuous GT，有界）

- 上游 `synth_data_gen.continuous_evaluator.ContinuousTaskEvaluator`
  （`evaluator_id=panda_continuous_gt_v0`）流式观测 object/EE/gripper，产出
  `episode_results.jsonl` 行，字段对齐本仓 `evaluation/schemas/episode_result.schema.json`。
- `batch_generator` 在 `episode_results_path` 非空时写出；smoke 默认
  `BATCH_PREFLIGHT_EPISODE_RESULTS_PATH` → `$OUT_ROOT/episode_results.jsonl`。
- lift 用 **held-peak**（夹持期间峰值高度），place 用 bin XY；slip 为相对 EE 的 hold
  偏移漂移（运输平移不记为 slip）；单元测试含正/负轨迹与可选 schema 校验。
- Isaac policy GT：**v1** `scripts/isaac_continuous_gt_recorder.py` 分离 gripper cmd/state、
  MultiThreadedExecutor drain、`/ft_sensor`；`run_isaac_gt_preflight.sh` 做一致性门禁。
  `evidence/e3_nominal20_home_30ep_20260719/INVALID_EVALUATOR_V0.md` 的 9 行 **不得**计入 E3。

边界：batch 物理门禁仍以 `_validate_episode` 为准；continuous 行在 completed 时会把
`outcome.success` 与该门禁对齐。有界 Isaac ACT smoke 默认 `EPISODE_RESULTS_PATH` 为空
（不写 continuous GT）；`run_isaac_nominal_suite.sh` 会设置路径。日常指标分栏与
「Success Rate / RMSE / Episode Time / Collision / Distribution Shift」的**代码级权威来源**
见 [`EMBODIED_POLICY_EVALUATION_SOP.md`](EMBODIED_POLICY_EVALUATION_SOP.md) §1.3。

### 尚未实现

- ACT checkpoint → MoveIt Servo 的 learned-policy online rollout；
- 多 suite regression、失败视频和 checkpoint A/B report（valid GT v1 nominal20 进行中）；
- policy online rollout 默认挂载 continuous GT（当前主要挂在 batch/expert + suite 路径）。

E1 只证明 action execution infrastructure。canonical 5-repeat 的 trajectory RMSE 最大
0.360 rad、终态 L2 最大 1.337 rad，说明 open-loop repeatability 仍有明显风险；不证明
learned policy、稳定控制、物理任务成功、hard real-time 或 Sim2Real 效果。
