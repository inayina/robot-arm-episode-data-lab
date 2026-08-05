# RA 科研助理方向补强 SPEC

**版本**：v0.3  
**状态**：Research design + application docs + RA-WP2 normalized-progress shift analysis complete；technical report pending  
**日期**：2026-07-30  
**Owner**：`robot-arm-episode-data-lab`（研究问题、评测协议、证据与写作）  
**涉及仓库**：`ros2-arm-teleoperation-suite`、`robot-arm-episode-data-lab`、`ros2-moveit-pybullet-bridge`  
**项目边界**：**Not task success / Not Sim2Real / Not real robot**。本文定义求职补强与研究交付，不授权重训、第三次 data-fix、扩 Isaac seed、修改 `eval_gate_v3`、恢复 LingBot、下载新权重或进入真机。

关联材料：

- [FINAL_PROJECT_SUMMARY.md](FINAL_PROJECT_SUMMARY.md)
- [BADCASE_ATTRIBUTION_SUMMARY.md](BADCASE_ATTRIBUTION_SUMMARY.md)
- [FUTURE_WORK_ROADMAP.md](../FUTURE_WORK_ROADMAP.md)
- [SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md](../SMOLVLA_OPENLOOP_PERTURBATION_DESIGN.md)
- [SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md](../SMOLVLA_S4_LIFT0_OFFLINE_ATTRIBUTION.md)
- [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)

---

## 0. 一句话决策

> **把现有“三仓工程”收敛为一个可证伪的机器人学习研究问题：为什么专家状态分布上的 first-action open-loop Pass 没有迁移成自主闭环任务成功，以及怎样用可审计的分层实验量化这种失配。**

目标岗位不是泛化的“纯模型算法 RA”，而是以下交集：

- 机器人学习 / 模仿学习评测；
- Embodied AI Benchmark / data-centric robotics；
- 仿真、数字孪生与 Sim2Sim；
- 机器人系统研究工程；
- 具身策略安全、验证与 failure analysis。

若目标实验室只招聘新模型结构、超大规模预训练或纯理论优化方向，当前项目只能作为系统与实验能力辅助证据，不能替代算法论文。

---

## 1. 当前研究基线

### 1.1 已实现且证据充分

| 研究资产 | 当前事实 | 权威证据 |
|---|---|---|
| 独立 prospective 评测 | 10 episodes / 2,593 帧；与训练集、阈值设计过程零重叠 | `runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/` |
| Offline 结果 | Recovery v3 EE RMSE `0.0253 m`、gripper balanced accuracy `0.9943`；`eval_gate_v3` Pass | 同上 + `configs/smolvla_s3/eval_gate_v3.lock.json` |
| Closed-loop 结果 | 修光后有界 Isaac S4：interface 5/5、reach 1/5、grasp 0/5、lift 0/5、Hold | `evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json` |
| 物理链上界 | scripted oracle 修复物理链后 lift 5/5 | `evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720/oracle_gate.json` |
| 数据泄漏审计 | 历史 v2 训练根实际含 20 episodes，旧 held-out/OOD 表述已降级；Recovery 改为 train-only 36 episodes | `docs/portfolio/resume_description.md` §B.4、`tests/test_smolvla_s3_train_split_materialization.py` |
| 同 seeds 反证 | 近黑首轮 reach 3/5、grasp 1/5 被修光复测证伪为 1/5、0/5；首轮已标记 Superseded | `docs/portfolio/BADCASE_ATTRIBUTION_SUMMARY.md` |
| 扰动诊断 | 已有 240 次阶段锚点 + 840 次 close 窗口 H=1 诊断；不具 Gate 资格 | `runs/smolvla_s3/openloop_perturbation_20260725T045044Z/` |

### 1.2 当前领先推断

现有链条为：

```text
Data 无已知泄漏
  → checkpoint / state / camera / action 合同通过
  → expert-state first-action open-loop Pass
  → policy interface 5/5
  → continuous Task GT lift 0/5
```

物理链、执行链、`state[15]` 编码和相机失明已被逐项检查；当前领先解释为闭环 BC / covariate shift，但现有 MuJoCo 训练域对照只有人工提前停止的 1-seed，**证据不足以确认它是唯一根因**。

### 1.3 当前研究缺口

