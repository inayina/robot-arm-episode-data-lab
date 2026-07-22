# Panda ACT → Isaac 评测审计报告

状态日期：2026-07-20<br>
范围：`ros2-arm-teleoperation-suite`（上游）、`robot-arm-episode-data-lab`（中游）、
`ros2-moveit-pybullet-bridge`（下游）<br>
当前结论：评测链路已闭环；learned policy 的 E3 nominal 结果为 **0/20，No-Go**；
scripted oracle 的 E3.5 lift 门禁为 **5/5，Pass**。因此问题已经从“Isaac 是否能抓”收敛到
“ACT 的 home→对准→接触闭合策略”。

> 本报告是当前实验结论入口。执行细节见
> [EMBODIED_POLICY_EVALUATION_SOP.md](EMBODIED_POLICY_EVALUATION_SOP.md)，模型身份与 A/B 见
> [E2_E3_MODEL_CARD.md](E2_E3_MODEL_CARD.md)，oracle 完整实验过程见
> [E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md](E3P5_ISAAC_SCRIPTED_ORACLE_EXPERIMENT.md)。

## 1. 审计方法

项目事实按以下优先级核对：运行产物与测试 → 当前代码 → 配置/schema → 当前文档 → README。
三仓知识审计命令：

```bash
python3 -m project_knowledge.cli query --mode auto --no-llm \
  --query "E0 E1 E2 E3 E3.5 当前实现、证据与边界"

python3 -m project_knowledge.cli audit \
  --json-out /tmp/project-audit.json \
  --markdown-out /tmp/project-audit.md
```

2026-07-20 审计覆盖三个仓库，`coverage complete=true`、`errors=0`。初始 217 个 warning
主要是跨仓绝对本地链接的可移植性提示（其中 207 个来自下游面试知识库）以及相邻仓
`AGENTS.md` 未单独注册；它们不是测试失败或运行时故障。当前仓库 README 的主要事实冲突是：
旧首页仍以 MLP/handoff 为主，并声称 ACT online runtime 未完成，而实际 E2/E3/E3.5 已有运行证据。

## 2. 评测漏斗与权威结论

| 阶段 | 问题 | 当前证据 | 结论 |
|---|---|---|---|
| E0 契约 | run、episode、summary 能否追溯？ | JSON Schema、fixture、聚合测试 | 已实现 |
| E1 执行 | action 能否被 Isaac 有界消费？ | 5-repeat action execution、watchdog、安全状态 | 已实现；不等于 learned policy 成功 |
| E2 数据/模型 | 数据是否可训练、模型是否可复现？ | 500 Hz real-rendered MuJoCo release、ACT checkpoint、episode split | 已实现 diagnostic baseline |
| E3 nominal | home_start learned policy 能否完成任务？ | 20 seeds、continuous GT、20 个失败视频 | **0/20，No-Go** |
| E3.5 oracle | 失败是物理链还是策略？ | scripted FSM 5-repeat lift gate | **5/5，物理链 Pass** |
| E2.1 定向迭代 | close→lift 数据能否改善策略？ | 40-episode release + 新 5-epoch checkpoint + 5-seed smoke | **lift 0/5，No-Go** |
| E4 泛化 | object/visual/camera/dynamics shift 如何？ | 仅有规划 | 完整 100+ rollout 未执行 |

这套漏斗刻意分开五类指标：

| 指标层 | 权威来源 | 允许的结论 | 禁止外推 |
|---|---|---|---|
| Offline | inspection、`metrics.json` | schema、split、拟合误差、gripper 分类 | 任务成功率 |
| Interface | policy `report.json` | checkpoint 加载、动作数量、护栏与 E-stop | 抓取/放置成功 |
| Behavior | EE/gripper 曲线、home/warm A/B | 降 Z、XY 对准、闭合时序 | 物理 lift/place |
| Task | continuous simulator GT | reach/grasp/lift/place | 真机成功、Sim2Real |
| System | CPU/GPU、时延、QoS、cleanup | 本轮资源与运行健康 | hard real-time 保证 |

## 3. E3：learned-policy nominal20

