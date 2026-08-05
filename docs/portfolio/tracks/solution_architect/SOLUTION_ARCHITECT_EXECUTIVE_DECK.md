# 机器人策略上线前验证与风险治理——Executive Deck

**版本**：v1.0 / 5 pages  
**受众**：招聘经理、客户技术负责人、交付负责人  
**讲述时长**：5–8 分钟  
**边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[解决方案架构文档包](README.md)

---

## Page 1/5：客户决策——为什么不能从离线指标直接走向机器人

### 业务风险

一个策略“离线指标不错”，仍可能因为数据泄漏、动作语义、checkpoint 身份、执行接口、观测质量或闭环行为而失败。若这些问题没有分层，团队往往继续投入 GPU、rollout 和硬件时间，却不能回答投入消除了哪个不确定性。

### 要做的决策

> 在进入昂贵仿真或硬件前，这个 policy bundle 是否具备可验证的身份、合同和下一阶段资格？

### 方案承诺

- 尽早拦截可确定的合同错误；
- 把 Data / Offline / Interface / Behavior / Task / System 六层证据分开；
- 输出可追溯的 Pass / Hold / No-Go，而不包装任务成功；
- 把下一投入关联到明确风险、owner 和停止条件。

建议 KPI 是首次接入耗时、preflight 拦截数、证据完整率、failure-lane 定位耗时和被止损的无效预算；当前未实测客户 ROI。

---

## Page 2/5：解决方案——六层验收与明确责任

```text
Customer Policy / Data
  → Identity + SHA + Schema + Runtime Preflight
  → Data / Offline Evidence
  → Neutral Handoff + Interface Replay
  → Behavior / Task Validation（高成本阶段需批准）
  → System / Safety Evidence
  → Unified Acceptance + Handoff
```

| Layer | 回答的问题 | 决策所有权 |
|---|---|---|
| Data | 数据、split、schema 和 provenance 是否可信 | 中游合同/数据 |
| Offline | 冻结专家态上的预测是否过线 | 中游评测 |
| Interface | artifact 能否加载、动作能否正确映射 | 中游合同 + 下游 replay |
| Behavior | 轨迹、夹爪和时序是否合理 | 评测协议 |
| Task | 是否实际 reach/grasp/lift/place | 上游 continuous Task GT |
| System | QoS、deadline、risk、Hold/E-stop 是否健康 | 上游 Safety + 下游 Monitor |

关键治理规则：Risk 可以 Hold/E-stop，但不能改写 Task GT；Interface Pass 不能升级为任务成功。

---

## Page 3/5：可运行 PoC——错误在昂贵阶段前被拦截

### Policy Onboarding Preflight

CPU validator 按 G0–G7 检查 identity、artifact SHA、observation/action、runtime、adapter、claims 和 evidence。

| Fixture | 实际结果 | 决策 |
|---|---|---|
| valid bundle | `pass` | 可进入 offline/interface |
| action 7-D vs declared 8-D | `invalid_action_dim` | Invalid，停止 |
| checkpoint SHA 不一致 | `contract_mismatch` | Invalid，停止 |
| command sequence 回退 | `command_sequence_regression` | Hold，整改 |

### 两次计时演练

- Run 1：`17.923 ms`；Run 2：`16.470 ms`；
- 四案例均 4/4 匹配冻结预期；
- normalized SHA 两次同为 `b3f0e9e2…a004`；
- NFR-02 reproducibility：`pass`。

证据：[双次演练报告](../../../../evidence/solution_architect/policy_onboarding_rehearsal_20260730/README.md)。计时仅覆盖进程内四案例验证与 JSON 写入，不是模型推理或端到端机器人时延。

---

## Page 4/5：为什么还不能上线——分层证据避免错误结论

| 已有证据 | 当前结论 | 不能证明 |
|---|---|---|
| Recovery v3 open-loop | expert-state first-action Pass | closed-loop success |
| PolicyRunner | interface/replay smoke complete | autonomous grasp |
| bounded Isaac S4 | interface 5/5；lift 0/5，Hold | Sim2Real / production |
| M6 mock ROS/DDS | R0 EXECUTED、R2 HELD、R3 ESTOPPED | 真实力矩归零/硬件认证 |
| onboarding rehearsal | contracts 可重复 fail closed | 模型质量或 Task success |

当前总体决策：**readiness evidence available / Task Hold / No production claim**。

未完成项：真实客户 bundle、完整 8 分钟录屏、现场安全验收、云 IAM/HA、多租户和真实 Panda。任何新 Isaac、训练或真机阶段都必须单独批准。

---

## Page 5/5：交付路线——每一笔投入购买明确的信息

| 阶段 | 交付 | Exit decision |
|---|---|---|
| Discovery | scope、Task GT、预算、RACI、停止条件 | 是否进入 PoC |
| Preflight | identity/schema/hash/runtime/adapter report | Pass / Invalid / Hold |
| CPU PoC | 四类 fixture、双次可重复报告 | 是否接入真实客户 bundle |
| Technical PoC | offline/interface/system evidence | 是否申请 bounded validation |
| Bounded validation | continuous Task GT（需批准） | Task Pass/Hold，仅该协议 |
| Handoff | acceptance、known limitations、runbook | 下一阶段 owner 签字 |

### 当前建议决策

1. 使用脱敏的真实客户 bundle 替换 fixture，保持相同合同；
2. 完成 8 分钟录屏和一次第三方复现；
3. 只有前置证据通过，才评估 GPU/仿真预算；
4. 真机保持 Hardware Pending，另行完成安全、标定、网络和操作员验收。

**最终主张**：这是一套机器人策略上线前的验证与风险治理方案，不是成功抓取模型，也不是已经上线的生产平台。
