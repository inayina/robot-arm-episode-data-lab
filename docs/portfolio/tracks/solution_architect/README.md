# 产品解决方案架构文档包

**目标**：把项目整理成客户可理解、可 PoC、可验收、可移交的机器人策略上线前验证方案。  
**适用岗位**：产品解决方案架构、技术售前、PoC 架构、机器人/工业 AI 交付架构、forward-deployed engineering。  
**不负责**：科研 novelty、控制原理题库。  
**诚实边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[三轨总导航](../README.md)

---

## 1. 本轨道唯一主线

> **客户带来一个机器人策略后，本方案在进入昂贵仿真或硬件前检查数据、合同和模型身份，再通过离线、接口、行为、任务和系统六层验收定位风险，最终交付可追溯的 Hold / No-Go / readiness 报告。**

解决方案架构表达必须从客户问题和 measurable outcome 开始，不从 SmolVLA 指标、ROS topic 或三仓代码目录开始。

---

## 2. 核心文档

| 顺序 | 材料 | 用途 |
|---|---|---|
| 1 | [SOLUTION_BRIEF.md](SOLUTION_BRIEF.md) | 一页客户问题、方案价值、范围与适用条件 |
| 2 | [CUSTOMER_DISCOVERY_QUESTIONNAIRE.md](CUSTOMER_DISCOVERY_QUESTIONNAIRE.md) | use case、风险、预算、停止条件与 RACI |
| 3 | [REFERENCE_ARCHITECTURE.md](REFERENCE_ARCHITECTURE.md) | 客户旅程、三仓架构、部署画像与信任边界 |
| 4 | [POLICY_ONBOARDING_GUIDE.md](POLICY_ONBOARDING_GUIDE.md) | 新策略 identity/schema/runtime/adapter 预检合同 |
| 5 | [CUSTOMER_ACCEPTANCE_MATRIX.md](CUSTOMER_ACCEPTANCE_MATRIX.md) | 六层 Pass/Hold/No-Go、证据和签字条件 |
| 6 | [DEPLOYMENT_AND_OPERATIONS_RUNBOOK.md](DEPLOYMENT_AND_OPERATIONS_RUNBOOK.md) | 部署、日志、cleanup、回滚与升级路径 |
| 7 | [POC_DEMO_SCRIPT.md](POC_DEMO_SCRIPT.md) | CPU/frozen-evidence 8 分钟演示脚本 |
| 8 | [SECURITY_COST_CHECKLIST.md](SECURITY_COST_CHECKLIST.md) | 数据、依赖、机器人安全、成本和 ROI 约束 |
| 9 | [SOLUTION_ARCHITECT_EXECUTIVE_DECK.md](SOLUTION_ARCHITECT_EXECUTIVE_DECK.md) | 5 页客户/招聘经理决策叙事与真实 PoC 证据 |
| 10 | [templates/](templates/) | 客户范围、合同、manifest、预检、验收和成本模板 |
| 11 | [../../PRODUCT_SOLUTION_ARCHITECT_STRENGTHENING_SPEC.md](../../PRODUCT_SOLUTION_ARCHITECT_STRENGTHENING_SPEC.md) | 本轨道主 SPEC 与剩余产品化路线 |

技术事实需要深挖时才进入 `FINAL_PROJECT_SUMMARY.md`；不要把完整内部实验史放入客户主 deck。

---

## 3. 文档包结构

### 3.1 已有

- 主 SPEC；
- 三仓与 Policy Runtime 架构；
- M6 wiring evidence；
- unified report；
- public evidence；
- Badcase 案例。

### 3.2 本轮已交付