权威目录：
[evidence/e3_nominal20_home_30ep_gt_v1_20260719/](../evidence/e3_nominal20_home_30ep_gt_v1_20260719/)

| 项 | 结果 |
|---|---:|
| Seeds | 2000–2019 |
| Completed / infrastructure failure | 20 / 0 |
| Reach | 10/20 |
| Grasp | 0/20 |
| Lift / Place / Overall | 0/20 |
| Overall Wilson 95% CI | `[0.000, 0.161]` |
| Go/No-Go | **No-Go** |

策略可以完成 160 个有界在线动作，且 safety/E-stop 正常，但物体 lift delta 仅约
`2.7e-6–3.7e-6 m`。这证明 interface PASS 与 task PASS 必须分开报告。

### Evaluator v0 隔离

第一轮 nominal 运行发现夹爪 command 被错误当作 measured state，旧结果已隔离到
`evidence/e3_nominal20_home_30ep_20260719/`，并标记 `INVALID_EVALUATOR_V0`，不计成功率。
修复后的 recorder 分离 command/state、接入 FT、完成两个种子一致性预检后，才启动权威
20-seed suite。该过程本身是评测器验证与止损证据。

## 4. E3.5：scripted oracle 二分归因

### v1 失败对照

权威目录：
[evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/](../evidence/e3p5_isaac_scripted_oracle_5x_lift_20260720/)

- scripted FSM 阶段完成 5/5；
- reach/grasp 5/5；
- lift 0/5；
- 暴露 pick 偏高、夹爪瞬移、摩擦和 GT close threshold 问题。

### v2b 通过

权威目录：
[evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/](../evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/)

修复 pick Z offset、PD gripper、方块摩擦、grasp pause 和侧夹阈值后：

| Reach | Grasp | Lift | Gate |
|---:|---:|---:|---|
| 5/5 | 5/5 | **5/5** | `gate_pass=true` |

可确认 Isaac 名义红方块的物理抓取链可用；不能据此声称 ACT 成功或 Sim2Real。

## 5. 当前定向迭代（在线验收未通过）

E3.5 通过后只增加 close→lift 阶段数据，没有继续均匀堆普通下降轨迹。

| 产物 | 当前事实 |
|---|---|
| Release ID | `e2_500hz_random35_closelift_20260720`（名称保留；manifest 实际为 40 episodes） |
| 数据 | 40 episodes / 9,779 frames / 320×240@10 Hz |
| Inspection | PASS；`upstream_gate=batch_generator`；`filter_scope=training_split_only` |
| Training | ACT 5 epochs；CUDA；873.19 s |
| Loss | `1.7390 → 0.3276` |
| Validation L1 | `0.009193` |
| Gripper accuracy | `0.971790` |
| Checkpoint SHA-256 | `bc4a8fc49d24e9c22e8337ae9376fe189344235405d91e1034bcb7fe332785c3` |
| Online task status | 5-seed home smoke：**lift 0/5；不得声称优于 E3 checkpoint** |

Release：
[data/releases/e2_500hz_random35_closelift_20260720/manifest.json](../data/releases/e2_500hz_random35_closelift_20260720/manifest.json)<br>
Metrics：
[data/e2_500hz_act_random35_closelift_5epoch_20260720/metrics.json](../data/e2_500hz_act_random35_closelift_5epoch_20260720/metrics.json)

### 5-seed Isaac smoke

权威结果：
[evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json](../evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json)

| 项 | 结果 |
|---|---:|
| Seeds | 2200–2204 |
| Interface / report | 5/5 PASS |
| Reach / grasp / lift | 0 / 0 / **0** |
| Behavior | 5/5 `HOME_NO_CLOSE` |
| Gripper / Z | `grip_min=1.0`；`z_span≈0.014 m` |
| GT | `failure_stage=reach`；`gripper never closed below 0.120` |
| Gate | `gate_pass_ge1=false` |

定向增加 close→lift 数据没有带来首次真实 lift；策略仍在 home 附近近静止且不闭合。
因此完整 E4 不启动，下一问题仍是 home→对准→闭合的观测/阶段建模，而不是 rollout 数量。

## 6. 三仓职责审计

