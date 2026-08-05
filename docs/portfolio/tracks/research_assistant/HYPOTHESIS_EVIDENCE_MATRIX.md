# Hypothesis–Evidence Matrix

**版本**：v1.0  
**目的**：把每个解释写成可被反驳的假设，并记录证据如何加强、降级或保留它。  
**边界**：矩阵不授权新实验；“排除”只限当前协议和证据范围；不证明任务成功（Not task success）、Sim2Real 或真机。

返回：[RA 科研助理文档包](README.md)

---

## 1. 主问题与观察

**RQ1**：为何 Recovery v3 的 prospective canonical first-action open-loop Pass 没有迁移为 bounded closed-loop lift？

冻结观察：Offline EE `0.0253 m`、grip BA `0.9943`、Pass；S4 interface 5/5、reach 1/5、grasp/lift 0/5、Hold。两者回答不同问题，不能互相覆盖。

## 2. 假设矩阵

| ID | 假设 | 可观测预测 | 当前支持 | 当前反证 | 状态 |
|---|---|---|---|---|---|
| H1 | 视觉不可见/外观域差是主因 | 可见性修复后行为明显改善 | 首轮 near-black 说明视觉链曾失效 | 同 seeds relight 后仍 grasp/lift 0/5 | 显著降级；其它视觉域差保留 |
| H2 | 自主状态偏离专家分布导致 compounding error | state distance 在失败前随时间/phase 增长，并与 Z/grip 退化对齐 | RA-WP2：global mean W1 `0.7228`；5/5 late progress energy > early；不下探/不闭爪 | 无可靠 phase/failure onset，不能检验先后或因果 | 方向性支持，未证明因果 |
| H3 | observation/state/action 合同错配 | 修复合同后 offline/online 都应显著变化 | 历史 v1/v2 有 state 契约问题 | Recovery state15、camera1、checkpoint audit、runtime encoding 已一致 | 当前范围基本排除 |
| H4 | 执行接口、限幅或 safety 吞掉动作 | clipped/Hold/E-stop 应与失败同步 | learned policy 任务失败 | interface 5/5、150/150 unclipped、无 E-stop；oracle 同链 5/5 | 当前范围基本排除 |
| H5 | 同步推理和 queue deadline 造成时序退化 | deadline miss 与行为失败时序对应；async 应改善闭环 | offline bench 显示 sync miss，async 可减少 miss | async 尚未在线接线，无法比较任务行为 | 保留为系统候选 |
| H6 | 物理链/Task GT 无法完成抓取 | oracle 在同链也应持续失败 | oracle v1 曾 lift 0/5 | 修复物理链后 oracle v2b lift 5/5 | 名义链已排除；learned policy 未成功 |

## 3. 假设更新日志

| 事件 | 原先可能结论 | 新证据 | 更新后结论 |
|---|---|---|---|
| evaluator v0 混淆 command/state | ACT/策略结果可直接解释 | evaluator preflight 发现语义错误 | 旧结果 Invalid，先修测量链 |
| oracle v1 lift 0/5 | learned policy 是唯一失败源 | oracle 也失败 | 先修物理链，暂停策略归因 |
| oracle v2b lift 5/5 | 物理链仍不可用 | 同链 5/5 | 建立系统上界，但不升级 learned policy |
| dark S4 reach 3/5 | 可能“部分成功” | policy input 近黑 | 首轮失去权威资格 |
| relight same seeds | 修光可能解决失败 | reach 1/5、grasp/lift 0/5 | H1 降级，H2 相对增强 |
| MuJoCo seed1 early-stop | 域差可能是唯一主因 | 训练域也未闭爪 | H2 获方向支持，但 N=1 且 early-stop，不能定因 |

## 4. 可证伪条件

H2 将被明显削弱，如果预注册分析发现：

- 自主 rollout 与训练态的 phase-conditioned state distance 没有随时间增长；
- 距离上升发生在行为失败之后，而不是之前；
- 距离变化无法跨 episode 复现；
- 主要偏移只出现在不进入 policy 的 privileged 变量；
- 时序/deadline 指标对失败的解释力明显更高。

相反，即使距离与失败相关，也只能写“supports H2”，不能写“proves causal covariate shift”。

## 5. 决策规则

- 新证据支持某假设：标记 `strengthened`，保留替代解释；
- 出现直接反证：标记 `downgraded` 或 `excluded_in_current_scope`；
- provenance、样本完整性或 evaluator 失败：结果标记 `invalid`；
- 只有单 seed/early-stop：只允许 `directional evidence`；
- 任何结果都不得移动 `eval_gate_v3` 或改写历史 S4 Hold。
