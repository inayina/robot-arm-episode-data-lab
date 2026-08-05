# Research Brief：VLA First-Action 精度与闭环任务表现的失配

**版本**：v1.0  
**研究类型**：机器人模仿学习 evaluation study / system study  
**状态**：Current evidence synthesized；closed-loop shift quantified with normalized-progress proxy  
**边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[RA 科研助理文档包](README.md)

---

## 研究问题

在 Panda 单方块操作中，为什么一个策略能在独立 prospective 专家状态上通过 canonical first-action open-loop Gate，却在自主闭环仿真中无法完成 grasp/lift？哪些分层指标能够区分数据、接口、行为、任务和系统失败？

这个问题源于一个明确断层：Recovery v3 在 10 条独立 prospective episode、2,593 帧上达到 EE RMSE `0.0253 m`、gripper balanced accuracy `0.9943`，通过冻结的 `eval_gate_v3`；但同一策略在修光后的 bounded Isaac S4 中 interface 5/5，reach 1/5、grasp 0/5、lift 0/5，最终 Hold。

## 方法

研究采用证据分层和假设消除，而不是继续调参：

1. 冻结 train / threshold-design / prospective eval 身份，审计 overlap；
2. 把 expert-state H=1 指标、action interface、行为 trace、continuous Task GT 和系统健康分栏；
3. 用 scripted oracle 建立同一仿真物理链的系统上界；
4. 用同 seeds relight 复测控制视觉可见性变量；
5. 保留 early-stop、small-N、非独立帧和域差等 threats；
6. 经用户明确批准后执行 closed-loop state shift 分析；因原始 trace 缺少可靠 phase，按运行前 Amendment A 改用 normalized-progress proxy。

## 当前结果

| 证据 | 观察 | 对假设的影响 |
|---|---|---|
| prospective open-loop | Gate Pass，且 train/threshold overlap 均为空 | 说明 expert-state first-action fit 成立 |
| relight S4 | interface 5/5，但 lift 0/5 | 定位 offline→closed-loop gap |
| oracle v2b | 同物理链 lift 5/5 | 排除“仿真链必然抓不起” |
| same-seed relight | 近黑首轮被修光复测证伪 | 相机失明不是权威 run 的主因 |
| runtime trace | 150/150 动作未限幅，无 E-stop | 接口吞动作不是当前主解释 |
| MuJoCo seed1 | early-stopped，仍未闭爪 | 支持 H2，但不足以证明唯一因果 |

RA-WP2 进一步量化了 state15 shift：global mean W1 `0.7228`、energy distance `2.0554`；5/5 episode 的末 progress-bin energy 高于首 bin。失败责任层仍位于 Behavior + Task GT，闭环 BC / covariate shift 获得方向性支持；但真实 phase 和 failure-onset 字段缺失，因此不是完整因果证明。

## 研究贡献与边界

本工作的贡献不是新 policy architecture，而是：

- 一个区分 offline fit、interface health、behavior 和 Task GT 的评测协议；
- 一套保留 Superseded/Invalid/Hold 的 benchmark governance 方法；
- 一个由 oracle、same-seed counterfactual 和 prospective split 支撑的失败归因案例；
- 一个带 provenance、合成测试和 episode-level bootstrap 的闭环状态分布偏移分析。

局限包括：learned policy closed-loop 仅 5 seeds；MuJoCo 对照仅 early-stopped seed1；没有真实机器人；由于 telemetry 缺少权威 phase 与 failure-onset，无法完成真实 phase-conditioned 与 failure-precedence 分析。因此最合适的学术定位是 **evaluation study / engineering replication with negative results**。

## 下一最小信息增益步骤

优先改进 telemetry contract：在 observation trace 中记录权威 Task phase 与 failure-onset event timestamp，再决定是否复做 phase-conditioned analysis。当前不需要重训或扩 Isaac seeds；任何新 rollout 仍需单独批准。

身份冻结见 [research_identity.yaml](research_identity.yaml)，详细预注册见 [EXPERIMENT_PREREGISTRATION.md](EXPERIMENT_PREREGISTRATION.md)。
