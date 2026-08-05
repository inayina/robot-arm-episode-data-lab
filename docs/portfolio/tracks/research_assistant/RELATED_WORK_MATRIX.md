# Related Work Matrix

**版本**：v1.0  
**检索日期**：2026-07-30  
**来源规则**：只链接原论文或官方会议页面；不以博客替代论文。  
**定位结论**：当前最稳妥定位是 **evaluation study / engineering replication with negative results**，不是新 imitation-learning algorithm。
**边界**：文献相关性不证明当前项目任务成功（Not task success）、Sim2Real 或真机能力。

返回：[RA 科研助理文档包](README.md)

---

## 1. 文献矩阵

| 年份 | 工作 | 研究贡献 | 与本项目的关系 | 本项目不重复声称 |
|---:|---|---|---|---|
| 2010 | [Efficient Reductions for Imitation Learning](https://proceedings.mlr.press/v9/ross10a.html) | 形式化 learned policy 改变测试状态分布及误差随 horizon 累积 | 为 offline expert-state fit ≠ rollout performance 提供经典理论动机 | 不声称重新证明其 regret bound |
| 2017 | [DART](https://proceedings.mlr.press/v78/laskey17a.html) | 用 demonstration noise 缓解 BC covariate shift | 提供 H2 的方法背景和 recovery-state 视角 | 本项目未采 DART 数据、未训练 DART |
| 2023 | [ACT / Learning Fine-Grained Bimanual Manipulation](https://arxiv.org/abs/2304.13705) | action chunking 与 temporal aggregation 应对长时精细操作 | 解释项目中的 chunk/K 与 ACT diagnostic baseline | ACT 在本项目已冻结，不能移植论文成功率 |
| 2023 | [Diffusion Policy](https://arxiv.org/abs/2303.04137) | action diffusion、receding-horizon control 与多模态动作建模 | 表明 action sequence 与 rollout control 是策略评测关键变量 | 本项目没有实现或比较 Diffusion Policy |
| 2023 | [Waypoint-Based Imitation Learning](https://proceedings.mlr.press/v229/shi23b.html) | 通过 waypoint 降低有效决策 horizon | 支持 phase/trajectory structure 对 compounding error 的影响 | 本项目只做 phase-conditioned 诊断，不提出 waypoint 方法 |
| 2023 | [HYDRA](https://proceedings.mlr.press/v229/belkhale23a.html) | 混合 action representation 缓解 manipulation state shift | 提醒 action representation 可能改变闭环稳定性 | 本项目不比较 hybrid action heads |
| 2023 | [Open X-Embodiment](https://arxiv.org/abs/2310.08864) | 跨本体数据格式与 generalist policy 数据规模 | 强化 dataset/schema/embodiment identity 的必要性 | 本项目只有 Panda 主线，不声称跨本体泛化 |
| 2023 | [BEHAVIOR-1K](https://proceedings.mlr.press/v205/li23a.html) | 大规模具身任务定义与 realistic simulation benchmark | 说明任务定义、物理属性和 benchmark governance 是研究对象 | 本项目只是单方块有界任务，不声称广泛 benchmark coverage |
| 2024 | [SIMPLER](https://arxiv.org/abs/2405.05941) | 研究仿真评测与真实 policy behavior/performance 的对齐 | 与本项目的 Sim2Sim/readiness 分层直接相关 | 本项目没有 paired sim-real，因此不能声称 sim-real correlation |
| 2024 | [BAKU](https://arxiv.org/abs/2406.07539) | 系统比较 observation trunk、action head、chunking 与 temporal smoothing 的多任务策略设计 | 提醒 action chunk 和调度必须作为显式实验变量 | 本项目没有实现 BAKU，也不把 queue bench 当任务改进 |
| 2025 | [AutoEval](https://arxiv.org/abs/2503.24278) | 自动化、可扩展的真实机器人策略评测与 reset | 对 reproducibility、success detection 和 evaluation operations 有启发 | 本项目没有真实机器人自动评测系统 |
| 2025 | [RoboEval](https://arxiv.org/abs/2507.00435) | 用阶段化行为指标补充 binary success | 直接支持 Behavior 与 Task GT 分栏及 failure localization | 本项目规模小，不声称提出通用 benchmark |
| 2025 | [The Pitfalls of Imitation Learning when Actions are Continuous](https://proceedings.mlr.press/v291/simchowitz25a.html) | 给出连续状态/动作模仿中 execution error 可远大于 expert-distribution error 的负结果 | 强化“低 first-action error 不蕴含 rollout 稳定”的理论边界 | 本项目不验证该论文的全部假设或下界 |
| 2025 | [Robot Policy Evaluation for Sim-to-Real Transfer](https://arxiv.org/abs/2508.11117) | 从 benchmark 角度讨论复杂度、扰动和 sim-real alignment | 支持逐层增加复杂度与明确仿真外推边界 | 本项目没有 real-world alignment 数据 |

矩阵共 14 篇，其中 2024–2025 的直接相关工作不少于 6 篇，满足本 SPEC 的近三年覆盖目标；经典工作用于问题动机，近期工作用于评测设计和定位。

## 2. 研究空位

已有工作分别讨论 compounding error、action representation、大规模 benchmark、simulated evaluation 与自动化评测。本项目可贡献的窄空位是：

> 在一个完整保留失败历史的 Panda/VLA 工程案例中，把 prospective expert-state first-action Gate、runtime interface、phase behavior、continuous Task GT、oracle upper bound 和 same-seed counterfactual 串成同一条可审计归因链，并预注册 closed-loop state-shift 量化。

这不是“提出新 BC 方法”，也不是“大规模 benchmark”。更合适的研究问题是：**哪些证据足以支持或反驳 offline-to-closed-loop gap 的具体解释，以及评测协议如何避免错误升级结论。**

## 3. Novelty Claim 边界

可写：

- “a reproducible evaluation case study”；
- “a layered evidence protocol for separating offline fit, interface validity, behavior, and Task GT”；
- “negative-result-driven attribution with prospective split, oracle control, and same-seed counterfactual”。

不可写：

- “首次发现 behavior cloning covariate shift”；
- “提出新的 VLA/BC 算法”；
- “证明仿真结果能预测真机”；
- “建立通用机器人 benchmark”；
- “证明 H2 是唯一因果根因”。

## 4. 待进一步补充

投稿或正式申请前，还应针对目标导师近 3 年论文增加 3–5 篇定制条目，并说明本项目能复用其实验协议、数据或 failure-analysis 视角的具体位置。该定制不能由通用矩阵替代。
