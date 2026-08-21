# 作品集对外入口

**Current as of 2026-08-21**：**Panda Manipulation Runtime, Data & Validation
System**。这是一个由三个仓组成的仿真范围项目：上游执行/采集，中游数据/训练/评测，
下游 replay/risk/diagnostic witness。

**当前结论**：Route A 的 learned policy 为 Reach `1/4`、Grasp `0/4`、Lift `0/4`；
Route B 是 Isaac–ROS prerequisite failure，不能作为策略任务失败。Not task success ·
Not Sim2Real · Not real robot。

唯一 current authority 是 [THREE_REPO_CANONICAL_FACTS.md](THREE_REPO_CANONICAL_FACTS.md)。
[BOUNDARY_FREEZE.md](BOUNDARY_FREEZE.md) 仅为 Historical 2026-07-27 快照。

---

## 对外主导航

| # | 材料 | 回答什么问题 |
| --- | --- | --- |
| 1 | **[CURRENT_CASE_STUDIES.md](CURRENT_CASE_STUDIES.md)** | 两个当前技术深挖：Recovery intervention 与 cross-backend bridge isolation |
| 2 | **[PORTFOLIO_REFERENCE.md](PORTFOLIO_REFERENCE.md)** | 作品集母版：招聘经理 5 分钟看价值、技术面试官 30 分钟深挖 |
| 3 | **[portfolio_system_overview.svg](portfolio_system_overview.svg)** | 三仓如何组成一个系统 |
| 4 | **[BADCASE_ATTRIBUTION_SUMMARY.md](BADCASE_ATTRIBUTION_SUMMARY.md)** | 历史故障归因与证据边界 |
| 5 | **[EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)** | 每份 JSON 从哪来、能证明什么 |
| 6 | **[resume_description.md](resume_description.md)** | 简历条与 30 秒/2 分钟话术 |

历史最小公开证据包仍见 [public_evidence/canonical_v3/](public_evidence/canonical_v3/README.md)，不得把它当作 2026-08-21 current result。

---

## 内部审计（不进主导航）

事实底稿、岗位对齐长文、单路线一页纸、自动进度快照等仍保留在 `docs/portfolio/` 与 `docs/`，供审计与进一步深挖：

- [FINAL_PROJECT_SUMMARY.md](FINAL_PROJECT_SUMMARY.md) · [THREE_REPO_CANONICAL_FACTS.md](THREE_REPO_CANONICAL_FACTS.md)
- [UNIFIED_EVAL_REPORT.md](UNIFIED_EVAL_REPORT.md) · [SMOLVLA_RECOVERY_V3_PORTFOLIO.md](SMOLVLA_RECOVERY_V3_PORTFOLIO.md)
- [RA_RESEARCH_ASSISTANT_STRENGTHENING_SPEC.md](RA_RESEARCH_ASSISTANT_STRENGTHENING_SPEC.md) · [PRODUCT_SOLUTION_ARCHITECT_STRENGTHENING_SPEC.md](PRODUCT_SOLUTION_ARCHITECT_STRENGTHENING_SPEC.md)
- [tracks/README.md](tracks/README.md) — 技术面试 / 产品解决方案架构 / RA 科研助理三套独立文档包
- [../README.md](../README.md)「内部审计」表

**提交冻结**：新 Gate / runtime lane / risk 维度 / dashboard 页面 — 见 [BOUNDARY_FREEZE.md §7](BOUNDARY_FREEZE.md#7-功能提交冻结)。
