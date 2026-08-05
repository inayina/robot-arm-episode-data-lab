# 产品解决方案架构方向补强 SPEC

**版本**：v0.4  
**状态**：Solution docs、templates、CPU validator/fixtures、two-run rehearsal 与 5-page executive deck complete；recorded PoC / technical deck pending  
**日期**：2026-07-30  
**Owner**：`robot-arm-episode-data-lab`（解决方案定义、合同、验收与证据包）  
**涉及仓库**：`ros2-arm-teleoperation-suite`、`robot-arm-episode-data-lab`、`ros2-moveit-pybullet-bridge`  
**项目边界**：**Not task success / Not Sim2Real / Not real robot**。本文将现有三仓能力整理为客户可理解的上线前验证方案，不把它升级为生产平台，不授权新 Gate、新 runtime lane、新 risk 维度、新 dashboard、重训、扩 seed 或真机。

关联材料：

- [BOUNDARY_FREEZE.md](BOUNDARY_FREEZE.md)
- [PORTFOLIO_REFERENCE.md](PORTFOLIO_REFERENCE.md)
- [POLICY_RUNTIME_INTEGRATION_SPEC.md](../POLICY_RUNTIME_INTEGRATION_SPEC.md)
- [POLICY_RUNTIME_M6_WIRING_RESULTS.md](POLICY_RUNTIME_M6_WIRING_RESULTS.md)
- [UNIFIED_EVAL_REPORT.md](UNIFIED_EVAL_REPORT.md)
- [EVIDENCE_INDEX.md](EVIDENCE_INDEX.md)
- [DEMO_GUIDE.md](../DEMO_GUIDE.md)

---

## 0. 一句话决策

> **把项目包装为“机器人策略上线前验证与风险治理解决方案”：客户提交策略产物和合同，系统通过 Data → Offline → Interface → Behavior → Task → System 六层验收，输出可追溯的 Pass / Hold / No-Go 证据，但不替客户虚构任务成功。**

对外仍使用冻结主语“具身策略数据治理与分层验证框架”。Policy Runtime、Risk、HOC 是验证配套，不得拆成三条并列产品线。

目标岗位：

- 机器人 / 具身智能产品解决方案架构；
- AI 平台、仿真验证和机器人软件解决方案；
- 技术售前、PoC 架构、交付架构；
- 工业 AI / 数字孪生 / 模型评测平台方案；
- Forward-deployed / customer engineering 类岗位。

若目标是通用云解决方案架构，还需额外补充云部署、IAM、网络、安全、容量、成本和 IaC；当前三仓不能自动证明这些能力已实现。

---

## 1. 客户问题与解决方案边界

### 1.1 目标客户

| Persona | 核心问题 | 本方案交付 |
|---|---|---|
| 算法负责人 | 离线指标很好，为什么机器人仍失败？ | Offline / Behavior / Task 分栏与 failure attribution |
| 机器人平台负责人 | 新策略的 state/action、频率和安全语义能否接入？ | schema、adapter、runtime contract、interface smoke |
| 测试/质量负责人 | 结果是否可复现，旧结论是否被悄悄改写？ | immutable evidence、SHA lock、历史状态标签、统一报告 |
| 交付负责人 | 出现异常时由谁负责，何时 Hold / No-Go？ | 责任泳道、验收矩阵、runbook、升级与止损条件 |
| 管理/业务负责人 | 为什么还不能上线，下一笔投入买到什么信息？ | executive summary、风险清单、下一实验的信息增益 |

### 1.2 Jobs to Be Done

1. 当客户带来一个新 policy/checkpoint 时，在进入昂贵仿真或硬件前拦截合同与数据问题；
2. 当 interface Pass 但任务失败时，快速定位 Data / Model / Execution / Task GT / System 责任层；
3. 当实验结果发生修订时，保留历史证据并说明为什么新结果成为权威；
4. 当需要做 Go/Hold/No-Go 决策时，给出机器可读、可复核的依据；
5. 当客户移交给下一团队时，使用中立 handoff，而不是捆绑训练框架。

### 1.3 非目标

- 不承诺训练出成功策略；
- 不提供真实 Panda 驱动或现场安全认证；
- 不把 risk score 当任务成功；
- 不把 replay harness 称为在线策略大脑；
- 不把 mock ROS wiring、fixture dashboard 或 `ran_isaac=true` 称为生产部署；
- 不承诺多租户、云原生、高可用或合规认证已经实现。

