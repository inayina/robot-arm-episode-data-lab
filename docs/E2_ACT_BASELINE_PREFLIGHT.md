# E2 ACT Baseline Preflight

关联日常评测执行手册：[`EMBODIED_POLICY_EVALUATION_SOP.md`](EMBODIED_POLICY_EVALUATION_SOP.md)
（home/warmstart 分层、判定标签、止损门与失败归因）。

状态：**本文的早期 preflight 已完成；后续 E2/E3 diagnostic 也已关闭。权威 E3 nominal20
为 0/20，E3.5 scripted oracle lift 5/5，close→lift 定向模型 5-seed 仍 lift 0/5；不开完整 E4。**

当前总报告见 [`EVALUATION_REPORT.md`](EVALUATION_REPORT.md)。下文保留 preflight 和中间 A/B
过程，用于复现实验演进，不应覆盖最新 Go/No-Go。

E2 原路线的“约 50 条”是里程碑目标，不是无条件扩采许可证。项目已根据 home 行为和真实
task GT 触发止损；不能把 5 条 preflight 描述成完整 E2，也不能把后续 offline 指标描述成
learned-policy 抓取成功。

## 已实现并有运行证据

- 上游仓库：`ros2-arm-teleoperation-suite`
  - MuJoCo 真实 Renderer，scene RGB 为 320×240、10 Hz；不是 synthetic fallback。
  - `grasp_assist_enabled=false`，5 条均由 `batch_generator` 物理门禁接受。
  - 5 条 episode 共 1537 帧，视频帧数为 302/308/311/308/308。
  - 相机为完整任务斜俯视；左/右篮位于画面左/右，机械臂、夹爪、物体和运输路径均入镜。
  - `stop_stack.sh` 对完整节点集合执行 TERM → bounded wait → KILL → zero-residue check。
- 中游仓库：`robot-arm-episode-data-lab`
  - release id：`e2_rendered_scene_20260718_v1`。
  - `state[8]`、`ee_delta_gripper[7]`、scene RGB `[240, 320, 3]` inspection PASS。
  - episode-level split：episode 0–3 训练、episode 4 验证（1229/308 帧）。
  - LeRobot ACT、chunk size 50、1 epoch、batch size 8，在 RTX PRO 500 Blackwell Laptop
    GPU（CUDA 13.0）完成；checkpoint 可在 CPU 反加载为 `ACTPolicy`。
  - 验证原始动作 L1 `0.0234662350`，normalized L1 `0.4638658399`，夹爪开闭分类准确率
    `0.9078659612`，训练/评估耗时 `21.024 s`。

机器可读证据：

- `evidence/e2_act_preflight/release_manifest.json`
- `evidence/e2_act_preflight/inspection_report.json`
- `evidence/e2_act_preflight/act_1epoch_metrics.json`

## 10 条随机化采集 preflight

2026-07-18 在本机顺序运行 MuJoCo Renderer 批采，配置为红方块、
`randomize=true`、`grasp_assist_enabled=false`、320×240、10 Hz。11 次尝试中有
10 条通过上游 `batch_generator._validate_episode` 的 lift/place 物理门禁，1 条漏抓被丢弃；
accepted 轨迹共 3056 帧。

中游 `adapt_upstream_panda_dataset.py --derive-ee-delta-action --inspect` 和独立
`inspect_dataset.py` 均 PASS：`state[8]`、`ee_pose[7]`、`action[7]`、FT `[6]`，10 个
scene RGB 视频均为 320×240、10 Hz。适配产物显式记录
`upstream_gate=batch_generator` 和 `filter_scope=training_split_only`，中游没有从
`observation.object_pose` 重复推导物理成败。

本机生成产物：

- 上游数据：`/home/ina/dev/ros2-arm-teleoperation-suite/data/e2_randomized_scene_episodes`
- 上游门禁证据：`/home/ina/dev/ros2-arm-teleoperation-suite/evidence/e2_randomized_scene_episodes`
- 中游适配：`data/e2_randomized_adapted`
- 中游检查：`data/e2_randomized_inspection.json`