1. “covariate shift”仍主要是归因结论，缺少随闭环时间累积的量化曲线；
2. 缺少 phase-conditioned 的训练态 / 自主态分布比较；
3. MuJoCo 训练域闭环只有 1-seed，不是完整对照；
4. 现有材料以工程事实表为主，缺少论文结构、相关工作定位和 threat-to-validity；
5. 没有把实验产物压缩成导师可在 3–5 分钟判断研究价值的 research brief。

---

## 2. 研究命题与假设矩阵

### 2.1 主研究问题

**RQ1：** 在 Panda 单方块操作中，专家状态分布上的 first-action 预测精度与自主闭环任务表现为什么出现显著断层？

### 2.2 次研究问题

- **RQ2：** 分布偏移首先在哪个任务阶段出现，如何随自主 rollout 时间累积？
- **RQ3：** 失败更接近 observation shift、动作调度/时延、夹爪决策退化，还是仿真域差？
- **RQ4：** 哪些离线指标对闭环 failure lane 有诊断价值，哪些指标只应停留在 expert-state fit？

### 2.3 可证伪假设

| ID | 假设 | 支持它的观测 | 反驳条件 | 当前状态 |
|---|---|---|---|---|
| H1 | 主要失败来自相机不可见或视觉域差 | 修光前输入近黑 | 修光后同 seeds 仍 Hold；训练域 MuJoCo 也出现不闭爪 | 已显著降级，不作为主因 |
| H2 | 主要失败来自闭环 BC 分布偏移 | offline Pass、closed-loop lift 0/5；MuJoCo seed1 同样退化 | 在线状态与训练状态分布无明显漂移，或漂移与行为失败无时序关联 | 领先假设，待量化 |
| H3 | state/action 合同错配导致策略失效 | 历史 v1/v2 曾存在 state 维度问题 | Recovery checkpoint audit、state 编码与在线遥测一致 | 当前已基本排除 |
| H4 | 执行接口、限幅或安全链吞掉了有效动作 | 闭环任务失败 | interface 5/5、150/150 未限幅、无 E-stop，且 oracle 同链可 lift 5/5 | 当前已基本排除 |
| H5 | 同步推理 deadline miss 导致闭环退化 | sync queue bench 有 deadline miss | async 只改善时序但行为仍不改善；或失败发生在无 miss 区间 | 诊断候选；在线 async 未接线 |

所有结论必须使用“支持 / 降级 / 排除到当前证据范围”措辞，禁止把相关性写成唯一因果证明。

---

## 3. 工作包

| 工作包 | 当前状态 | 本轮证据 |
|---|---|---|
| RA-WP0 | 文档完成 | `research_identity.yaml`、事实与状态冻结 |
| RA-WP1 | 通用矩阵完成 | 14 篇原论文；目标导师定制待申请前完成 |
| RA-WP2 | 完成（降级协议） | 36 train ep / 9,122 frames vs 5 S4 ep / 750 frames；真实 phase 不可用，使用 normalized-progress proxy；H2 方向支持但非因果证明 |
| RA-WP3 | 未授权 | paired MuJoCo 5-seed 不执行 |
| RA-WP4 | 证据整理完成 | canonical/queued/oracle/relight 对照分栏；不新增训练 |
| RA-WP5 | 部分完成 | negative results、threats、reproducibility 与 WP2 Results 完成；technical report 待写 |
| RA-WP6 | 完成 | brief、摘要、三档讲述、邮件、5 页 slides |

### RA-WP0：事实冻结与研究身份卡

**目的**：确保论文、简历和面试使用同一组权威事实。

**任务**：

1. 建立 `research_identity.yaml`，记录问题版本、数据 release、checkpoint、gate lock、rollout evidence 和代码 commit；
2. 把 Historical / Invalidated / Superseded / Current 产物分栏；
3. 固定 `claims_task_success=false`、`claims_sim2real=false`；
4. 为每个表格和图记录生成脚本与 source SHA256。

**验收**：

- 任一核心数字都能追到 JSON/YAML 和生成命令；
- 不使用 v2 被污染 split 作为 held-out/OOD 证据；
- 图表与 JSON 数字一致性测试通过。

### RA-WP1：相关工作与研究空位

**目的**：证明研究问题不是对现有工程日志换标题。

**检索主题**：

- behavior cloning 的 compounding error / covariate shift；
- offline policy evaluation 与 closed-loop evaluation 的边界；
- robot manipulation benchmark 的 task GT 与置信区间；
- simulation-domain comparison 与 paired-seed 实验；
- data leakage、prospective evaluation 和 benchmark governance。