---

## 2. 当前产品化基线

### 2.1 已实现且有代码/产物证据

| 能力 | 当前锚点 | 对客户的意义 |
|---|---|---|
| 三仓事实所有权 | 上游执行/GT，中游合同/数据/评测/handoff，下游 replay/risk/HOC | 减少多头定义和责任漂移 |
| 数据与动作合同 | `configs/robot_schemas/panda.yaml`、`training/adapters/upstream_m6.py` | 在入口发现 state/action 维度和语义错误 |
| release 与 inspection | `training/scripts/prepare_dataset_release.py`；SmolVLA immutable release 工具链 | 拒绝未通过 inspection 的数据发布；权威训练根可做 SHA 追踪 |
| checkpoint audit | Recovery config audit 与 adapter SHA | 防止 policy/preprocessor/runtime 静默不一致 |
| 统一评测信封 | `evaluation/unified_report.py` + schema + tests | 三后端同一报告结构，同时限制 claims 越权 |
| replay harness | 下游 `PolicyRunner`、`PandaActionAdapter`、handoff loader | 模型框架解耦的接口复用和回放验证 |
| task/system 对照 | continuous Task GT、scripted oracle、S4 gate | 把接口健康与物理任务结果分开 |
| 风险反馈接线证据 | M6 mock-policy ROS/DDS：R0 EXECUTED、R2 HELD、R3 ESTOPPED | 证明合同接线与裁决链，不证明物理执行或任务成功 |

### 2.2 文档声明、交付前需重新验证

- 三仓 CPU pytest 全绿：测试与历史结果存在，但每次对外演示前必须重新运行；
- M6 ROS/DDS wiring Pass：有结果文档与证据包，但新环境须重跑 smoke；
- HOC 截图是可复现 fixture 展示，不是 live authoritative policy 截图；
- SmolVLA online authoritative cutover 未启用；默认仍是受控的 legacy/mock/replay 路径；
- async double-buffer 只有 offline GPU bench，未接线上游在线节点；
- sensor fusion / risk 的真实 Panda handoff 仍未完整验证。

### 2.3 产品化缺口

1. 缺少明确的客户发现问卷和 use-case scoping；
2. onboarding 文档、模板、CPU validator 与四个错误/正确 fixtures 已补齐；真实 checkpoint 和客户 bundle 尚未接入；
3. 验收矩阵和 RACI 模板已完成，尚未经过真实客户签字演练；
4. 部署、成本、安全与运维文档已完成，容量和现场硬件仍是待测项；
5. PoC 脚本和双次 CPU 一致性演练已完成，但完整 8 分钟录屏尚未形成；
6. discovery → PoC → acceptance → handoff 的文档叙事和 5 页 executive deck 已完成，technical deck 尚未制作。

---

## 3. 解决方案原则

### SA-P1：从客户风险倒推架构

每个模块必须回答一个客户风险；没有验收项和责任人的模块不进入主架构图。

### SA-P2：一份事实，多种视图

工程师看 JSON/trace，负责人看 failure lane，管理者看 Hold/No-Go 与下一投入；三种视图必须来自同一证据，不手工改数字。

### SA-P3：Fail closed

未知 schema、hash 不一致、NaN/Inf、TTL 过期、sequence 回退或 task GT 缺失时默认拒绝、Hold 或结果降级，不做“尽量成功”的隐式兼容。

### SA-P4：安全、任务和系统健康分权

- Safety/Risk 可以 Hold 或 E-stop；
- 只有上游 continuous Task GT 判定 reach/grasp/lift/place；
- System health 不得覆盖 Task failure；
- replay 结果不得升级为 closed-loop success。

### SA-P5：PoC 必须可移交

PoC 结束时必须交付合同、部署参数、验收报告、已知限制、回滚/清理方法和 ownership，而不是只交一段视频。

### SA-P6：不新增并列产品线

Policy Runtime、Risk、HOC 只作为“具身策略数据治理与分层验证框架”的验证配套；不得分别包装成独立商业产品。

---

## 4. 参考解决方案

### 4.1 客户旅程

```text
Discovery
  → Policy / data intake
  → Contract & provenance preflight
  → Offline gate
  → Interface replay / wiring smoke
  → Bounded task validation（仅在获批时）
  → Risk / failure attribution
  → Unified acceptance report
  → Handoff + known limitations
```

### 4.2 六层验收视图

