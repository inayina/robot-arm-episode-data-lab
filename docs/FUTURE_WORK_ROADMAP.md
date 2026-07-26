# Future Work Roadmap（P0 / P1 / P2）

**冻结日期**：2026-07-25 · **基线 commit**：`d7ba9d53e9df94c0c4565ba31114cf9b1511a878`  
**本文性质**：**登记表，不是执行计划**。P0 已完成；P1-0A / P1-0B / P1-1 是已获批准并完成的诊断例外，**其余 P1 / P2 只登记，不执行**。
**诚实边界**：**Not task success / Not Sim2Real / Not real robot**。

## 0. 执行闸门（硬约束）

以下任何一项都**需要显式人工批准**，Agent 不得自动推进：

| 动作 | 现状 | 需要什么 |
|---|---|---|
| 正式训练 / 重训 / 第三次 data-fix | `max_data_fix_retries: 1` **已用尽** | 显式人工批准 + 外部 ≥16GB GPU |
| 扩大 Isaac seed（>5） | 有界 S4 已跑，lift 0/5 → **默认禁止扩种子** | 显式人工批准 + 明确假设与止损条件 |
| 新增数据采集 | 已完成 v3 scene-only 训练集与 seeds 70–74 eval-only | 显式人工批准（含 attempts / 位置定义） |
| 修改 Gate 阈值 | `eval_gate_v3` 已 SHA256 冻结（`37325a1f…`） | 显式人工批准；**禁止追溯改判历史 Hold** |
| 恢复 LingBot Gate V1 / 下载 6B 权重 | **Closed / Archived** | 显式人工批准 + ≥24GB 资源 + 明确多本体需求 |
| 真机 / Sim2Real | 从未开始 | 不在当前项目范围内 |
| ACT 继续训练 | **Frozen diagnostic baseline** | 不做（已判定 floor effect） |

---

## 1. P0 — 事实冻结与作品集收口（**已完成**）

| # | 事项 | 状态 | 产物 |
|---|---|---|---|
| P0-1 | 冻结 SmolVLA Recovery v3 canonical open-loop **Pass** 口径（`canonical_first_action` / 每观测独立 reset / `stride=1` / 全帧 / prospective 零重叠） | 完成 | `runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/`、`configs/smolvla_s3/eval_gate_v3.lock.json` |
| P0-2 | 冻结有界 Isaac S4 **Hold**（chunk10 / K5 / 10 Hz；seeds 1–5；interface 5/5；lift 0/5） | 完成 | `evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json` |
| P0-3 | 明确**修光后 relight run 为权威 S4**，首轮近黑场景标注 `Superseded / historical` | 完成 | `docs/SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md` §6、`configs/smolvla_s3/recovery_decisions.yaml: bounded_s4_executed` |
| P0-4 | `queued_diagnostic` 与 canonical first-action 严格分离（前者永不具备 Gate Pass 资格） | 完成 | `recovery_decisions.yaml: local_inference_contract`、`docs/SMOLVLA_V3_EVAL_SOP.md` §3 |
| P0-5 | ACT 冻结为 diagnostic baseline；Scripted oracle 定位为系统上界参考；LingBot Closed/Archived | 完成 | `docs/portfolio/THREE_REPO_CANONICAL_FACTS.md` VLA 路线表 |
| P0-6 | 最终项目总结 + 分层 Badcase 归因 + 三套求职材料 | 完成 | `docs/portfolio/FINAL_PROJECT_SUMMARY.md`、`docs/portfolio/BADCASE_ATTRIBUTION_SUMMARY.md`、`docs/portfolio/resume_description.md` |
| P0-7 | 图表与原始 JSON 一致（funnel / per-seed 从权威 gate 读数，不硬编码） | 完成 | `scripts/generate_smolvla_v3_portfolio_figures.py`、7 张 `docs/portfolio/smolvla_*.png` |
| P0-8 | 统一评测信封重出到权威 gate；旧信封保留为历史 | 完成 | `evidence/smolvla_v3_eval_framework_relight_20260725/`、`evidence/smolvla_v3_eval_framework_20260724/`（historical） |
| P0-9 | 文档事实一致性回归测试（honest claims / 图表来源 / 链接 / 数字比对） | 完成 | `tests/test_portfolio_docs_consistency.py`、`tests/test_unified_eval_report.py`、`tests/test_smolvla_s3_recovery_decisions.py` |

---

## 2. P1 — 已登记，**不执行**（评测框架深化，无需新训练）

这些都是「不需要重训、不需要扩种子」就能提高评测框架说服力的工作。**当前不执行**，需要人工批准才启动。