| 文档 | 目标读者 | 回答的问题 |
|---|---|---|
| `SOLUTION_BRIEF.md` | 决策者 | 客户问题、价值、范围、为什么现在做 |
| `CUSTOMER_DISCOVERY_QUESTIONNAIRE.md` | 客户技术/业务负责人 | 本体、策略、数据、风险、预算、RACI |
| `REFERENCE_ARCHITECTURE.md` | 架构师 | 逻辑图、部署画像、信任边界和 integration points |
| `POLICY_ONBOARDING_GUIDE.md` + `templates/` | 算法/平台工程师 | 新策略如何声明 identity/schema/runtime 并 preflight |
| `CUSTOMER_ACCEPTANCE_MATRIX.md` | QA/交付负责人 | 每层 Pass/Hold/No-Go 与签字证据 |
| `DEPLOYMENT_AND_OPERATIONS_RUNBOOK.md` | 运维/现场工程师 | 启停、日志、cleanup、回滚、升级和 escalation |
| `POC_DEMO_SCRIPT.md` | 售前/面试 | 8 分钟演示流程、事实边界和失败叙事 |
| `SECURITY_COST_CHECKLIST.md` | 架构/管理 | 数据权限、license、retention、BOM 与成本假设 |

### 3.3 尚未完成

- 完整 8 分钟录屏与第三方复现；
- 10–12 页 technical deck；
- 真实客户 discovery/acceptance 签字演练。

因此当前准确口径是“**解决方案文档、模板、CPU 自动预检、双次一致性演练和 5 页 executive deck 已完成；录屏、technical deck 与真实客户演练待完成**”，不能写成端到端产品已完成。

---

## 4. 客户叙事顺序

```text
客户风险
  → 当前流程为什么无法定位
  → 六层验收与责任所有权
  → Policy onboarding / fail closed
  → PoC 故障注入与统一报告
  → 当前 Hold / 已知限制
  → 下一阶段投入与停止条件
```

主 deck 只保留：1 张客户旅程、1 张 reference architecture、1 张 acceptance funnel、1 张 Badcase、1 张阶段路线图。

---

## 5. 三个客户案例

| 案例 | 客户价值 | 证据 |
|---|---|---|
| split 泄漏审计 | 防止把训练见过的数据包装为 held-out/OOD | `resume_description.md` §B.4 |
| interface 通过但 Task GT 失败 | 防止集成完成被误写成业务成功 | unified report + S4 gate |
| 近黑输入同 seeds 复测 | 用低成本观测与对照减少盲目重训 | Badcase summary |

每个案例都要落到时间、风险、成本或质量指标；没有实测 ROI 时只能写“建议 KPI / 待测目标”。

---

## 6. 不进入本轨道主材料的内容

- 大段公式、控制器推导和总线协议百科；
- 完整 related work 与科研 novelty；
- v1/v2 每轮训练的历史细节；
- 未验证的云、多租户、IAM、HA 或合规能力；
- 把 HOC、Risk、Runtime 包装成三条并列产品线；
- 把 fixture/mock/replay 冒充生产系统或真实策略闭环。

技术追问统一跳转到 [技术面试包](../technical_interview/README.md)，研究方法追问跳转到 [RA 包](../research_assistant/README.md)。

---

## 7. Solution Architect readiness

| ID | 自检项 | Pass 标准 |
|---|---|---|
| SA-T-01 | Discovery | 能在 15 分钟内澄清客户目标、约束、风险、预算和 RACI |
| SA-T-02 | Whiteboard | 能从客户问题画出 reference architecture 与信任边界 |
| SA-T-03 | PoC | 有错误包、正确 replay、R2/R3、unified report 的可重复演示 |
| SA-T-04 | Acceptance | 每个能力都有证据、owner、Pass/Hold/No-Go 和不可证明项 |
| SA-T-05 | Operations | 能说明部署、依赖、日志、cleanup、rollback 和 escalation |
| SA-T-06 | Business value | 能把能力映射到时间/成本/风险/质量，不编造 ROI |
| SA-T-07 | Executive communication | 5 页内讲清问题、方案、证据、边界和下一决策 |

---

## 8. 本轨道交付清单

- [x] 1 页 Solution Brief；
- [x] discovery questionnaire；
- [x] reference architecture + deployment profiles；
- [x] policy onboarding 文档与 10 个可填写模板；
- [x] acceptance matrix；
- [x] operations/security/cost checklist；
- [x] executable validator + valid/dim/hash/sequence fixtures；
- [x] 两次计时 PoC，规范化结果等价；
- [x] 5 页 executive deck；
- [ ] 10–12 页 technical deck；
- [ ] 8 分钟完整演示视频；
- [ ] 产品解决方案架构专用简历与四类面试案例。
