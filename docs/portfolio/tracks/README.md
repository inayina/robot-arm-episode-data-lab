# 求职材料三轨导航

**状态**：Current  
**日期**：2026-07-30  
**用途**：把同一项目的材料按“技术面试 / 产品解决方案架构 / RA 科研助理”拆成三个独立使用包。  
**诚实边界**：**Not task success / Not Sim2Real / Not real robot**。

---

## 1. 三个独立入口

| 轨道 | 独立入口 | 回答的核心问题 |
|---|---|---|
| 技术面试 | [technical_interview/README.md](technical_interview/README.md) | 我是否真正理解并能独立解释、排查和修改这套机器人系统？ |
| 产品解决方案架构 | [solution_architect/README.md](solution_architect/README.md) | 我如何把技术能力转化为客户可理解、可验收、可移交的方案？ |
| RA 科研助理 | [research_assistant/README.md](research_assistant/README.md) | 我能否提出可证伪问题、设计实验、分析证据并形成科研交付？ |

三条轨道不能用同一套开场白：

- 技术面试从**系统链路、设计取舍和故障定位**开始；
- 解决方案架构从**客户问题、风险、参考架构和验收**开始；
- RA 从**研究问题、假设、实验和证据限制**开始。

---

## 2. 共享事实层

以下文件是三条轨道共同引用的 canonical facts，轨道文档不得复制并独立维护其中的实验数字：

| 事实源 | 用途 |
|---|---|
| [../BOUNDARY_FREEZE.md](../BOUNDARY_FREEZE.md) | 对外定位、模块所有权、release 术语和功能冻结 |
| [../FINAL_PROJECT_SUMMARY.md](../FINAL_PROJECT_SUMMARY.md) | 完整 Pass/Hold、实验数字和证据边界 |
| [../THREE_REPO_CANONICAL_FACTS.md](../THREE_REPO_CANONICAL_FACTS.md) | 三仓事实状态与实现锚点 |
| [../BADCASE_ATTRIBUTION_SUMMARY.md](../BADCASE_ATTRIBUTION_SUMMARY.md) | 权威失败归因案例 |
| [../EVIDENCE_INDEX.md](../EVIDENCE_INDEX.md) | 机器可读证据与生成入口 |
| [../public_evidence/canonical_v3/README.md](../public_evidence/canonical_v3/README.md) | 最小公开证据包 |

若轨道文档与事实层冲突，以测试/代码/运行产物和上述 canonical facts 为准；轨道文档只负责选材，不创造新事实。

---

## 3. 内容所有权

| 内容 | 唯一维护位置 | 其它轨道如何使用 |
|---|---|---|
| 项目真实状态与数字 | `FINAL_PROJECT_SUMMARY.md` | 链接引用，不复制改写 |
| 控制、DDS、总线、安全 FAQ | 下游 `docs/portfolio/INTERVIEW_PREP.md` | 技术面试轨道按 current 章节选读 |
| 客户场景、PoC、验收、移交 | 解决方案架构 SPEC | 其它轨道不扩写商业结论 |
| RQ、假设、实验协议、统计 | RA SPEC | 其它轨道不把研究计划写成已完成 |
| 简历短句与 STAR 案例 | `resume_description.md` | 按轨道选择，不跨版本拼接 |

---

## 4. 更新规则

1. 新实验数字只进入 canonical facts / evidence，不直接写入三个轨道 README；
2. 新技术 FAQ进入下游面试知识库，技术面试轨道只更新索引；
3. 客户 PoC、验收模板只进入 solution architect 轨道；
4. 文献、假设和实验计划只进入 research assistant 轨道；
5. 三条轨道都必须保留 Current / Historical / Superseded / Hardware Pending 标签；
6. 不因求职包装修改 `eval_gate_v3`、历史 JSON 或任务成功定义。

---

## 5. 当前完成度

| 轨道 | 已整理 | 下一交付 |
|---|---|---|
| 技术面试 | current 事实入口、专题矩阵、问答使用规则、自检清单 | 按目标 JD 选 20 个必答题并录制 mock interview |
| 产品解决方案架构 | 完整补强 SPEC、客户旅程、FR/NFR、PoC 与验收框架 | Solution Brief、onboarding fixtures、8 分钟 PoC |
| RA 科研助理 | 完整补强 SPEC、RQ/假设、实验与论文交付框架 | related-work matrix、闭环分布偏移量化 |