| 仓库 | 已实现职责 | 不应放入该仓的职责 |
|---|---|---|
| 上游 `ros2-arm-teleoperation-suite` | MuJoCo 采集、batch physical gate、Isaac execution、continuous GT、scripted oracle | release、训练、离线聚合 |
| 中游（本仓） | adapter、inspection、immutable release、ACT training、summary aggregation、model card/SOP | ROS 实时控制、重新推导物理成功 |
| 下游 `ros2-moveit-pybullet-bridge` | handoff loader、PyBullet replay、risk/monitoring | 采集、训练、替代上游 GT |

Legacy `agents/`、`core/` 和 KUKA/PyBullet 图片不属于当前 Panda ACT 主线。

## 7. Go / No-Go 与下一步

| 决策 | 状态 | 原因 |
|---|---|---|
| 将 30-episode ACT 描述为成功抓放模型 | No-Go | E3 task 0/20 |
| 认为 Isaac 物理链无法抓起物体 | 否定 | E3.5 oracle lift 5/5 |
| 继续均匀扩到 50 条 | No-Go | 已有止损证据；需验证定向数据 |
| 新 close→lift checkpoint 继续扩大评测 | No-Go | 5-seed lift 0/5，`HOME_NO_CLOSE` |
| 直接启动完整 E4 100+ | No-Go | nominal 和定向模型均无 learned-policy lift；存在 floor effect |
| 模型无关评测框架（Adapter 契约 / Benchmark 规范 / VLA V0–V0.5 契约） | Go（文档与 schema；LingBot 执行路线 Archived） | 见 `POLICY_ADAPTER_CONTRACT.md`、`THREE_REPO_CANONICAL_FACTS.md`；不自动训、不恢复 LingBot V1、不跑 E4 |
| 继续盲训 ACT / 普通下降扩采 / 盲扫 stage weight | No-Go | `ACT_HOME_NO_CLOSE_HYPOTHESIS_MATRIX.md` |
| LingBot-VLA 2.0 本机 Gate V1（6B） | **No-Go / Closed / Archived** | 本机 ~6GB；见 `VLA_GATE_V1_PREFLIGHT.md`；不得自动恢复 |
| SmolVLA（当前活动预训练候选） | **Active / S3 Ready** | S0–S2 完成；S3 本地冻结；正式 LoRA/Isaac 未执行 |
| SmolVLA Gate S1（官方推理复现） | **Go / pass** | peak ≈925 MiB，~171 ms；见 `SMOLVLA_GATE_S1_OFFICIAL_REPRO.md` |
| SmolVLA Gate S2（Panda open-loop） | **Interface Go；H-3 No-Go** | EE RMSE≈0.27 m，gripper acc 0；见 `SMOLVLA_GATE_S2_OPEN_LOOP.md` |
| SmolVLA Gate S3 Ready（本地准备） | **Go / ready** | release+config+AutoDL 入口；见 `SMOLVLA_GATE_S3_READY.md` |
| 自动进入 SmolVLA 正式 S3 训练 / S4 Isaac | No-Go（本轮） | 须人工批准 + 外部 ≥16GB + preflight Pass；open-loop Pass 后才可议 Isaac |

## 8. 可对外陈述与边界

**可以陈述**：实现了 Panda 多仓数据、ACT 训练、Isaac 有界 rollout、continuous GT、失败视频、
评测器预检、scripted oracle 和数据回流的评测闭环；通过 oracle 将物理问题与策略问题分离；
已冻结模型无关 Policy Adapter 契约与单方块 Benchmark 规范（执行矩阵未跑）；LingBot V0/V0.5
审计已完成并归档执行路线；SmolVLA 为当前活动预训练候选（S2 Hold）。

**必须同时陈述**：当前 learned-policy nominal 为 0/20；新定向 checkpoint 的 5-seed smoke
仍为 lift 0/5；没有真实机械臂部署、completed Sim2Real 或稳定在线自主抓取；LingBot **未**作为
后训练策略推进；SmolVLA **S2 接口 Pass ≠ 已适配 Panda / 任务成功**；base zero-shot open-loop
No-Go；**尚未 LoRA、尚未 Isaac VLA**。