运行时三秒 `mpstat` 抽样为整机平均 37.93% active、62.07% idle；没有观察到由资源
竞争造成的批次失败。该短窗口只能证明本轮本机负载有余量，不是所有工作负载的容量上限。

## 当前 Isaac 与 MuJoCo 场景差异

两者已完成**标称几何与初态对齐，但物理与分布仍不等价**。Isaac 现在有 ground、Panda、
5 cm / 0.03 kg 红方块、左右篮和 scene camera；Panda home、红块初态、篮中心以及近似相机
视点均按 MuJoCo 标称配置设置。蓝圆柱、绿球、材质/接触参数对齐和 `randomization.yaml`
同语义随机化仍未实现。

| 项目 | MuJoCo 采集场景 | Isaac smoke 场景 |
|---|---|---|
| 红物体 | 5 cm 立方体，0.03 kg，初始 `(0.35,-0.07,0.025)` | 标称尺寸、质量、初态已对齐 |
| 篮子 | `(0.4,±0.35,0.02)` 左右两篮 | 中心位置和近似外形已对齐 |
| Panda 初态 | controller nominal home | 7 关节 nominal home 已对齐 |
| 其他物体 | 蓝圆柱、绿球 | 未实现 |
| 随机化 | 位置、质量、摩擦、相机、光照 | 未实现同语义映射 |
| 视觉 | MuJoCo `scene_camera` | 相机位置/视点近似对齐；渲染域未标定 |
| 物理 | MuJoCo 接触、摩擦、阻尼 | PhysX 默认接触；参数未做配对标定 |

因此当前 Isaac 已适合 nominal 接口/执行和单次端点任务检查；还不适合把 MuJoCo 与 Isaac
pick/place 成功率当作公平的 Sim2Sim 物理对比。正式比较前仍需对齐材质/接触参数、渲染域、
随机化 seed 语义，并实现连续 object/contact ground-truth evaluator。

## ACT→Isaac 有界接口 smoke

上游已加载本页所述真实 ACT checkpoint，并把真实 Isaac joint/camera/EE/gripper 观测转换为
checkpoint 所需输入。运行时把 inference 和 execution 分开判定，避免“模型推理成功”掩盖
“机械臂执行发散”。

- `panda_hand` 到数据契约 `panda_ee` 的本地 `+Z 0.10 m` 固定变换已补齐；与 URDF FK 的
  位置误差为 `1.382e-7 m`。
- effort 模式下，Servo 目标最大只变化 `0.024880 rad`，但实际关节最大变化 `2.8973 rad`、
  EE 最大变化 `1.1741 m`，安全 E-stop 正确触发。问题位于跨进程、低反馈频率的 effort
  执行边界，不在 checkpoint 输出或 Servo 目标生成。
- 默认 smoke 改为 ACT → MoveIt Servo → 有界 `/joint_target` → Isaac-local position drive；
  三步动作 inference/execution/overall 均 PASS，最大关节变化 `0.0729 rad`、最大 EE 位移
  `0.004123 m`、`safety_ok=true`、`estop=false`。
- 三步运行 GPU 全窗口平均 8.857%、非零样本平均 9.864%、峰值 11%；VRAM 从 1683 MiB
  增至 2232 MiB。Isaac 启动阶段的整机 CPU 抽样平均 19.1%、峰值 33.04%；Isaac 单进程
  平均约 1.675 个逻辑核、峰值约 3.59 个逻辑核。

机器可读证据位于上游
`evidence/e2_act_isaac_smoke_20260718/summary.json`。这只证明三步有界接口 smoke，不证明
机械臂已经完成抓放，也不证明 learned-policy task success。

## 500 Hz tiny ACT → Isaac 20-action 有界闭环（2026-07-19）

为尽快形成可用于作品集的诚实闭环，本轮只使用 `write()` 异步发布与 500 Hz encoder 修复后的
真实 MuJoCo 数据；没有混入旧 1000 Hz episode，也没有使用 synthetic/fake video。

- 上游 seed 42/43 共 10 条 accepted 随机红块 episode，均为真实 MuJoCo Renderer、
  `grasp_assist_enabled=false`，中游合并后为 3289 帧、10 个 320×240@10 Hz 视频。