| 层 | 客户问题 | 证据 | 不可升级的结论 |
|---|---|---|---|
| Data | 数据能否被可信训练与复现？ | inspection、split、release SHA | 不能证明策略成功 |
| Offline | 模型在冻结专家数据上是否满足指标？ | metrics、open-loop gate | 不能证明闭环 |
| Interface | checkpoint 能否加载，动作能否正确映射？ | audit、replay、latency、clip | 不能证明物体被抓起 |
| Behavior | 轨迹和夹爪时序是否合理？ | phase/action traces | 不能替代 lift/place GT |
| Task | 是否真的 reach/grasp/lift/place？ | continuous simulator GT | 不能证明真机或 Sim2Real |
| System | 运行是否健康、安全反馈是否生效？ | QoS、deadline、risk、Hold/E-stop、cleanup | 不能覆盖 Task failure |

### 4.3 部署画像

| Profile | 用途 | 当前状态 | 必须说明 |
|---|---|---|---|
| Local CPU | schema、release、报告、replay 单测 | 已有实现路径 | 不含真实 VLA forward 或 Isaac |
| Lab GPU workstation | SmolVLA offline inference、queue bench | 有历史证据 | 环境版本、显存、依赖和计费边界 |
| Simulation workstation | MuJoCo/Isaac bounded validation | 已有有界证据 | 生命周期上限、GPU/EGL、Nuke On Done |
| Robot edge / real Panda | 未来现场接入 | Hardware Pending | IAM、网络、PREEMPT_RT、安全评审、物理急停均未验收 |

---

## 5. 功能需求

### SA-FR-01：Discovery 与范围冻结

必须提供结构化问卷：

- 业务目标和不可接受失败；
- 机器人本体、传感器、控制频率和动作语义；
- policy 输入、输出、chunk/replan、依赖和硬件需求；
- 数据来源、隐私、license 与 retention；
- 任务 GT 定义、Gate、预算和停止条件；
- 谁拥有 Data / Model / Execution / Safety / Task GT。

**验收**：生成一页 Solution Scope，明确 in-scope、out-of-scope、assumptions、dependencies 和 RACI。

### SA-FR-02：Policy Onboarding Kit

必须包含：

```text
policy_identity.yaml
observation_schema.yaml
action_schema.yaml
runtime_contract.yaml
artifact_manifest.json
adapter_mapping.md
preflight_report.json
```

**预检顺序**：身份与 hash → schema → state/action 维度 → camera key → chunk/K → normalization → adapter → runtime limits → claims。

**验收**：至少用三个 fixture 演示：正确包通过、action dim 错误被拒绝、hash/sequence 错误 fail closed。

### SA-FR-03：分层验证编排

每一层必须输出独立状态：`not_run | pass | hold | no_go | invalid`。后层不得反向覆盖前层原始结论。

**验收**：统一报告能同时呈现 open-loop Pass、replay smoke complete 和 Isaac Task Hold，且 `claims_task_success=false`。

### SA-FR-04：故障注入与安全演示

复用现有 M6 证据和测试路径，演示：

- 正常命令 → EXECUTED；
- R2 风险 → HELD；
- R3 风险 → ESTOPPED；
- stale/invalid command → fail closed。

**限制**：默认使用 mock/replay；不得把结果描述成物理力矩归零或真实机械臂急停认证。

### SA-FR-05：统一验收报告

报告必须有三个视图：

1. Executive：结论、主要风险、下一决策；
2. Architecture：责任边界、数据流、运行拓扑；
3. Evidence：输入 SHA、指标、trace、per-seed、失败原因和复现命令。

报告不变量：

```yaml
claims_task_success: false
claims_sim2real: false
claims_online_autonomous_grasp: false
risk_overrides_failure_lane: false
```

### SA-FR-06：交付与移交

必须交付：

- deployment parameters；
- dependency lock / environment audit；
- acceptance report；
- known limitations；
- rollback、cleanup 与 escalation runbook；
- artifact ownership 与 retention；
- 未完成项和下一阶段启动条件。

---

## 6. 非功能需求

