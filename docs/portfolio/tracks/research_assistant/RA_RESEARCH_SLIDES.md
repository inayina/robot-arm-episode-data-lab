# RA Research Slides：Offline-to-Closed-Loop Gap

**版本**：v1.0 / 5 pages  
**讲述时长**：5 分钟主讲 + 5 分钟问答  
**研究定位**：evaluation study / negative-results-driven failure attribution  
**边界**：**Not task success / Not Sim2Real / Not real robot**。

返回：[RA 科研助理文档包](README.md)

---

## Page 1/5：Research Question

### 为什么 expert-state first-action Pass 没有迁移成 autonomous lift？

```text
Prospective expert states
  EE RMSE 0.0253 m / grip BA 0.9943 / Gate Pass
                      ↓ distribution + execution feedback
Bounded autonomous rollout
  interface 5/5 / reach 1/5 / grasp 0/5 / lift 0/5 / Hold
```

**RQ1**：断层首先出现在哪一层、哪个 phase？  
**RQ2**：闭环状态偏移是否在行为失败前累积？  
**RQ3**：哪些离线指标有诊断价值，哪些只表示 expert-state fit？

贡献定位：把 offline、interface、behavior、Task GT 和 system evidence 放进同一可审计假设链；不提出新 VLA architecture。

---

## Page 2/5：Protocol and Controls

| Design | 控制的偏差 |
|---|---|
| train-only 36 ep + prospective eval-only 10 ep | split / threshold contamination |
| canonical first-action、stride=1、full episode | 离线语义漂移 |
| continuous reach/grasp/lift/place GT | command ≠ measured outcome |
| scripted oracle on same physics chain | 系统上界 / 物理可行性 |
| same seeds before/after relight | 视觉可见性混杂 |
| Current/Historical/Superseded/Invalid | benchmark history rewriting |

统计单位：episode；连续 frame 不视为 iid。S4 N=5，只报告有界结果和小样本限制。

---

## Page 3/5：Evidence Changed the Hypotheses

| Evidence | Hypothesis update |
|---|---|
| evaluator v0 command/state 混淆 | 旧结果 Invalid；先修测量链 |
| oracle v1 lift 0/5 | 暂停把失败归给 learned policy |
| oracle v2b lift 5/5 | 名义物理链排除；建立 upper bound |
| near-black policy input | dark first run 失去权威资格 |
| same-seed relight 仍 lift 0/5 | H1 下降，H2 相对增强 |
| interface 5/5、150/150 unclipped | H4 在当前范围基本排除 |
| MuJoCo seed1 early-stop | H2 方向支持，但不足以定因 |

科学信号：更差但更可信的 relight 结果被保留；0/5 没有被包装成“部分成功”。

---

## Page 4/5：RA-WP2 Result — Directional, Not Causal

### 36 train episodes vs 5 autonomous S4 episodes

- global mean W1 `0.7228`；energy distance `2.0554`；
- episode median energy `2.7953 [1.6511, 3.4008]`；
- 5/5 episode：last progress-bin energy > first；
- high-shift dimensions：joint1、EE x、joint5、EE z、gripper；
- 5/5 command/measured gripper 从未低于 `0.7`。

```yaml
status: completed_diagnostic
diagnostic_only: true
gate_eligible: false
claims_causal_proof: false
```

字段审计发现无可靠 phase、`gt_events.jsonl` 为空，因此只使用 normalized-progress proxy。结论是 `directional_support_not_causal_proof`，不能声称在哪个 phase 首先偏移或 shift 先于 failure。

---

## Page 5/5：What I Can Contribute as an RA

### 已证明的能力

- 把工程异常转成 falsifiable RQ 和 hypothesis matrix；
- 设计 prospective split、same-seed control 和 oracle upper bound；
- 分离 expert-state metric、interface validity 和 Task GT；
- 主动报告 Hold、Invalid、Superseded、early-stop 和 small-N；
- 建立 schema、SHA、测试、生成命令和 reproducibility statement。

### 下一研究步骤

1. 在 telemetry 中增加权威 Task phase 与 failure-onset timestamp；
2. 复做 phase-conditioned / failure-precedence analysis；
3. 再决定是否值得申请 paired MuJoCo 5-seed；
4. 不在零 lift 状态下盲目扩 seed 或重训。

**Takeaway**：我的优势是机器人学习实验设计、评测治理、负结果归因和系统复现；当前项目没有证明 task success、Sim2Real 或真实机器人能力。