- immutable release：`data/releases/e2_500hz_random10_20260719`，inspection PASS，
  `upstream_gate=batch_generator`、`filter_scope=training_split_only`。
- 真实 LeRobot ACT 训练 3 epochs，训练 loss 为 `3.3977 → 1.1549 → 0.6415`；episode-level
  validation L1 `0.011165`、normalized L1 `0.298236`、gripper accuracy `0.970526`，耗时
  `107.19 s`。checkpoint SHA-256 为
  `fb278200066caa214695285a6d078061d27bf202d14f6b64e1d4c5072132e8b0`。
- 对齐后的真实 Isaac position-drive 运行完成 20/20 个在线推理动作，interface/execution
  `PASS`，`safety_ok=true`、`estop=false`，EE 最大位移 `0.005114 m`、关节最大位移
  `0.0108 rad`。
- task 结果为 `FAIL`：20 个动作的最小 gripper command 仍为 `1.0`（全程张开），红块端点
  位移仅 `2.11e-8 m`，距左篮中心 XY 仍为 `0.2844 m`。因此不能声称抓放成功。
- 推理延迟 p50/p95/max 为 `87.84/426.61/539.78 ms`；GPU 平均/峰值
  `13.65%/18%`，VRAM 1683→2266 MiB。

机器可读汇总和简报：

- `evidence/e3_act_tiny_500hz_aligned_20action_v3_20260719/summary.json`
- `evidence/e3_act_tiny_500hz_aligned_20action_v3_20260719/report.md`
- 上游原始运行证据：
  `/home/ina/dev/ros2-arm-teleoperation-suite/evidence/e3_act_tiny_500hz_aligned_20action_v3_20260719`

该结果证明 checkpoint 加载、真实在线推理、Isaac 有界执行、安全处理和自动报告生成已闭环。
它仍不是完整 E2（路线要求约 50 条 accepted episode），也不是完整 E3（仅 1 次而非 20 seeds，
且只有端点 object pose 检查，没有连续 lift/contact/outcome evaluator 或成功 rollout）。

## 单红块阶段均衡采样 A/B（2026-07-19）

中游 `train_act_lerobot.py` 新增可选 `--stage-balanced-sampling`。它只根据每个 episode 已验证的
gripper command 时序识别 `grasp_context`、`closing`、`closed_transport` 和 `release`，不读取
`observation.object_pose`、不重新判定 lift/place 成败，也不修改 release/schema/action。训练使用
`WeightedRandomSampler(replacement=true)` 且每个 epoch 样本总数保持不变；验证集继续顺序、
无权重采样。`closed_transport` 只是“闭合结束到释放开始”的时序名称，不是物理运输成功声明。

真实训练集原始锚点分布为：other `59.16%`、grasp context `3.04%`、closing `8.43%`、
closed transport `19.76%`、release `9.61%`。

两组 3-epoch A/B 均使用同一 release、episode split、seed、batch size、学习率和 Isaac 场景：

| 组别 | context/close/transport 权重 | 期望采样特点 | 离线 L1 / gripper acc | 真实 Isaac 20-action 结果 |
|---|---:|---|---|---|
| aggressive | `2/4/3` | closing+transport `55.41%` | `0.01704 / 93.87%` | 第 3 步过早闭合；18/20 动作限幅；红块未移动，task FAIL |
| context-first | `4/2/1.5` | other `46.42%`、context `9.54%`、closing `13.24%`、transport `23.26%` | `0.01745 / 95.08%` | 20 步仍全程张开且近静止；红块未移动，task FAIL |

context-first 是当前代码默认的保守增权配置，避免 aggressive 组明显的提前闭合和大动作；但它
没有证明任务改善，不能作为成功 checkpoint。两组真实运行均 interface/execution PASS、
`safety_ok=true`、`estop=false`，因此当前止损结论是：**停止继续扫权重，优先补采单红块数据**。
建议先从 10 条增加到 20–30 条，重点扩大有效 approach、闭合前 1–2 秒和稳定 lift/transport
轨迹的初态变化；权重不能创造现有数据中不存在的视觉—动作对应。