### 2.0 评测语义冻结（所有 P1 共用，先于实现）

| 部分 | 每次预测 | 评测范围 | 用途 | 改动策略 |
|---|---|---|---|---|
| **Clean canonical** | first action，**H=1** | 10 条完整 episode、**全帧**、`stride=1`、**每帧 reset** | **唯一 Gate** | **保持不变**；禁止为省算力改成只跑 5/10 步 |
| **Queue 诊断** | K5（chunk=10 / consume=5） | 现有 `queued_diagnostic`；reset = episode boundary | 诊断 only | **继续保留**；永不替代 canonical、不单独说明闭环任务能力 |
| **扰动快速诊断** | first action，H=1 | 每 ep **6 阶段锚点** × 10 ep = 60；× clean/轻/中/重 = **240** | 阶段敏感性诊断 | **P1-0A 已执行** |
| **Close 扰动诊断** | first action，H=1 | 每 ep 21 帧 × 10 × 4 条件 = **840** | 闭爪时序 / debounce / 漏 close | **P1-0B 已执行** |
| **自主能力** | K5 closed-loop | 已有 S4 有界 5-seed（权威 relight） | 任务 funnel | **不再扩展 seed** |

**禁止**：新增 H=5 / H=10 open-loop 未来动作误差指标（模型未来状态假设 ≠ 专家未来状态假设，误差不可解释）。  
完整协议见 **[SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md](SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md)**。

| # | 事项 | 为什么值得做 | 需要的前置 | 预期产物 | 明确不做 |
|---|---|---|---|---|---|
| P1-0A | **Open-loop 扰动快速诊断（阶段锚点）** | 在不重跑全帧的前提下量化阶段敏感性；仍保持 first-action / 每观测 reset | ✅ **2026-07-25 已执行**（人工批准「开跑扰动实验」） | `runs/smolvla_s3/openloop_perturbation_20260725T045044Z/`（240 锚点推理）；摘要 `docs/portfolio/OPENLOOP_PERTURBATION_RESULTS.md` | 不改 clean 全帧协议；不对 2593 帧默认全扫；不改 Gate；不宣称任务成功 |
| P1-0B | **Close 窗口扰动诊断（21 帧/ep × 4 条件）** | close timing / 3-frame debounce / 漏 close 不能只靠单锚点 | ✅ **同跑次已执行**（840 推理；全 nuisance 条件可比） | 同上；`close_timing` 分条件；无漏 close，扰动加重提前闭爪 | 不用窗口数字替代全帧 Gate；不做 H=5/H=10 |
| P1-0C | **Recovery probe（可选，锚点子集）** | 在少量 pre-grasp / descend 态加局部扰动，看第一动作是否朝恢复方向 | 人工批准 + scripted oracle corrective target | 方向性 / 误差减小 / 错误闭爪 / 近静止指标 | **不得**声称 autonomous recovery success |
| P1-1 | **异步 action-chunk queue runtime 实测** | sync 重规划是否撑住 10 Hz；async 能否把 ~160 ms 推理藏进 K=5 / 0.5 s | ✅ **2026-07-26 已执行**（offline GPU bench；非 Isaac 扩种子） | `runs/smolvla_s3/queue_runtime_bench_20260726T040945Z/`；摘要 `docs/portfolio/QUEUE_RUNTIME_BENCH_RESULTS.md`；sync deadline miss 20% → async 0.67%（仅冷启动） | 不改 Gate；不宣称任务成功；**未**接线上游在线节点（`async_double_buffer_online_wired=false`） |
| P1-2 | **闭环 BC 分布偏移量化**（DAgger-free 诊断） | 把「H2 倾向」升级为可量化证据：统计在线 state 与训练 state 分布距离随时间的累积 | 只用现有 telemetry `observations.jsonl` | 分布距离 vs 时间曲线 + 与 z/grip 退化的相关性 | 不做 DAgger 采集；不重训 |
| P1-3 | **完成 MuJoCo 训练域 5-seed 对照** | 现有 H2 对照仅 seed1 完整 GT、`early_stopped=true`，不足以称完整 gate | 人工批准 + 解决 EGL/GPU 争用（每 chunk 7–13 s） | 完整 `s4_gate.json`（训练域）与 Isaac 的成对对照 | 不扩到 >5 seeds；不因此扩 Isaac |
| P1-4 | **统一 Policy Runtime + 四泳道 HOC 落地** | ✅ M0–M6 implementation complete：M6 mock-policy 真实 ROS/DDS wiring 已验证 QoS、R2 Hold、R3 E-stop、HOC trace 与清理；默认 SmolVLA executor 仍 legacy | 若未来切真实 SmolVLA authoritative，必须重新人工批准并单独验收；继续消费 M0/M5 SHA lock | [POLICY_RUNTIME_INTEGRATION_SPEC.md](POLICY_RUNTIME_INTEGRATION_SPEC.md) + [POLICY_RUNTIME_HOC_IMPLEMENTATION_ROADMAP.md](POLICY_RUNTIME_HOC_IMPLEMENTATION_ROADMAP.md) + [M6 Results](portfolio/POLICY_RUNTIME_M6_WIRING_RESULTS.md) | 不把 mock `EXECUTED` 写成策略执行或任务成功；不声称已完成 Isaac/真机切流 |
| P1-5 | **Single-block generalization Benchmark 最小执行** | spec 与 fixture 已冻结，矩阵从未跑过 | 人工批准 + 有界 rollout 额度 | Baseline / ID / OOD-position 的最小对照 | 不跑完整 E4（100+ rollouts） |
| P1-6 | **behavior 标签自动化** | `HOME_NO_CLOSE` 等标签目前靠人工/半自动判定 | 无（纯离线） | 标签规则 + 单测 + 对历史 evidence 的回溯标注 | 不改历史 gate 判定 |
| P1-7 | **`assets/diagrams/three_repo_*` 重生成** | EVIDENCE_INDEX 标注为 `regenerate`，缺可追溯生成脚本 | 无 | canonical 生成脚本 + 重出图 | 不删旧图 |