**产物**：

- 1 页 related-work matrix：论文、问题、方法、指标、与本项目差异；
- 1 段明确 novelty claim；若检索后证据不足，必须写“engineering replication / evaluation study”，不得声称新方法。

**验收**：至少覆盖 12 篇直接相关论文，其中近 3 年论文不少于 6 篇；所有引用可访问，且不使用二手博客替代原论文。

### RA-WP2：闭环分布偏移量化（最高优先级）

**授权边界**：默认只读取现有 train release 与 rollout telemetry；不启动 Isaac、不采新数据、不重训。

**输入**：

- Recovery v3 train-only 36 episodes；
- prospective eval-only 10 episodes；
- 权威 relight S4 的 `observations.jsonl` / action / task telemetry；
- 可选：现有 MuJoCo seed1 对照，仅标记 `early_stopped=true`。

**必须实现的分析**：

1. 使用冻结 norm 对 `state[15]` 做同空间比较；
2. 按 hover / approach / descend / pre-close / close / lift 分阶段；
3. 报告 per-dimension Wasserstein-1、标准化均值差和至少一种 multivariate distance（MMD 或 energy distance）；
4. 报告分布距离随 rollout 时间/阶段的累积曲线；
5. 将距离变化与 Z 下降、gripper close、near-static 和最终 `failure_lane` 对齐；
6. 使用 episode-level bootstrap，避免把连续帧当作独立样本；
7. privileged `object_pose` 只允许用于诊断标签，不得混入 policy state。

**建议产物**：

```text
evaluation/closed_loop_shift.py
training/scripts/analyze_closed_loop_shift.py
evaluation/schemas/closed_loop_shift_report.schema.json
tests/test_closed_loop_shift.py
evidence/closed_loop_shift_v1/report.json
docs/portfolio/CLOSED_LOOP_SHIFT_RESULTS.md
```

**报告不变量**：

```yaml
artifact_type: closed_loop_shift_report_v1
diagnostic_only: true
gate_eligible: false
claims_causal_proof: false
claims_task_success: false
claims_sim2real: false
```

**验收**：

- 输入 provenance、样本数、episode 数和 early-stop 状态完整；
- 指标实现有合成数据单测；
- 输出包含效应量与 episode-level uncertainty，不只给 p-value；
- 结果无论支持还是反驳 H2 都保留，不移动 Gate。

### RA-WP3：训练域闭环配对对照（需另批）

**目的**：把 MuJoCo 1-seed 观察升级为与 Isaac 同规模的 paired 5-seed 对照。

**启动闸门**：显式人工批准、GPU/EGL 资源可用、预注册假设与停止条件、完整物理清理方案。

**协议**：

- 同一 checkpoint、state/action 合同、chunk10/K5、控制频率和 seeds；
- MuJoCo 与 Isaac 分别保留原生 task GT，不由中游重推物理成功；
- paired-seed 报告域内输入统计、行为漏斗与 failure lane；
- 不扩到 >5 seeds，不把 5-seed 结果外推为泛化率。

**验收**：5/5 seeds 均有完整 GT 或明确失败原因；任何提前停止必须让该 run 失去完整 gate 资格。

### RA-WP4：最小 baseline 与 ablation

优先复用已有产物，不新增训练：

| 对照 | 回答的问题 | 资格 |
|---|---|---|
| base vs Recovery v3 LoRA | PEFT 是否改善 expert-state first action | canonical offline |
| clean vs nuisance perturbation | 哪一阶段对视觉扰动敏感 | diagnostic only |
| canonical H=1 vs queued K5 | first-action fit 与队列消费差异 | 分栏，queued 无 Gate 资格 |
| oracle vs learned policy | 物理链上界与策略行为差异 | task/system reference |
| Isaac relight vs MuJoCo paired seeds | 域差与闭环 BC 的相对解释力 | 需 RA-WP3 批准 |

禁止重新启用 v1/v2 污染 split 充当 held-out baseline；禁止通过选择性删除失败 seed 改善结果。

### RA-WP5：论文式交付

**主文档目标**：6–8 页 workshop / technical report 格式。

**固定结构**：