证据：

- `data/e2_500hz_act_stagebalanced_3epoch_20260719/metrics.json`
- `evidence/e3_act_stagebalanced_500hz_20action_20260719/summary.json`
- `data/e2_500hz_act_stagebalanced_v2_3epoch_20260719/metrics.json`
- `evidence/e3_act_stagebalanced_v2_500hz_20action_20260719/summary.json`

## 20-episode approach 补采 + 保守 5-epoch Isaac A/B（2026-07-19）

在上一轮“停扫权重、先补数据”结论上，追加 10 条单红块 accepted episode（seed 44/45 各 5），
合并为 20-ep release 后用保守阶段权重训 5 epochs，再对 Isaac nominal 20-action 做 A/B。

采集约束未变：单红块、`grasp_assist_enabled=false`、真实 MuJoCo Renderer、500 Hz encoder、
`validation_mode=place`。相对 seeds 42/43，补采扩大 Y 到 `[-0.14, 0.16]`、红块 yaw `±15°`，
并把 `record_warmup`/`grasp_pause`/`post_lift_hold` 压到 `0.8/1.5/1.5` 以减少 idle。

| 产物 | 路径 / 结果 |
|---|---|
| 上游 seed44/45 | `ros2-arm-teleoperation-suite/data/e2_red_500hz_seed44_approach10_strict_20260719`（5）、`..._seed45_approach5_...`（5） |
| release | `data/releases/e2_500hz_random20_approach_20260719`：20 ep / 5660 frames，inspection PASS |
| 训练 | `data/e2_500hz_act_random20_conservative_5epoch_20260719`：loss `2.50→0.37`，val L1 `0.0115`，gripper acc `96.0%`；权重 context/close/transport=`4/2/1.5`，`grasp_context_frames=15` |
| Isaac B | `evidence/e3_act_random20_conservative_5epoch_20action_20260719/summary.json` |

Isaac nominal A/B（同一 20-action 有界协议）：

| 组别 | 数据 / 训练 | min gripper | 是否出现先接近再闭合 | task |
|---|---|---:|---|---|
| A baseline | 10-ep context-first 3ep | `1.0` | 否（全程张开） | FAIL |
| B this run | 20-ep conservative 5ep | `0.995` | 否（几乎不动的微开） | FAIL |

B 完成了 20 个在线推理动作且 `safety_ok=true`、`estop=false`、红块端点位移≈0；
interface/execution 曾记为 FAIL（startup timeout 误伤长跑），但夹爪命令从未进入闭合区。
**当时止损：不扩到 30–50 条；优先检查动作时序 / ACT chunk 执行。**

## ACT chunk 执行修复与复测（2026-07-19）

离线诊断证明：`SceneACTRuntime.infer` 原先每次只取
`predict_action_chunk(...)[0, 0]`。在接近/闭合帧上，chunk 后续步已闭合到 ~0，但第 0 步仍
~1.0，部署侧因此永远看不到闭合。

已实现：

- `scene_act_runtime.py` 改为 `policy.select_action()` 消费 chunk 队列；`reset()` 在 smoke
  边界清空队列。
- `policy_inference_node.py`：startup timeout 仅在 `completed_actions==0` 时触发。
- 回归：`tests/test_scene_act_runtime_chunk_queue.py`。

复测证据：`evidence/e3_act_random20_chunkfix_20action_20260719/`（上游与中游同名）。
接口 `PASS` 20/20；首帧推理 ~1.1 s、后续 ~30 ms，确认队列在走。但 Isaac **home 初态**
下整段 chunk 的 gripper 仍 ~0.995–1.0（`STILL_OPEN`），与离线 ep0 第 0 帧“全程张开 chunk”
一致。

放宽 envelope 的 50-action@5 Hz 复测
（`evidence/e3_act_random20_chunkfix_50action_approach_20260719/`）：EE 有位移但夹爪仍
~0.99–1.0，XY 未真正逼近抓取点（`APPROACH_NO_CLOSE`）。因此：**chunk bug 已修，但仍不能
仅靠扩 episode 解决**；瓶颈是 home→pregrasp 视觉区进入，而非“闭合标签学不会”。