---

## 3. P2 — 已登记，**不执行**（需要新资源 / 新实验授权）

| # | 事项 | 触发条件（缺一不可） | 明确不做 |
|---|---|---|---|
| P2-1 | 针对闭环失败的策略侧改进（如 action chunking 调度、闭环感知的数据配比、DAgger 式修正数据） | 人工批准 + 外部 ≥16GB GPU + P1-2 给出量化偏移证据 + 预先写明 Pass/Hold 判据 | 不做超参盲扫；不做架构改动 |
| P2-2 | 扩大 Isaac seed 到统计可比规模（≥20 seeds + Wilson CI） | 人工批准 + 至少一次真实 lift > 0 的有界证据 | 不在 lift 0/5 状态下扩种子 |
| P2-3 | 完整 E4 泛化矩阵（object / visual / camera / dynamics 四类 shift，100+ bounded rollouts） | 人工批准 + 打破 zero-lift floor effect | 当前 blocked by zero-lift gate |
| P2-4 | 多本体 / 更大 VLA（含 LingBot 路线复审） | 人工批准 + ≥24GB 资源 + 明确多本体需求 | 不得自动恢复 Gate V1；不下载 6B 权重 |
| P2-5 | 真机 / Sim2Real | 超出当前项目范围；需要硬件、安全评审与独立立项 | 当前不得声称任何真机或 Sim2Real 进展 |
| P2-6 | 下游 sensor fusion / risk engine 从 `implemented_not_fully_verified` 升级为已验证 | 人工批准 + canonical Panda handoff 运行证据 | risk R-level 永不作为任务 go/no-go |

---

## 4. 止损与升级矩阵（复用 v3 SOP）

| 情形 | 默认动作 | 需要升级给人工决定的问题 |
|---|---|---|
| open-loop Hold | 停止；产物归档为 Hold 证据 | 是否批准新一轮 data-fix / 重训（额度已用尽） |
| Isaac lift 0/N | Hold；不扩种子、不重训 | 走行为归因还是冻结该候选 |
| 图与 JSON 不一致 | 以 JSON 为准重出图 | — |
| 信封 schema 校验失败 | 修 normalizer/schema | — |
| 采集不足 | 停止，不换 seed 续采 | 是否放宽 attempts / 改位置定义 |

## 5. 关联

- [SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md](SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md) — clean / K5 / 扰动两层 / 禁止 H=5·H=10
- [portfolio/FINAL_PROJECT_SUMMARY.md](portfolio/FINAL_PROJECT_SUMMARY.md)
- [portfolio/BADCASE_ATTRIBUTION_SUMMARY.md](portfolio/BADCASE_ATTRIBUTION_SUMMARY.md)
- [SMOLVLA_V3_EVAL_SOP.md](SMOLVLA_V3_EVAL_SOP.md) §3 canonical、§8 止损与升级矩阵
- [SMOLVLA_S3_ISAAC_S4_RUN_CHECKLIST.md](SMOLVLA_S3_ISAAC_S4_RUN_CHECKLIST.md) §5 明确不做
- [portfolio/THREE_REPO_CANONICAL_FACTS.md](portfolio/THREE_REPO_CANONICAL_FACTS.md)