1. Abstract：问题、方法、最重要的正/负结果、边界；
2. Introduction：offline→closed-loop gap，而非三仓功能清单；
3. Related Work；
4. System and Evaluation Protocol；
5. Hypotheses and Experiments；
6. Results；
7. Failure Attribution；
8. Threats to Validity；
9. Reproducibility Statement；
10. Conclusion。

**核心图表上限**：主文只放 4 张——研究问题图、实验矩阵、分布偏移曲线、Task funnel；其余进入附录。

**验收**：

- 摘要不出现“成功抓取 / Sim2Real / 真机”；
- 每个结论可映射到假设和证据；
- `0/5`、`5/5` 均带 Wilson CI 或明确小样本限制；
- 有完整 threats-to-validity，不隐藏 early-stop、mock、fixture 或非独立帧问题。

### RA-WP6：申请材料

**交付物**：

- 1 页 Research Brief；
- 150 字项目摘要；
- 30 秒、2 分钟、10 分钟三档讲述；
- 一封面向目标导师的定制邮件模板；
- 5 页以内研究 slide；
- 代码/证据最小公开包链接。

**推荐简历标题**：

> 具身策略离线—闭环失配研究与可审计评测框架

**推荐主句**：

> 在独立 prospective 数据上验证 VLA first-action 精度后，通过 paired-seed、scripted oracle、相机遥测和分层 Task GT 证伪虚高指标，并设计闭环状态分布偏移量化协议；当前结论为 offline Pass / bounded closed-loop Hold。

---

## 4. 研究验收矩阵

| ID | 验收项 | Pass 条件 |
|---|---|---|
| RA-AC-01 | 问题清晰 | 1 个主 RQ、最多 3 个次 RQ；每个都有可反驳条件 |
| RA-AC-02 | 数据独立性 | train / threshold-design / prospective eval 身份与 overlap 报告完整 |
| RA-AC-03 | 统计正确性 | episode-level uncertainty；不把连续帧当独立样本 |
| RA-AC-04 | 因果克制 | 相关性不写成唯一因果；保留 alternative hypotheses |
| RA-AC-05 | 可复现 | 从冻结输入到图表有单命令入口、schema 与测试 |
| RA-AC-06 | 负结果价值 | Hold / No-Go 能导出明确的责任层和下一信息增益实验 |
| RA-AC-07 | 研究写作 | 6–8 页报告 + 1 页 brief + 5 页 slide |
| RA-AC-08 | 诚实边界 | 所有公开材料通过 claims consistency 检查 |

---

## 5. 建议节奏

| 周期 | 目标 | 主要产物 |
|---|---|---|
| Week 1 | RQ、假设、相关工作与 evidence identity 冻结 | Research Brief v0、related-work matrix |
| Week 2 | 用现有 telemetry 完成 RA-WP2 | shift report + tests + 2 张图 |
| Week 3 | baseline/ablation、统计与 threats-to-validity | 实验主表、paper draft |
| Week 4 | 论文式收口与申请材料 | 6–8 页报告、slides、RA 简历版 |

RA-WP3 不纳入默认四周计划；只有显式批准后单独排期。

---

## 6. 停止条件与禁止项

出现以下任一情况时停止升级结论：

- 输入 provenance 或 checkpoint/release 身份不完整；
- 训练/评测 overlap 无法排除；
- 指标对 phase、normalization 或 sample dependence 敏感但未解释；
- 只有单 seed 或 early-stopped run，却试图声称完整域对照；
- 新实验需要 GPU、Isaac、采集或训练但未取得批准。

明确禁止：

1. 把 open-loop Pass 写成闭环能力；
2. 把 oracle 5/5 写成 learned-policy 成功；
3. 把 lift 0/5 写成“模型永远失败”；
4. 把修光前 reach 3/5、grasp 1/5 写成部分成功；
5. 为做论文自动扩 seed、重训、第三次 data-fix 或进入真机；
6. 删除 Historical / Invalidated / Superseded 证据。

---

## 7. Definition of Done

本 SPEC 完成必须同时满足：

- 有一个能被反驳的中心研究主张，而不是功能清单；
- RA-WP2 使用现有证据完成并可复现；
- 至少一个结论因新分析被加强、降级或反驳；
- 论文、brief、slide、简历使用同一事实表；
- 未经批准的 RA-WP3 和任何训练/扩 seed 工作保持未执行；
- 最终材料明确写出 **Not task success / Not Sim2Real / Not real robot**。