## Pregrasp warmstart 诊断（2026-07-19）

为验证“进入接近区后是否会闭合”，在 Isaac smoke 增加可选 pregrasp warmstart
（`scripts/isaac_pregrasp_warmstart.py` + `PREGRASP_WARMSTART=true`）：先把 EE 插值到物体
上方再跑 policy。Warmstart 本身**不计** task success。

| 项 | 结果 |
|---|---|
| 证据 | `evidence/e3_act_random20_chunkfix_50action_warmstart_20260719/` |
| Warmstart | `ee_obj_xy≈0.0002 m`，EE z≈0.069（物上约 4 cm） |
| Interface | `PASS` 50/50；`safety_ok=true`，`estop=false` |
| Gripper | min=`0.0`；约第 27 步 `<0.5`，第 43 步起 `0.0`（`CLOSE_SEEN`） |
| Object | 端点位移 ≈`1.4e-5 m`（未抬起）；task 仍 `FAIL` / `task_success_not_established` |

**结论**：同一 20-ep conservative checkpoint，在 pre-close 视觉态下**会命令闭合**；home
起步失败主因是未进入该态，不是闭合头彻底坏掉。

注意：该次 warmstart 中 `workspace_min.z` 默认仍为 `0.15`，39/50 步
`workspace_clipped`，目标 z 被抬到 ≥0.15，物体位移≈0（空中闭合）。

## 闭环 replan + 可抓取 workspace 地板（2026-07-19）

两处部署修复：

1. **`n_action_steps` 可覆盖**（默认 0=checkpoint `chunk_size=50`）。小于 chunk 时队列更快耗尽，
   `select_action` 更频繁按最新观测 replan。开关：`N_ACTION_STEPS` /
   `policy_inference_node` 参数 `n_action_steps`。
2. **`workspace_min.z` 默认 `0.15→0.02`**，否则无法下到物体高度（~0.025 m）。Smoke 可用
   `WORKSPACE_MIN` / `WORKSPACE_MAX` 覆盖。`max_actions` 上限放宽到 200。

对照跑：

| 协议 | 证据 | grip | z | clips | object Δ | 判定 |
|---|---|---:|---|---:|---:|---|
| home, n=8, ws z=0.02, 100@5Hz | `evidence/e3_act_random20_home_n8_ws02_100action_20260719/` | min≈0.995 | 源/目标均≈0.48–0.49（几乎不降） | 0 | ≈0 | `HOME_APPROACH_NO_CLOSE`（XY 0.082→0.057 m） |
| warmstart, n=8, ws z=0.02, 50@5Hz | `evidence/e3_act_random20_warmstart_n8_ws02_50action_20260719/` | min=0.0（约第 16 步 `<0.5`） | 源≈0.033–0.065 | 0 | ≈**7.0 mm** | `WARM_CLOSE_CONTACT` |

**结论**：

- 闭合与轻接触在 **pregrasp + 可下降 workspace** 下已证实；先前 warmstart“闭合但不碰物”主要是
  z 地板误伤，不是策略完全不会抓。
- home 起步在短 horizon replan 下开始有 XY 接近，但仍**不降 Z、不闭合**；瓶颈仍是
  home→pregrasp（尤其竖直接近），不是再堆 episode 权重。

**止损不变：不扩到 30–50 条。** 下一优先：加长 home 有效接近（更多 steps / 更大单步
translation 或显式阶段 curriculum），直到出现 home→降 Z→闭合；评估继续区分
`home_start` vs `pregrasp_warmstart`。

上游开关：`PREGRASP_WARMSTART` / `N_ACTION_STEPS` / `WORKSPACE_MIN`（见
`ros2-arm-teleoperation-suite/scripts/run_isaac_act_smoke.sh`）。

## Home 加长评测 + 针对性 hover→descend 补采（2026-07-19）

按 ROI 顺序执行（**不是**均匀冲到 50）：

