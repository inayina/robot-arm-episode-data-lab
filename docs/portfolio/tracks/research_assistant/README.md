# RA 科研助理文档包

**目标**：把工程证据收敛为可证伪的机器人学习问题、预注册实验、统计分析和论文式交付。  
**适用岗位**：机器人学习、模仿学习评测、Embodied AI Benchmark、data-centric robotics、仿真/数字孪生研究工程。  
**不负责**：客户售前叙事、控制/总线百科题库。  
**诚实边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[三轨总导航](../README.md)

---

## 1. 本轨道唯一主线

> **为什么专家状态分布上的 first-action open-loop Pass 没有迁移成自主闭环任务成功，以及怎样用分层、可复现的实验量化这种失配？**

RA 材料从 RQ、假设和证据缺口开始，不从“三仓做了很多模块”或“客户上线风险”开始。

---

## 2. 核心文档

| 顺序 | 材料 | 用途 |
|---|---|---|
| 1 | [RESEARCH_BRIEF.md](RESEARCH_BRIEF.md) | 1 页 RQ、方法、结果、贡献和限制 |
| 2 | [HYPOTHESIS_EVIDENCE_MATRIX.md](HYPOTHESIS_EVIDENCE_MATRIX.md) | H1–H6 的支持、反证、状态与可证伪条件 |
| 3 | [EXPERIMENT_PREREGISTRATION.md](EXPERIMENT_PREREGISTRATION.md) | closed-loop shift 的输入、指标和停止规则；已按 Amendment A 的 normalized-progress proxy 执行 |
| 4 | [CLOSED_LOOP_SHIFT_RESULTS.md](CLOSED_LOOP_SHIFT_RESULTS.md) | 36 train ep vs 5 S4 ep 的 W1/energy/bootstrap 实际结果 |
| 5 | [../../../../evidence/closed_loop_phase_shift_v2/README.md](../../../../evidence/closed_loop_phase_shift_v2/README.md) | true phase/failure-onset telemetry contract 已补齐；旧证据 readiness fail-closed |
| 6 | [RELATED_WORK_MATRIX.md](RELATED_WORK_MATRIX.md) | 14 篇原论文与 evaluation-study 研究空位 |
| 7 | [NEGATIVE_RESULTS_AND_THREATS.md](NEGATIVE_RESULTS_AND_THREATS.md) | Hold/Invalid/Superseded、统计边界与 validity threats |
| 8 | [REPRODUCIBILITY_GUIDE.md](REPRODUCIBILITY_GUIDE.md) | R0–R5 复现等级、身份、命令和数字来源 |
| 9 | [RA_APPLICATION_BRIEF.md](RA_APPLICATION_BRIEF.md) | 150 字摘要、简历条、三档讲述、导师邮件和追问 |
| 10 | [RA_RESEARCH_SLIDES.md](RA_RESEARCH_SLIDES.md) | 5 页研究申请 slides |
| 11 | [research_identity.yaml](research_identity.yaml) | checkpoint/release/gate/evidence 与 claims 身份卡 |
| 12 | [../../RA_RESEARCH_ASSISTANT_STRENGTHENING_SPEC.md](../../RA_RESEARCH_ASSISTANT_STRENGTHENING_SPEC.md) | 本轨道主 SPEC 与剩余研究路线 |

---

## 3. 文档包结构

### 3.1 已有

- 研究补强 SPEC；
- prospective open-loop 与 bounded closed-loop 证据；
- scripted oracle 系统上界；
- same-seed relight 反证；
- perturbation 与 queue latency 诊断；
- 数据泄漏审计和 immutable evidence。

### 3.2 本轮已交付

| 文档 | 当前状态 |
|---|---|---|
| Research Brief + identity | 完成 |
| H1–H6 hypothesis/evidence matrix | 完成 |
| Related-work matrix（14 篇原论文） | 完成；投稿前仍需按目标导师定制 |
| Experiment preregistration + Amendment A | 完成并执行 |
| Closed-loop shift report | 完成；global/progress-proxy directional support，phase/causal unavailable |
| Phase/failure-onset telemetry contract | 完成；旧证据 readiness fail-closed，新采集后可运行 true phase-conditioned analysis |
| Negative results + threats | 完成 |
| Reproducibility guide | 完成 |
| Application brief + 5-page slides | 完成 |

