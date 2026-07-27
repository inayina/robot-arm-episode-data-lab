# 作品集对外入口（压缩导航）

**冻结日期**：2026-07-27 · 完整边界见 **[BOUNDARY_FREEZE.md](BOUNDARY_FREEZE.md)**

**对外主语**：**Panda 策略软硬件链路诊断与分层验证系统**（数据合同是底座；Policy Runtime / Risk / HOC 提供跨层排查证据，非并列产品线）。

**诚实边界**：Not task success · Not Sim2Real · Not real robot。

---

## 对外仅保留以下八份

| # | 材料 | 回答什么问题 |
| --- | --- | --- |
| 1 | **[PORTFOLIO_REFERENCE.md](PORTFOLIO_REFERENCE.md)** | 作品集母版：以软硬件链条排查能力为主线，招聘经理 5 分钟看价值、技术面试官 30 分钟深挖 |
| 2 | **[portfolio_fault_localization_chain.svg](portfolio_fault_localization_chain.svg)** | 感知、ROS 2、数据/模型、动作、控制/物理、Task GT 六层故障定位链 |
| 3 | **[portfolio_system_overview.svg](portfolio_system_overview.svg)** | 三仓如何组成可排查的机器人系统 |
| 4 | **[portfolio_control_safety_stack.svg](portfolio_control_safety_stack.svg)** | 策略、控制器、硬件接口、总线、驱动、看门狗与 Task GT 的落地链 |
| 5 | **[portfolio_realtime_priority_gantt.svg](portfolio_realtime_priority_gantt.svg)** | 真机 FIFO / 仿真防反转、多速率与四层非确定性治理 |
| 6 | **[BADCASE_ATTRIBUTION_SUMMARY.md](BADCASE_ATTRIBUTION_SUMMARY.md)** | 一次异常如何沿软硬件链逐层排除 |
| 7 | **[EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)** | 每张图/每份 JSON 从哪来、能证明什么 |
| 8 | **[resume_description.md](resume_description.md)** | 三套简历条 + 30 秒/2 分钟话术 |

**最小公开证据包**（gate JSON、SHA、per-seed、unified report、复现命令）：直接查看 [public_evidence/canonical_v3/](public_evidence/canonical_v3/README.md)；范围规则见 [BOUNDARY_FREEZE.md §4](BOUNDARY_FREEZE.md#4-可公开复核的最小证据包)。

---

## 内部审计（不进主导航）

事实底稿、岗位对齐长文、单路线一页纸、自动进度快照等仍保留在 `docs/portfolio/` 与 `docs/`，供审计与进一步深挖：

- [FINAL_PROJECT_SUMMARY.md](FINAL_PROJECT_SUMMARY.md) · [THREE_REPO_CANONICAL_FACTS.md](THREE_REPO_CANONICAL_FACTS.md)
- [UNIFIED_EVAL_REPORT.md](UNIFIED_EVAL_REPORT.md) · [SMOLVLA_RECOVERY_V3_PORTFOLIO.md](SMOLVLA_RECOVERY_V3_PORTFOLIO.md)
- [../README.md](../README.md)「内部审计」表

**提交冻结**：新 Gate / runtime lane / risk 维度 / dashboard 页面 — 见 [BOUNDARY_FREEZE.md §7](BOUNDARY_FREEZE.md#7-功能提交冻结)。