### A. 20-ep checkpoint，加长 home
`evidence/e3_act_random20_home_n8_ws02_200action_tx03_20260719/`：200@5Hz，
`n_action_steps=8`，`max_translation=0.03`，ws z=0.02。

- XY：0.082→**0.041** m（有接近）
- Z：几乎只掉 ~13 mm；`bnd_dz<-5mm` = 0
- grip min≈0.995 → **`HOME_DESCEND_NO_CLOSE`（弱降）/ 实质仍不闭合**

### B. 针对性 +10（seeds 46/47），合并 30-ep
| 批 | 路径 | 设定 |
|---|---|---|
| seed46×5 | `.../e2_red_500hz_seed46_descend5_highhover_20260719` | hover_h=**0.18**，descend=**5.5** s |
| seed47×5 | `.../e2_red_500hz_seed47_descend5_midhover_20260719` | hover_h=**0.14**，descend=**5.0** s |
| release | `data/releases/e2_500hz_random30_descend_20260719` | **30 ep / 7727 frames**，inspection PASS |
| train | `data/e2_500hz_act_random30_descend_conservative_5epoch_20260719` | 5ep，权重 4/2/1.5；loss~0.34，grip acc~95.3% |

### C. 30-ep home 复测
| 证据 | 结果 |
|---|---|
| `.../e3_act_random30_descend_home_n8_ws02_200action_tx03_20260719` | 9/200 即因 joint excursion>1.0 rad + estop 中断；已见明显降 Z（span~0.17 m） |
| `.../e3_act_random30_descend_home_n8_ws02_200action_j1p5_20260719` | 放宽到 1.5 rad 后仍 13/200 护栏；z span~**0.255** m（0.49→0.24）；XY 0.082→**0.121**（漂远）；grip min~0.988 → **`HOME_DESCEND_NO_CLOSE`** |

**结论**：针对性 descend 补采**有效**（home 终于会大幅降 Z）；但仍未出现
home→对准物体→闭合。当前失败模式是 **降 Z + XY 漂移 + 关节行程护栏**，不是“条数不够 50”。

**仍不扩到 50。** 下一优先（更高 ROI）：

1. 控制侧：降速 / 限幅 / 更大 joint budget，让长时域 home rollout 跑完而不 E-stop；或
2. 数据侧：补 **XY 对齐后再降** 的轨迹（不是再堆纯高悬停下降），再评估是否闭合。

## 控制侧：关节预算 + 长时域跑完（2026-07-19）

先做控制侧（按 ROI 优先于再采数据）：

| 改动 | 说明 |
|---|---|
| `MAX_JOINT_EXCURSION_RAD=3.0` | home→低位 pick 常需 >1.5 rad；先前 1.0/1.5 过早 E-stop |
| `MAX_TRANSLATION_M=0.015` | 略降单步，减轻暴力关节跳变 |
| `BACKEND_DURATION_SEC` 可配 | 修 smoke 后端写死 100s 掐断长跑 |
| `policy_inference_node._flush_report` | 达 `max_actions` 立即落盘 `report.json`，避免 teardown 丢报告 |

主证据：`evidence/e3_act_random30_descend_home_n8_ws02_160action_j3_tx015_reportfix_20260719/`

| 指标 | 值 |
|---|---|
| Interface | **PASS** 160/160；`estop=false`，`safety_ok=true` |
| joint / ee excursion | 2.72 rad / 0.44 m（未护栏跳闸） |
| Gripper | min=**0.0**；约第 32 步 `<0.5`，第 40 步 `<0.1`（**会闭合**） |
| Z | span≈**0.27** m（0.49→最低≈0.22） |
| XY→物体 | start 0.082 → best **0.071**（很早）→ end **0.312**（闭合时已漂远） |
| 判定 | **`HOME_CLOSE_MISALIGNED`** |

**结论**：控制侧成功——home 长时域可跑完，且会出现闭合；剩余主因是 **未先对准物体再降/闭**（XY 漂移）。
**仍不扩到 50。** 下一步转数据侧：补「先 XY 对齐再降」轨迹后复训/复测。

## 数据侧：XY-align-then-descend +10 → 40-ep（2026-07-19）