### 3.3 尚未完成

- 6–8 页 `TECHNICAL_REPORT.md` 正式稿；
- 针对具体导师近 3 年工作的定制 related-work/邮件；
- paired MuJoCo 5-seed：需显式运行授权，不在本轮范围。

准确口径是“**RA 研究设计、申请材料、normalized-progress closed-loop shift analysis、true phase/failure-onset telemetry contract 和 fail-closed readiness audit 已完成；真实 phase-conditioned 结果需要新采集写出 v1/v2 telemetry 后才能生成**”。

---

## 4. 研究叙事顺序

```text
Offline–closed-loop gap
  → frozen data and protocol
  → falsifiable hypotheses
  → paired / phase-conditioned analysis
  → supporting and contradicting evidence
  → threats to validity
  → next minimum-information experiment
```

论文主文不以三仓模块清单组织章节；三仓只作为实验系统和事实所有权说明。

---

## 5. 核心研究案例

| 案例 | 科研能力信号 | 对应问题 |
|---|---|---|
| prospective eval-only 重采 | 防止 threshold-design contamination | 数据独立性与 benchmark governance |
| open-loop Pass / S4 Hold | 指标回答不同问题 | offline-to-closed-loop gap |
| oracle 5/5 | 建立系统上界与控制组 | 排除物理链 |
| relight same seeds | 控制变量并证伪虚高结果 | 视觉可见性与域差 |
| MuJoCo seed1 early-stop | 主动报告不足证据 | threat to validity |

RA 讲述重点是“哪个证据改变了哪个假设”，不是“我修了多少模块”。

---

## 6. 不进入本轨道主材料的内容

- 客户 persona、ROI、售前 discovery 和商业 deck；
- 大量 ROS 2/CANopen 原理题，除非它们直接影响实验 validity；
- Legacy KUKA/RRT 作为 Panda 研究事实；
- 被污染的 v2 split 作为 held-out/OOD；
- 把相关性写成唯一因果；
- 把 0/5、5/5 小样本外推为总体成功率；
- 未经批准自动重训、扩 seed、进入 Isaac 或真机。

系统实现追问统一跳转到 [技术面试包](../technical_interview/README.md)，应用转化追问跳转到 [解决方案架构包](../solution_architect/README.md)。

---

## 7. RA readiness

| ID | 自检项 | Pass 标准 |
|---|---|---|
| RA-T-01 | Research question | 一个主 RQ、最多三个次 RQ，均可被反驳 |
| RA-T-02 | Literature | 能说明与最近相关工作的差异，不把工程复现冒充新方法 |
| RA-T-03 | Experimental design | control、paired seeds、变量、指标、stop rules 清楚 |
| RA-T-04 | Statistics | episode-level uncertainty，不把连续帧当独立样本 |
| RA-T-05 | Negative results | 能解释 Hold/No-Go 提供了什么信息增益 |
| RA-T-06 | Reproducibility | release/checkpoint/gate/code identity 和生成命令完整 |
| RA-T-07 | Scientific writing | 有 threats-to-validity 和 alternative hypotheses |
| RA-T-08 | Oral defense | 5 分钟讲清问题，10 分钟经得住方法和边界追问 |

---

## 8. 本轨道交付清单

- [x] 1 页 Research Brief + research identity；
- [x] related-work matrix；
- [x] hypothesis matrix + preregistration；
- [x] negative results / threats / reproducibility；
- [x] 5 页 research slides；
- [x] RA 专用简历摘要和导师邮件；
- [x] closed-loop shift analysis + schema + tests + report；
- [x] phase/failure-onset telemetry contract + true phase analyzer + readiness audit；
- [ ] 6–8 页 technical report；
- [ ] 研究代码/证据最小公开包更新。
