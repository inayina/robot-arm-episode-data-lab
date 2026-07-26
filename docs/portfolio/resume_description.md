# 求职材料：三套简历版本 + 面试话术（具身策略评测框架）

**冻结日期**：2026-07-25 · **基线 commit**：`d7ba9d53e9df94c0c4565ba31114cf9b1511a878`
**岗位定位**：**系统验证 / 测试开发 / 评测工程**（具身智能方向）。**不是** VLA 算法研究员，不以「刷高任务成功率」为卖点，而以「建立可复现、防包装的策略评测与归因体系」为卖点。
**诚实边界（所有版本通用，必须保留）**：**Not task success / Not Sim2Real / Not real robot**。open-loop Pass、interface Pass、`ran_isaac=true` 都不是任务成功。所有评测产物 `claims_task_success=false`。

**技术栈**：ROS 2 (Jazzy)、MoveIt Servo、MuJoCo、Isaac Sim、PyBullet、PyTorch、LeRobot / SmolVLA (LoRA / PEFT)、PyArrow (Parquet)、pytest、JSON Schema、Python、C++

**可引用的核心数字（均有机器可读产物）**：

| 事实 | 数字 | 证据 |
|---|---|---|
| Recovery v3 LoRA | 5,705 steps；train-only 36 episodes；`state[15]`+scene RGB；checkpoint audit Pass；adapter SHA256 `4cfcc46e…` | `runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/checkpoint_config_audit.json` |
| Prospective open-loop **Pass** | 10 ep / **2,593 帧**（seeds 70–74）；EE RMSE **0.0253 m**；gripper balanced accuracy **0.9943**；close-edge beyond-ε **0.386%** | `runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/` |
| 相对基线改善 | EE 相对 S2（0.2734 m）改善 **90.7%** | 同上 + `configs/smolvla_s3/eval_gate_v3.yaml` baselines |
| Gate 冻结 | `eval_gate_v3` SHA256 **`37325a1f…`**，`frozen_at_utc=2026-07-24T06:25:00Z` | `configs/smolvla_s3/eval_gate_v3.lock.json` |
| 有界 Isaac S4（权威） | seeds 1–5；interface **5/5**；reach 1/5；grasp 0/5；lift **0/5** → **Hold** | `evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json` |
| 物理链上界（非本策略） | scripted oracle lift **5/5**，`gate_pass=true` | `evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/oracle_gate.json` |
| ACT 诊断基线 | E3 nominal20 overall **0/20**（reach 10/20，Wilson 95% CI `[0, 0.161]`） | `evidence/e3_nominal20_home_30ep_gt_v1_20260719/summary.json` |
| 跨后端统一信封 | 三后端同一 `unified_eval_report_v0`，`claims_*` 恒 false | `evidence/smolvla_v3_eval_framework_relight_20260725/` |
| 下游 interface 复用 | 1-ep `panda_jsonl_replay` + `pybullet_ik`；1,105 行时序；mean 18.0 ms / max 357.7 ms；`is_closed_loop=false` | `evidence/downstream/smolvla_v3_ep0_benchmark_summary.json` |
| CPU 回归 | 三仓契约 / 文档一致性 pytest 全绿 | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` |

---

# 版本 A — 系统验证 / 算法测试工程师

> 适合投：系统验证工程师、算法测试工程师、AI 测试开发、机器人软件测试。

## A.1 简历条（可直接粘贴）

- **具身策略评测与验证系统（Franka Panda 三仓闭环，独立研发）**——为模仿学习 / VLA 策略设计**分层验证体系**：Data → Offline → Interface → Behavior → Task-GT → System 六层分栏，每层只判定自己的问题，禁止跨层升级结论。
- 设计并**SHA256 冻结**评测门禁（`eval_gate_v3`，`37325a1f…`），把「预裁剪 raw 幅值」修订为**执行侧 `clip(raw,0,1)` 语义**，保留关爪边 beyond-ε（≤1%）与分类/时序不变式为硬安全项；**历史 Hold 判定不追溯改写**。
- 建立 **immutable release + checkpoint/norm/Benchmark 三向绑定**：release manifest 逐文件 SHA256、`splits.json` 三段无交集、checkpoint config audit 核验 `state[15]` / camera / `action[8]` / chunk / K / PEFT 正则与 adapter SHA256，杜绝「训练配置与评测配置静默漂移」。
- 用 **scripted oracle 隔离被测系统**：oracle v1 也 lift 0/5 → 定位为物理链缺陷（pick 高度 / PD 夹爪 / 摩擦 / GT 阈值），修复后 v2b lift **5/5**，从而把 learned policy 的失败**排除物理链嫌疑**。
- 主动**证伪自己的正向指标**：有界 Isaac S4 首轮 reach 3/5 · grasp 1/5 看似部分成功，补相机遥测发现 policy 输入近黑（像素均值 ≈0.3 vs 训练域 ≈50），修光后同 seeds 复测降为 reach 1/5 · grasp 0/5 —— **更差但更真实**，并把首轮标注为 `Superseded`。
- 交付**可复现回归**：三仓 CPU pytest 覆盖 gate 契约、统一报告 schema、checkpoint/manifest 引用、图表数据源、诚实声明不变式与失效链接；所有作品集图表由脚本从证据 JSON 重出，数字**不硬编码**。

## A.2 100–150 字概述

我独立搭建了一套面向机器人模仿学习与 VLA 策略的评测与验证系统。核心不是训练出能抓取的模型，而是把「数据质量、动作契约、离线预测、在线执行、任务真值、系统健康」拆成六层可判定门禁，并用 SHA256 冻结阈值与配置，防止指标被静默改写。我用 scripted oracle 把物理链故障与策略故障分离，用相机遥测证伪了自己看似正向的中间结果，并把每次失败归档为分层 Badcase 与止损决策。最终结论保持诚实：离线门禁 Pass，有界在线仿真仍 Hold，不声称任务成功或 Sim2Real。

## A.3 30 秒介绍

> 「我做的是具身策略的**验证与测试**，不是算法调参。项目在同一套 Panda 三仓闭环上被测了四个候选：MLP BC、ACT、SmolVLA VLA 和一个 scripted oracle。我的产出是一套六层门禁 —— 数据、离线、接口、行为、任务真值、系统 —— 每层只回答自己的问题。最典型的一次工作是：模型在 Isaac 里 interface 5/5 全通过、动作全下发、无限幅无急停，但连续真值显示 lift 0/5。我没有直接说『模型不行』，而是先跑 scripted oracle 证明同一条物理链能 5/5 抓起来，再补相机遥测发现在线输入近黑，修光后重测把虚高的 reach 3/5 降到 1/5。结论是 Hold，我不会在简历里写任务成功率。」

## A.4 2 分钟案例：把「interface PASS」和「任务成功」彻底分开

- **Situation**：ACT checkpoint 接进 Isaac 有界 rollout，20/20 episode 都能跑完有界动作、安全链正常、无限幅、无急停。从「系统联调」视角看，这是一次成功的集成。
- **Task**：判断这到底能不能作为「策略可用」的证据。
- **Action**：
  1. 先做**评测器自身的验证**：发现 recorder 把 gripper **command** 混作 **measured state**，评测器读到的不是真实开合；把旧结果整体隔离为 `INVALID_EVALUATOR_V0`，不计入任何成功率。
  2. 修复 command/state 分离、接入力/力矩，并用两个 seed 做一致性预检（2101/2102 PASS）后，才运行权威 nominal20。
  3. 引入**连续任务真值**（reach / grasp / lift / transport / place），与 interface 指标分栏。
  4. 结果：reach 10/20，grasp / lift / transport / place **0/20**，overall **0/20**，Wilson 95% CI `[0.000, 0.161]`，`go_no_go=no_go`。
- **Result**：把「20/20 动作完成」和「0/20 任务成功」写在同一份报告的不同分栏里，并据此**关闭 E3、冻结 ACT 为诊断基线、不启动规划中的 100+ rollout E4 矩阵**。这条判断后来复用到 SmolVLA：S4 同样 interface 5/5、lift 0/5，直接按既有规则判 Hold，不需要重新争论口径。
- **可验证**：`evidence/e3_nominal20_home_30ep_gt_v1_20260719/summary.json`、`evidence/e3_gt_preflight_v1_20260719/preflight_summary.json`。

## A.5 失败归因案例（版本 A 口径）

见下方[通用失败归因案例](#通用失败归因案例把自己的正向指标证伪)，A 版本面试时强调**「测试者要能证伪自己」**这一点。

---

# 版本 B — 具身数据评测 / Benchmark 工程师

> 适合投：具身智能数据平台、Benchmark / Eval 工程、数据质量与标注体系、Data-centric AI。

## B.1 简历条

- **具身操作策略 Benchmark 与数据治理（Panda 三仓，独立研发）**——把「专家示教 → immutable release → 训练 → 离线门禁 → 仿真执行 → 归因」做成契约化流水线，每一环产出机器可读产物（manifest / metrics / gate / unified report）。
- 设计 **Panda 数据契约**（`configs/robot_schemas/panda.yaml`）：`observation.state`、`ee_pose[7]`、`object_pose[7]`（privileged，禁入 policy state）、`ft[6]`、scene RGB 320×240@10 Hz、`action` 语义（ACT 的 `ee_delta_gripper[7]` 与 VLA 的 `absolute_eef_gripper[8]`）；入口静态校验，维度或通道漂移在**入口**拦截。
- 建立 **immutable release + 数据健康度门禁**：逐文件 SHA256、`release_content_sha256`、`splits.json` 三段无交集、joint-step P99 与反向运动率过滤抖动/丢帧、`scene_rgb_complete_rate`、`filter_scope=training_split_only`（物理成败归上游，中游不重复推导）。
- **发现并修复一次训练/评测泄漏**：事后审计发现某 release 虽声明 12/4/4 split，训练根与训练日志却是全部 20 episodes；据此把该轮的「held-out / OOD」表述**降级为 release-named slices**，并在 Recovery 中强制 **train-only 物化**（36 episodes）。
- 设计**prospective eval-only 采集**：为避免阈值设计污染评测集，为新 gate **重新采集** seeds 70–74 / 2,593 帧，保证与训练集和阈值设计过程零重叠，再出 Pass 结论。
- 定义 **`unified_eval_report_v0` 跨后端信封**：open-loop / 下游 PyBullet PolicyRunner / Isaac 有界 rollout 三后端映射到同一 interface / behavior / task / offline 分栏，`claims_task_success` 等恒为 false，只 remap 已有字段、**不发明指标**；JSON Schema + normalizer + 单测固定。

## B.2 100–150 字概述

我负责把具身操作的数据与评测做成契约。上游采集的 episode 经 schema 校验、抖动/丢帧过滤和不可变 release 固化，逐文件 SHA256、split 无交集；训练与评测通过 checkpoint audit 三向绑定，防止配置漂移。评测侧我定义了跨后端统一报告信封，把离线预测、接口执行和仿真任务真值分栏，并规定这些字段永远不得声称任务成功。过程中我审计出一次训练/评测泄漏并主动降级结论，也为新门禁重采了独立评测集以避免阈值设计污染。当前结论是离线门禁 Pass、在线有界仿真 Hold。

## B.3 30 秒介绍

> 「我做具身数据与 Benchmark 的契约化。一条 episode 从上游采集到最终评测报告，中间每一步都有机器可读产物和门禁：schema 校验、抖动过滤、不可变 release（逐文件 SHA256、split 无交集）、checkpoint 与 norm 的三向绑定，最后落到一个跨后端统一报告信封。我最看重两件事：一是**评测集干净** —— 我审计出过一次训练根没按 split 过滤，就把那轮的 held-out 表述降级，并为新门禁重采了独立评测集；二是**报告不能自我升级** —— 信封里 `claims_task_success` 这类字段恒为 false，schema 层面就拒绝把离线 Pass 写成任务成功。」

## B.4 2 分钟案例：一次训练/评测泄漏的审计与降级

- **Situation**：一轮经人工例外批准的 data-fix 重训完成，release 声明 12 train / 4 validation / 4 benchmark，我们准备用那 4+4 条报告「held-out / OOD 表现」。
- **Task**：在写结论前先核对训练实际吃了哪些 episode。
- **Action**：
  1. 比对 release `splits.json`、训练根目录与训练日志，发现训练入口**未按 split 过滤**，合并训练根与日志都是 **20 episodes**。
  2. 据此把该轮的「held-out / benchmark」措辞降级为 **release-named slices**，明确「当前结果是在训练见过这些 episode 的条件下仍 Hold」。
  3. 在 Recovery 阶段把 **train-only 物化**做成入口能力（36 episodes 可写 `state[15]`），并加契约测试固定。
  4. 为新一版门禁**重新采集** prospective eval-only 数据（seeds 70–74 / 2,593 帧），并写明「v2 的 prospective 10 条已被 v3 阈值设计污染，不能复用」。
- **Result**：训练产物仍然有效并保留，但结论强度被正确降级；后续 Pass（EE 0.0253 m、grip BA 0.9943）建立在真正独立的评测集上，可以放心对外引用。
- **可验证**：`runs/smolvla_s3/train_v2_lateclose_20260723T160000Z/train_log.txt`、`configs/smolvla_s3/recovery_decisions.yaml`、`tests/test_smolvla_s3_train_split_materialization.py`。

## B.5 失败归因案例（版本 B 口径）

见[通用失败归因案例](#通用失败归因案例把自己的正向指标证伪)，B 版本强调**「指标可信度取决于数据与口径，而不是数值大小」**。

---

# 版本 C — 仿真评测 / 数据闭环工程师

> 适合投：机器人仿真、Sim2Sim / Sim2Real readiness、多仿真后端评测、闭环验证平台。

## C.1 简历条

- **多仿真后端具身闭环验证平台（MuJoCo / Isaac Sim / PyBullet 三仓解耦，独立研发）**——上游 ROS 2 + MoveIt Servo 末端笛卡尔伺服与阻抗控制（仿真主线 500 Hz，真机路径设计为 1 kHz）+ MuJoCo 采集；中游数据治理与训练；下游 PyBullet 无 ROS 依赖轻量重放与风险监控。
- 设计**中立动作流 Handoff 机制**：模型预测导出为 `predicted_actions.jsonl` + manifest，下游不装 ROS / PyTorch 即可重放，实测 1-ep `panda_jsonl_replay` + `pybullet_ik`：1,105 行时序、mean 18.0 ms / max 357.7 ms、`is_closed_loop=false`。
- 冻结 **Isaac 有界 rollout runtime 合同单源**：`chunk_size=10` / `execute_K=5` / `10 Hz` / `replan_period=0.5 s` / `gripper=clip(raw,0,1)` / scene-only / `state[15]` / clamp+E-stop / **seeds 1–5 有界**；上游包内保留字节相同副本并在启动时 assert，禁止静默双写，CPU 契约单测覆盖。
- 用 **scripted oracle 做仿真链自检**：oracle v1 lift 0/5 → 修 pick 高度、PD 夹爪、方块摩擦、grasp pause、5 cm 方块侧夹阈值 → v2b **lift 5/5 / `gate_pass=true`**，把「仿真抓不起来」与「策略抓不起来」彻底分开。
- 做**跨后端同域对照**：同一 checkpoint 在 Isaac（修光后 policy 输入 JPEG≈154）与训练域 MuJoCo（JPEG≈50）均出现 `gripper never closed below 0.700`，因此**不把失败主要归因于 MuJoCo→Isaac 外观域差**，而指向闭环 BC；同时明确该对照是人工提前停止的 1-seed 结果，**不是完整 gate**。
- 严格执行**运行卫生**：所有仿真 / ROS 任务带显式生命周期上限（`timeout` / `auto_record_seconds`），结束前强杀 `teleop_bringup` / `mujoco_sim` / `lerobot_recorder` / `servo_node` / `ros2_control`，不把清理推给下一次运行。

## C.2 100–150 字概述

我搭建了一套跨 MuJoCo、Isaac Sim 和 PyBullet 的具身闭环验证平台。上游负责实时控制与采集，中游负责数据治理、训练与门禁，下游用无 ROS 依赖的中立动作包做轻量重放与风险监控，三仓通过 schema 与 handoff 契约解耦，避免依赖冲突。仿真侧我把运行时常量做成单源合同并在启动时校验，用 scripted oracle 自检物理链，用跨后端同域对照区分外观域差与闭环策略问题。当前结论是离线门禁通过、有界在线仿真 Hold，属于 Sim2Sim 与 Sim2Real-readiness，不宣称真机。

## C.3 30 秒介绍

> 「我做的是多仿真后端的闭环验证平台。三个仓分别跑实时控制、训练治理和轻量重放，靠 schema 和中立动作包解耦，下游不用装 ROS 或 PyTorch 就能重放策略输出。仿真评测这块我做了三件关键事：把 runtime 常量（chunk、K、控制频率、夹爪 clip）做成**单源合同**并在上游启动时 assert，防止双写漂移；用 scripted oracle 自检物理链，v1 也抓不起来时先修仿真而不是骂模型，修完 5/5；做跨后端同域对照，确认失败不是 MuJoCo 到 Isaac 的外观差。范围上我说清楚这是 Sim2Sim 和 Sim2Real-readiness，不是真机。」

## C.4 2 分钟案例：用 scripted oracle 隔离物理链

- **Situation**：ACT 在 Isaac 有界 rollout 里 lift 0/20。团队里最容易出现两种错误结论：「模型不行」或「Isaac 根本抓不起来」。
- **Task**：在不继续堆训练的前提下，判定失败责任在**仿真物理链**还是在**学习到的策略行为**。
- **Action**：
  1. 写一个固定 FSM 的 **scripted oracle**（专家式动作序列），跑同一条 Isaac 抓取链、同一套连续真值判定。
  2. **v1 结果：oracle 也 lift 0/5** —— 说明当时不能把失败归给策略。
  3. 逐项 triage 并修复：pick 高度、PD 夹爪控制、方块摩擦、grasp pause、5 cm 方块的侧夹阈值。
  4. **v2b 结果：reach / grasp / lift 5/5，`gate_pass=true`**，并补录成功 lift 视频作为可视对照。
- **Result**：确立「名义物理链可用」这一系统上界，把后续所有 learned-policy 失败的讨论**限定在 home → 对准 → 闭合的行为层**；同时明确 **oracle 成功 ≠ learned-policy 成功**，oracle 只是系统参考，不进任何策略成功率。
- **可验证**：`evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/`（v1 失败对照）、`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/oracle_gate.json`（v2b 通过）、`docs/portfolio/media/e3p5_isaac_scripted_oracle_lift_success_trial0.mp4`。

## C.5 失败归因案例（版本 C 口径）

见[通用失败归因案例](#通用失败归因案例把自己的正向指标证伪)，C 版本强调**「跨后端对照才能分清域差与策略」**。

---

# 通用失败归因案例：把自己的正向指标证伪

> 三套版本共用。这是最能体现「测试/评测工程师」价值的一段，建议作为面试主案例。

- **Situation**：SmolVLA Recovery v3 在独立 prospective 评测集上离线门禁 **Pass**（EE RMSE 0.0253 m、gripper balanced accuracy 0.9943、close-edge beyond-ε 0.386%）。人工批准后跑有界 Isaac S4（seeds 1–5）。首轮结果：interface **5/5**，**reach 3/5、grasp 1/5**，lift 0/5。
- **Task**：这个 reach 3/5 · grasp 1/5 能不能写成「已经具备部分视觉伺服能力」？
- **Action**：
  1. **先怀疑口径**：查连续真值定义，发现 `GRIPPER_CLOSE_MAX=0.70` 会把「半闭」（`grip_min≈0.21–0.28`）判为 closed，reach 也可能只是走廊几何重叠。
  2. **排除 state 编码（H3）**：比对训练 release 的 `observation.state[15]`（N=2,593）与在线遥测（N=750）：home 关节 L2 `0.006`、四元数 L2 `6.8e-6`、夹爪同 `[0,1]` 量纲 → **不是** joint 顺序 / ee 系 / 归一化搞错。
  3. **补相机遥测**（人工批准，不扩种子）：dump 每步 policy 输入 JPEG，发现像素均值 **≈0.3**（近黑），而 MuJoCo 训练帧 ≈50、同 harness 的 oracle 视频 ≈114 → 主因升级为 **H1′：Isaac 离线场景缺有效光照**，策略在失明状态下走「习惯走廊」。
  4. **修光并用同 seeds 复测**：加 Dome 450 + Distant 900 后 JPEG≈154，视觉可用。结果反而更差：**reach 1/5、grasp 0/5、lift 0/5**，5/5 seeds 报 `gripper never closed below 0.700`。
  5. **把首轮标注为 `Superseded`**，权威 S4 改为修光后的 relight run，并**重出 funnel / per-seed 图表**（数字从 gate JSON 读取，不硬编码）。
  6. **再做训练域对照（H2）**：同 checkpoint 在训练域 MuJoCo（JPEG≈50）上跑，seed1 仍 `grip_min≈0.976`、几乎不下探 → 归因倾向**闭环 BC / 协变量偏移**，而不是 MuJoCo→Isaac 外观域差。
- **Result**：
  - 最终对外结论：**离线 Pass + 有界在线 Hold（lift 0/5）**，`gate_pass=false`，不扩种子、不重训、不上真机。
  - 排除清单可追溯：数据泄漏（train-only 物化 + split 无交集）、接口（interface 5/5、150/150 未限幅、无 E-stop、checkpoint audit Pass）、物理链（oracle 5/5）、state 编码（H3）、相机失明（修光后仍 Hold）。
  - **保留的谨慎**：训练域 MuJoCo 对照是人工提前停止的 **1-seed** 完整真值，因此「协变量偏移是唯一根因」**尚未被完全证明**；async queue 已做 offline 实测（sync miss 20%→async 0.67%），但上游在线节点仍未接线；降级的假设仍保留在矩阵中。
- **面试收尾一句话**：「我最满意的不是那个 0.0253 m，而是我们主动把自己看起来更好的 reach 3/5 证伪成了 1/5。」
- **可验证**：`docs/portfolio/BADCASE_ATTRIBUTION_SUMMARY.md`、`docs/SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md`、`evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json`。

---

# 高频 Q&A（通用）

### Q0：SmolVLA 现在到哪一步了？能不能说已经抓起来了？

> 「不能。**离线 open-loop 门禁过了**，有界在线仿真仍是 **Hold**。Recovery v3 在独立 10 条 held-out 全帧评测上 EE 约 2.5 cm、夹爪 balanced accuracy 约 0.99，并且我们按执行侧 `clip(raw,0,1)` 修订了严重度口径。人工批准后跑了 **有界 Isaac S4（seeds 1–5，`ran_isaac=true`）**：policy interface 5/5，但连续真值 **lift 0/5**，`gate_pass=false`。所以我不会写任务成功率，也不会写 Sim2Real。」
>
> 一页纸：[`SMOLVLA_RECOVERY_V3_PORTFOLIO.md`](SMOLVLA_RECOVERY_V3_PORTFOLIO.md) · 总结：[`FINAL_PROJECT_SUMMARY.md`](FINAL_PROJECT_SUMMARY.md)

### Q0.5：你修改了 Gate 阈值，是不是为了刷过？

> 「不是。修订的是**严重度语义**：执行端下发的夹爪命令本来就是 `clip(raw, 0, 1)`，而 v2 的 Hold 全部来自**开爪边**的预裁剪过冲 —— 那些帧专家值本身是 1.0，裁剪后是同一个『完全张开』命令，分类和闭合时序变化都已经是 0。所以我把开爪边幅值降为**诊断项**，同时**关爪边 beyond-ε ≤1%、clip 分类变化 0、闭合时序变化 0** 仍是硬门禁，`[-0.5, 1.5]` 之外直接 No-Go。三条约束保证这不是放水：阈值 **SHA256 冻结**、**历史 v2 Hold 不追溯改判**、评测集**重新采集**（因为原来那 10 条已被阈值设计污染）。」

### Q1：为什么分三个仓？

> 「环境冲突与实时性隔离。上游要 ROS 2 实时控制栈，中游要 PyTorch/CUDA 深度学习环境，下游物理重放要高频碰撞结算。塞一个仓里依赖会互相踩。我用**中立动作流 Handoff** 解耦：中游输出标准 `jsonl` 动作包 + manifest，下游不装 ROS 或 PyTorch，只要 Python + PyBullet 就能重放。这既方便本地轻量调试，也为将来上真机留了接口 —— 但目前明确还没有做真机。」

### Q2：数据契约规范了什么？

> 「机器人状态/动作最容易发生静默漂移，所以我用 YAML Schema 固定：`observation.state`（Panda 关节 + 夹爪）、`ee_pose[7]`、可选 `object_pose[7]`、`ft[6]`、scene RGB 320×240@10 Hz；action 分两种语义 —— ACT 用 `ee_delta_gripper[7]`，VLA 用 `absolute_eef_gripper[8]`。关键设计有两条：一是 `object_pose` 是**仿真特权信息，禁止进 policy state**，否则破坏 Sim2Real-readiness；二是 `filter_scope=training_split_only`，物理成败判定归上游，中游只校验 schema 与 split，**不重复推导**物理成功，避免多头定义。」

### Q3：VLA 的 policy input 契约你踩过什么坑？

> 「踩过一次很典型的静默漂移：v1/v2 的 checkpoint 声明 `observation.state[6]`，而 release 的关节状态是 `[7]`，`ee_pose` 和 `gripper` 直接被 preprocessor 丢掉了。也就是说训练时策略根本没看到末端位姿和夹爪状态。修复方式是把 `state[15]`（`joint[7] + ee_pose_xyzw[7] + gripper[1]`）显式组装进数据集和 preprocessor，并加 **checkpoint config audit**：同时核验 policy 与 preprocessor 的 state 维度、camera key、`action` 维度、chunk / K 和 PEFT 正则，全项 Pass 才允许评测。这类问题不会报错，只会静默变差，所以必须靠契约测试而不是靠看 loss。」

### Q4：下游物理沙盒为什么不评估抓取成功率？

> 「职责隔离。下游 PyBullet 重放做的是几何/运动学层面的执行质量与 readiness 风险：轨迹偏差 RMSE、雅可比最小奇异值（<0.01 预警奇异性）、关节分布漂移（KL / Wasserstein）、速度跳变、软限位触发。物理抓取成败在**上游采集时由主轨自动标记**并存进 episode 属性，或由上游连续真值评测器判定。中下游都不重新推导，避免物理逻辑多头定义。而且下游 offline risk 的 R-level 有硬约束：`use_as_task_go_no_go=false`、`overrides_failure_lane=false`。」

### Q5：既然 lift 0/5，这个项目算失败吗？

> 「作为『训练一个能抓取的策略』它没达成；作为**评测与验证工程**它达成了目标。它交付的是：可复现的分层门禁、SHA256 冻结的判定契约、跨后端统一报告信封、能证伪自身正向指标的归因链，以及七次明确的止损决策（不扩种子、不第三次 data-fix、不盲训 ACT、不启动 100+ rollout 的 E4）。在真实工程里，能准确说出『现在还不行、瓶颈在哪一层、下一步该验什么』比给出一个来源不明的成功率更有价值。」

### Q6：接下来打算做什么？

> 「P1 已在获批范围内完成两类 open-loop 扰动诊断和一次 offline async queue 实测：本机上 sync 重规划有 20% tick 超过 100 ms，double-buffer 降到仅冷启动 1 次，但上游在线节点尚未接线。其余 P1（闭环分布偏移量化、MuJoCo 5-seed、Policy Adapter wrapper）与全部 P2 都只登记，仍需显式批准；P2 的策略改进和扩 seed 还以前置量化证据与外部 GPU 为条件。清单见 [`FUTURE_WORK_ROADMAP.md`](../FUTURE_WORK_ROADMAP.md)。」

---

# 禁止话术清单（写简历/面试前自查）

| 禁止 | 应该说 |
|---|---|
| 「SmolVLA 已完成抓取 / 已 Sim2Real / 已上真机」 | 「离线 open-loop 门禁 Pass，有界 Isaac 仍 Hold，lift 0/5」 |
| 「open-loop Pass = 任务成功」 | 「Pass 只代表专家状态分布上的 first-action 离线判定通过」 |
| 「`ran_isaac=true` = Sim2Real」 | 「跑过有界仿真 rollout，属 Sim2Sim / Sim2Real-readiness」 |
| 「interface 5/5 / reach 计数 = 部分抓取成功」 | 「接口全通过但任务真值 0；reach 含几何重叠与阈值口径」 |
| 「改门槛是为了刷过」 | 「按 `clip(raw,0,1)` 执行语义修订严重度；关爪边与不变式仍硬挡；历史判定不改写」 |
| 「离线 loss 下降 = 成功率提升」 | 「当前证据不足，无法确认」 |
| 「`queued_diagnostic` 也过了」 | 「queued 只作诊断，永不具备 canonical Gate Pass 资格」 |
| 「Isaac 抓不起来」 | 「scripted oracle lift 5/5，物理链可用；瓶颈在 learned policy 闭环行为」 |