实现与采集：

| 项 | 内容 |
|---|---|
| 代码 | `batch_generator.approach_xy_duration`；smoke：`BATCH_PREFLIGHT_APPROACH_XY_DURATION` / `USE_READY_POSE` |
| seed48×5 | `.../e2_red_500hz_seed48_xyalign5_home_20260719`：`use_ready_pose=false`，approach_xy=**6.0** s，hover_h=**0.10**，descend=4.5 s |
| seed49×5 | `.../e2_red_500hz_seed49_xyalign5_home_20260719`：approach_xy=**5.5** s，hover_h=**0.12**，descend=4.0 s |
| 日志确认 | Phase 1a 从 home `(0.307,0,0.49)` 做 approach_xy（无 ready） |
| release | `data/releases/e2_500hz_random40_xyalign_20260719`：**40 ep / 9666 frames** |
| train | `data/e2_500hz_act_random40_xyalign_conservative_5epoch_20260719`：loss~0.34，grip acc~96.6% |

Isaac home（同控制信封 j3 / tx0.015 / 160@5Hz）：

| ckpt | 证据 | grip | z span | XY best | 判定 |
|---|---|---:|---:|---:|---|
| 30-ep descend | `.../160action_j3_tx015_reportfix_...` | **0.0** | ~0.27 m | 0.071→漂到 0.31 | `HOME_CLOSE_MISALIGNED` |
| **40-ep xyalign** | `evidence/e3_act_random40_xyalign_home_n8_ws02_160action_j3_tx015_20260719/` | **1.0** | ~0.002 m | ~0.079 | **`HOME_NO_CLOSE`（回退）** |

**关键问题（已证实）**：专家 `approach_xy` 在 `ee_xy_tolerance≈0.08` 时过早判定到达，日志里
`Pose reached approach_xy: err_xy≈0.077–0.080`（约 1 s 结束），**并未真正对准物体再降**。
因此这 +10 条对“先对齐再降”贡献不足，与 30-ep descend 简单合并后反而冲淡了降 Z/闭合。

**止损**：**不扩到 50**；**暂以 30-ep descend checkpoint 为 home 行为最佳**。
下一步更高 ROI：收紧 approach_xy 到达门（更小 `ee_xy_tolerance` 或阶段专用阈值）后重采 XY-align，
或对 30/40 做 A/B 后只保留有效子集，而不是再均匀加量。

## 数据侧：tight approach_xy 门 +10 → 40-ep（2026-07-19，续）

| 项 | 内容 |
|---|---|
| 代码 | `batch_generator.approach_xy_tolerance`（默认 **0.025**）；贯通 `_position_reached` / confirm / stream；smoke：`BATCH_PREFLIGHT_APPROACH_XY_TOLERANCE` |
| seed50×5 | `.../e2_red_500hz_seed50_xyalign_tight5_home_20260719`：`use_ready_pose=false`，approach_xy=**8.0** s，xy_tol=**0.025**，hover_h=0.10 |
| seed51×5 | `.../e2_red_500hz_seed51_xyalign_tight5_home_20260719`：approach_xy=**7.5** s，hover_h=0.12 |
| 专家门证据 | 全部 `Approach XY gate PASS: err_xy≈0.003–0.004`（旧 48/49 为 `err_xy≈0.077–0.080` 假到达） |
| release | `data/releases/e2_500hz_random40_xyalign_tight_20260719`（30 descend + 10 tight；**不含**无效 48/49） |
| train | `data/e2_500hz_act_random40_xyalign_tight_conservative_5epoch_20260719` |

Isaac home（同控制信封 j3 / tx0.015 / 160@5Hz）：

| ckpt | 证据 | grip_min | z span | 判定 |
|---|---|---:|---:|---|
| 30-ep descend | `.../reportfix_...` | **0.0** | ~0.27 m | **`HOME_CLOSE_MISALIGNED`（仍最佳）** |
| 40-ep loose xyalign | `.../xyalign_home_...` | 1.0 | ~0.002 m | `HOME_NO_CLOSE` |
| **40-ep tight xyalign** | `evidence/e3_act_random40_xyalign_tight_home_n8_ws02_160action_j3_tx015_20260719/` | ~0.73 | ~0.27 m | **`HOME_DESCEND_NO_CLOSE`**（有降 Z，未充分闭合） |

