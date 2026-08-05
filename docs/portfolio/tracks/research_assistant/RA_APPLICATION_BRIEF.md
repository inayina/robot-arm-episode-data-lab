# RA Application Brief

**版本**：v1.0  
**目标岗位**：机器人学习评测、模仿学习、Embodied AI Benchmark、仿真研究工程  
**边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[RA 科研助理文档包](README.md)

---

## 1. 项目标题

中文：**具身策略离线—闭环失配研究与可审计评测框架**  
英文：**Auditable Evaluation of the Offline-to-Closed-Loop Gap in Embodied Policies**

## 2. 约 150 字摘要

我围绕机器人模仿学习中“专家状态上的低预测误差为何不能转化为自主闭环成功”开展评测研究。在独立 prospective 数据上，SmolVLA Recovery v3 的 first-action 指标通过冻结 Gate，但在有界 Isaac 闭环中 lift 0/5。通过 scripted oracle、同 seeds 修光复测、动作合同与连续 Task GT，我逐层排除数据泄漏、接口、物理链和相机失明；进一步比较 36 条训练 episode 与 5 条闭环 episode，得到 normalized state energy distance `2.0554`，且 5/5 episode 的末 progress-bin 偏移高于首 bin。结果方向性支持闭环状态分布偏移，但不构成 phase、failure precedence 或因果证明。

## 3. 简历条目

> 构建 Panda/VLA 离线—闭环失配的可审计评测研究：在 10 条独立 prospective episode、2,593 帧上验证 canonical first-action Gate Pass，并用 bounded S4（interface 5/5、lift 0/5）、scripted oracle 5/5 与 same-seed relight 分离 Data/Interface/Behavior/Task/System failure lanes；实现 36-train/5-rollout 的 W1、energy distance 与 episode bootstrap，5/5 rollout 末段偏移高于首段，同时明确不作 phase/因果声明。

## 4. 30 秒讲述

> 我的项目研究一个很具体的机器人学习问题：为什么策略在专家状态上预测得很准，放进自主闭环却失败。Recovery v3 的 prospective first-action Gate 是 Pass，但 Isaac 中 lift 0/5。我没有继续盲目训练，而是用 oracle、同 seeds 复测、接口 trace 和 Task GT 逐层排查，再用冻结数据量化闭环偏移：5/5 episode 的末段偏移都高于首段。这个结果支持 covariate-shift 方向，但因缺少真实 phase 和 failure-onset，我没有把相关性写成唯一根因。

## 5. 2 分钟讲述

1. **问题**：offline EE/gripper 指标与 closed-loop task funnel 出现断层；
2. **协议**：train/threshold/prospective 身份冻结，canonical H=1 与 queued/closed-loop 分栏；
3. **对照**：oracle 同物理链 lift 5/5，排除“仿真抓不起”；
4. **反证**：near-black 首轮被 same-seed relight 复测降级为 Superseded；
5. **结果**：interface 健康但 learned policy 不下探、不闭爪，责任层落在 Behavior + Task；
6. **克制**：MuJoCo 只有 early-stopped seed1，H2 仍未被完整证明；
7. **下一步**：改进 telemetry contract，记录权威 phase 与 failure-onset，再复做 phase-conditioned 分析；当前不重训、不扩 seeds。

## 6. 10 分钟答辩结构

| 时间 | 内容 | 必须回答 |
|---:|---|---|
| 0–1 min | RQ 与为何重要 | offline metric 为什么不能代表 rollout |
| 1–3 min | 数据和评测协议 | prospective 独立性、H=1、Task GT |
| 3–5 min | 关键正/负结果 | Pass/Hold/oracle/same-seed |
| 5–7 min | H1–H6 更新 | 哪个证据改变哪个假设 |
| 7–8 min | threats/statistics | small-N、frame dependence、early-stop |
| 8–9 min | RA-WP2 result | W1/SMD/energy distance/bootstrap 与 proxy 边界 |
| 9–10 min | fit 与下一步 | 对目标实验室能贡献什么 |

## 7. 导师邮件模板

**Subject**：RA application — auditable evaluation of offline-to-closed-loop gaps in robot imitation learning

> 老师您好，我关注您在【目标方向/论文】中关于【具体研究问题】的工作。我目前完成了一个 Panda/VLA evaluation study：策略在独立 prospective 专家状态上通过 first-action Gate，但在有界闭环中 lift 0/5。我通过 scripted oracle、same-seed relight、动作合同和 continuous Task GT 分离了物理链、视觉、接口与行为因素，并完成了带 provenance、episode bootstrap 和非因果边界的 closed-loop state-shift 量化。  
>  
> 我对贵组的契合点不是提出一个未经验证的新 policy，而是可复现评测、负结果分析、实验治理和机器人系统实现。我希望进一步参与【对方具体项目】，尤其是【数据/benchmark/failure analysis/robot learning systems】。附件包含 1 页 brief、5 页 slides 和最小证据入口。如您认为方向匹配，我希望有机会用 15 分钟介绍研究问题和当前边界。  
>  
> 谢谢！【姓名 / 联系方式 / GitHub】

邮件发送前必须替换目标导师论文与具体契合点；禁止群发同一模板。

## 8. 面试高频追问

| 追问 | 回答核心 |
|---|---|
| 你的 novelty 是什么？ | 评测/归因协议与完整负结果案例，不是新模型 |
| 如何证明 covariate shift？ | 现有 W1/energy/bootstrap 与 5/5 末段增大提供方向性证据；无真实 phase/failure-onset，不能声称因果证明 |
| 为什么不多跑 seeds？ | lift 0/5 已触发止损；先做现有数据的信息增益分析 |
| oracle 5/5 说明什么？ | 名义物理链有上界，不说明 learned policy 成功 |
| 2,593 帧能当 N=2,593 吗？ | 不能；主要 sampling unit 是 episode，帧相关 |
| 为什么适合 RA？ | 能把系统异常转成可证伪假设、控制实验、统计边界和复现资产 |