| ID | 维度 | 目标要求 | 当前证据状态 |
|---|---|---|---|
| SA-NFR-01 | 可审计 | 核心产物带 source path、SHA、contract version | 部分已实现，需 onboarding 统一 |
| SA-NFR-02 | 可复现 | reference environment 下一条命令重出报告 | CPU 路径可设计验收；GPU/ROS 需环境说明 |
| SA-NFR-03 | 可观测 | command、execution、safety、task GT 分泳道 | M5/M6 有证据；新环境需重验 |
| SA-NFR-04 | 安全 | invalid/stale/unknown 默认 fail closed | runtime 合同已定义；真机未验收 |
| SA-NFR-05 | 可运维 | 显式生命周期、日志目录、cleanup、故障升级 | 仿真规则已冻结 |
| SA-NFR-06 | 可移植 | handoff artifact 不绑定训练框架 | 下游 replay 已有 1-ep smoke |
| SA-NFR-07 | 性能 | 分开报告 inference、command、deadline 和 end-to-end latency | 已有部分历史数字，不承诺 hard real-time |
| SA-NFR-08 | 安全与合规 | secrets、数据权限、license、retention 清单 | 当前缺口；只能作为设计要求 |
| SA-NFR-09 | 成本 | GPU 小时、仿真时长、存储和人工验收成本可估算 | 当前缺统一成本模板 |

---

## 7. 解决方案架构工作包

| 工作包 | 当前状态 | 本轮证据 |
|---|---|---|
| SA-WP0 | 文档完成 | 主 SPEC、边界与 canonical evidence 链接 |
| SA-WP1 | 文档完成 | Solution Brief、Discovery Questionnaire |
| SA-WP2 | CPU 交付完成 | Reference Architecture、10 个模板、validator 与四个 frozen fixtures |
| SA-WP3 | 部分完成 | onboarding 双次 CPU 演练一致；完整 8 分钟录屏与第三方复现待完成 |
| SA-WP4 | 文档完成 | Acceptance、Operations、Security/Cost 文档与模板 |
| SA-WP5 | 部分完成 | 5 页 executive deck 已完成；technical deck、视频、专用简历与面试案例待完成 |

### SA-WP0：事实与产品边界冻结

**任务**：把 Current / Historical / Superseded / Hardware Pending 映射到客户术语；所有主数字来自最小公开证据包。

**验收**：Solution Brief、demo、简历、slide 与 `FINAL_PROJECT_SUMMARY.md` 无事实冲突。

### SA-WP1：客户发现与价值主张

**产物**：

- `CUSTOMER_DISCOVERY_QUESTIONNAIRE.md`；
- `SOLUTION_BRIEF.md`；
- 3 个 persona 的 pain → capability → evidence → outcome 映射；
- “何时不适合采用本方案”清单。

**推荐价值指标**：

- 首次接入耗时；
- preflight 拦截的合同错误数；
- trace/provenance 完整率；
- 从异常到 failure lane 的定位耗时；
- 被止损的无效 rollout/GPU 预算；
- acceptance report 自动生成覆盖率。

这些是建议 KPI，**不是当前已测结果**。

### SA-WP2：Reference Architecture 与 Onboarding Kit

**产物**：

- 一张客户视角 reference architecture；
- 一张 deployment topology；
- policy onboarding 模板与三个 fixture；
- compatibility matrix；
- RACI 与信任边界图。

**限制**：复用既有 schema、runtime、handoff；不创建新 runtime lane 或 risk 维度。

### SA-WP3：8 分钟可复现 PoC

**演示脚本**：

| 时间 | 演示 | 证明什么 |
|---|---|---|
| 0:00–1:00 | 客户问题与架构 | 方案为何存在 |
| 1:00–2:00 | 错误 policy bundle preflight | 合同错误能在昂贵执行前拦截 |
| 2:00–3:30 | 正确 bundle + replay | handoff 与执行接口可复用 |
| 3:30–5:00 | R2/R3 故障注入 | Hold/E-stop 裁决链按合同工作 |
| 5:00–6:30 | unified report | offline/interface/task 不互相冒充 |
| 6:30–8:00 | 已知限制与下一阶段 | 能做负责任的交付决策 |

**目标验收值**（待实测，不是当前事实）：

- reference 环境从命令启动到报告生成 ≤10 分钟；
- 8 分钟主演示不依赖临场手工修改 JSON；
- 3 个 fixture 结果可重复；
- trace/provenance 必填字段完整率 100%；
- 演示结束自动或显式执行物理清理。

### SA-WP4：验收、运维、安全与成本

**产物**：