**结论**：阶段专用门已修好专家演示质量；合并训练后 home **能降 Z**（优于 loose xyalign），但仍 **不如 30-ep 的闭合**。
**止损不变**：不扩到 50；**继续以 30-ep descend 为 home 最佳 checkpoint**。下一 ROI 应转闭合/接触阶段数据或策略，而非再加同类 XY-align 量。

## P3 warmstart A/B → 最终 E3 选型（2026-07-19）

同控制信封对比（详见 [`E2_E3_MODEL_CARD.md`](E2_E3_MODEL_CARD.md)）：

| ckpt | home | warm |
|---|---|---|
| **30-ep descend（选用）** | `HOME_CLOSE_MISALIGNED` | `WARM_NO_CLOSE`（60-step PASS） |
| 40-ep tight | `HOME_DESCEND_NO_CLOSE` | `WARM_CLOSE_CONTACT`（后 velocity E-stop） |

**最终 E3 checkpoint**：`data/e2_500hz_act_random30_descend_conservative_5epoch_20260719/checkpoint.pt`
**sha256**：`948e2949ae8af099f8347837969f596018bbf68a18cc703b6bc09abd01a92501`
**止损**：不扩到 50；home 为主门，warm 成功不替代 home。

本机 checkpoint：`data/e2_rendered_act_1epoch/checkpoint.pt`（约 197 MiB，生成产物，未复制进
Git evidence）。本机最终上游视频示例：
`/home/ina/dev/ros2-arm-teleoperation-suite/data/e2_rendered_scene_episodes/videos/chunk-000/observation.images.scene/episode_000000.mp4`。

## 修复的关键问题

1. 多轮 launch 退出后遗留 camera/recorder/state-publisher/aggregator 进程，导致同一 topic
   出现 5 个发布者、相机输入瞬时 110–130 Hz 和控制超时。修复后运行中为 1 publisher / 1
   subscriber，录制有效频率约 10.001 Hz，退出后零残留。
2. MuJoCo 新版 Renderer 已返回顶行优先数组，camera bridge 的遗留 `flipud` 又翻转一次，导致
   录制视频上下颠倒。移除二次翻转并添加回归测试。
3. 原物体与篮子边缘最近仅约 5 mm，任务运输距离不足。篮子中心改为 `y=±0.35 m`，红盒到
   左篮中心运输约 0.28 m。
4. ACT 0.5.x eval mode 中 `policy.forward()` 仍计算 VAE KL，而 `mu/log_sigma=None`；评估改为
   直接调用 `policy.model()` 并只在非 padding action 上计算 normalized L1。

## 限制声明

- 早期 5 条固定布局和本轮 10 条窄范围随机红块数据都不足以支撑泛化结论。
- 离线 L1/RMSE 和夹爪开闭准确率不是 task success rate。
- 已执行三步接口 smoke 和一次 20-action learned-policy 有界运行；后者 task 明确为 FAIL。
- **E3 nominal20**：权威证据 `evidence/e3_nominal20_home_30ep_gt_v1_20260719/`（20 seeds、
  summary、失败视频；GT v1）。`go_no_go=no_go`，place 成功率 0/20（诚实 `lift_failed`）。
  旧目录 `e3_nominal20_home_30ep_20260719/` 的 `invalid_evaluator_v0` 行不得计入成功率。
- 尚未完成真实机械臂部署或 Sim2Real。
- 本机适合顺序采集当前 10–50 条 320×240 MuJoCo 数据。远程/多机更适合 500+ 条、并行多物体、
  高分辨率或 Isaac 批量采集；这是一条基于本轮负载的工程建议，不是硬件上限证明。
- 项目 RAG 默认排除 `data/` 与 checkpoint；事实查询应读取本页和 `evidence/e2_act_preflight/`
  的小型证据文件，而不是把生成目录当版本化事实。