- `CUSTOMER_ACCEPTANCE_MATRIX.md`；
- `DEPLOYMENT_AND_OPERATIONS_RUNBOOK.md`；
- failure escalation tree；
- security/privacy/license checklist；
- BOM、GPU/CPU/存储/人工成本模板；
- PoC → pilot → production readiness 的阶段闸门。

**真机边界**：production readiness 只能列 Hardware Pending 项，不能以仿真 smoke 替代现场验收。

### SA-WP5：求职与客户表达

**交付物**：

- 1 页 Solution Brief；
- 5 页 executive deck；
- 10–12 页 technical deck；
- 8 分钟 demo 视频；
- discovery、whiteboard、PoC、escalation 四类面试案例；
- 产品解决方案架构专用简历条。

**推荐项目标题**：

> 机器人策略上线前验证与风险治理解决方案架构

**推荐主句**：

> 面向机器人算法团队设计从 policy/data intake、合同预检、分层 Gate、replay 与 bounded task validation 到统一验收报告的参考方案，用 SHA、failure lane 和安全反馈把“接口通过”与“任务成功”分开，并提供可移交的 PoC 与止损机制。

---

## 8. 客户验收矩阵

| ID | 验收项 | Pass 条件 |
|---|---|---|
| SA-AC-01 | 客户范围 | use case、成功条件、非目标、预算、RACI 完整 |
| SA-AC-02 | Onboarding | 正确包通过；dim/hash/sequence 三类错误 fail closed |
| SA-AC-03 | 分层报告 | Data/Offline/Interface/Behavior/Task/System 均可独立解释 |
| SA-AC-04 | 安全反馈 | mock/replay R0/R2/R3 分别得到 EXECUTED/HELD/ESTOPPED |
| SA-AC-05 | 证据追踪 | 核心报告字段可追到 source path 与 SHA |
| SA-AC-06 | 可重复演示 | reference 环境连续两次得到等价规范化结果 |
| SA-AC-07 | 运维移交 | 启停、cleanup、rollback、日志、升级路径完整 |
| SA-AC-08 | 商业表达 | 技术能力映射到时间、风险、成本或质量指标，不编造 ROI |
| SA-AC-09 | 诚实边界 | fixture/mock/replay/Hardware Pending 均被明确标注 |

---

## 9. 建议节奏

| 周期 | 目标 | 主要产物 |
|---|---|---|
| Week 1 | Discovery、persona、value proposition | questionnaire、Solution Brief v0 |
| Week 2 | Reference Architecture、onboarding 和 RACI | 两张架构图、模板、fixture 设计 |
| Week 3 | 8 分钟 PoC 与验收矩阵 | demo runbook、acceptance report |
| Week 4 | 运维/安全/成本与求职包装 | deck、视频、简历、handoff 包 |

默认四周只做文档、fixture、CPU/mock/replay 路径和既有证据重组；任何 GPU、ROS live、Isaac 或真实模型 cutover 均需单独评估授权和清理要求。

---

## 10. 禁止话术

| 禁止 | 正确表达 |
|---|---|
| “机器人策略上线平台” | “策略上线前验证与 readiness 方案” |
| “已经支持生产级 VLA 在线控制” | “M6 mock/replay 接线已验证；SmolVLA authoritative cutover 未启用” |
| “HOC 实时展示了自主抓取” | “HOC fixture/M6 trace 展示四泳道证据关联” |
| “Risk 判断任务成功” | “Risk 只做 readiness/safety；Task GT 由上游判定” |
| “PyBullet 完成闭环抓取” | “PolicyRunner replay smoke，`is_closed_loop=false`” |
| “已经完成 Sim2Real” | “Sim2Sim / Sim2Real-readiness；真机 Hardware Pending” |
| “immutable release 都由通用 release 脚本生成” | “区分 non-overwrite release 与带指纹的 immutable release” |

---

## 11. Definition of Done

本 SPEC 完成必须同时满足：

- 招聘经理能在 1 页内读懂客户问题、方案、价值和边界；
- 技术面试官能从 reference architecture 追到三仓代码和证据；
- 新策略 onboarding 有模板、错误 fixture 和验收报告；
- 8 分钟 PoC 可重复，不依赖手工篡改结果；
- discovery、PoC、acceptance、handoff、operations 五阶段闭环；
- 所有商业价值使用可测 KPI 或“待实测目标”，不编造 ROI；
- 不新增冻结范围内的 Gate/runtime/risk/dashboard 功能；
- 最终材料明确写出 **Not task success / Not Sim2Real / Not real robot**。
