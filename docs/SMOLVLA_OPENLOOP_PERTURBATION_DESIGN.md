# SmolVLA Open-loop：Clean Canonical / K5 / 扰动分层设计

**状态**：设计冻结；**P1-0A/0B 已于 2026-07-25 人工批准并执行**（diagnostic only）  
**执行产物**：`runs/smolvla_s3/openloop_perturbation_20260725T045044Z/` · 结果摘要 [portfolio/OPENLOOP_PERTURBATION_RESULTS.md](portfolio/OPENLOOP_PERTURBATION_RESULTS.md)  
**性质**：评测协议 + 已跑诊断；**不是**新 Gate。  
**诚实边界**：**Not task success / Not Sim2Real / Not real robot**。扰动诊断即使退化率很大，也**不得**改写已冻结的 `eval_gate_v3` Pass，也**不得**声称闭环任务能力。

关联：
- Clean / Gate：[SMOLVLA_V3_EVAL_SOP.md](SMOLVLA_V3_EVAL_SOP.md) §3
- 路线登记：[FUTURE_WORK_ROADMAP.md](FUTURE_WORK_ROADMAP.md) P1-0
- 推理合同：`configs/smolvla_s3/recovery_decisions.yaml` → `local_inference_contract`

---

## 1. 一句话原则

> **每个观测只评第一步（H=1 / first action）**；  
> **clean 基线仍覆盖全部帧**；  
> **新扰动实验只抽阶段锚点与 close 窗口**；  
> **不要为了省算力把 clean canonical 改成只跑 5 步或 10 步**；  
> **不要再造一套 H=5 / H=10 open-loop 未来动作误差指标**。

---

## 2. 已冻结、保持不变的两套协议

### 2.1 Clean canonical（Gate 唯一权威）

| 项 | 冻结值 |
|---|---|
| 每次观测评测步数 | **只评 1 步**（`canonical_first_action`，H=1） |
| 每条 episode 覆盖 | **所有帧**（完整 episode） |
| 评测集 | **10 条 prospective episode**（seeds 70–74，eval-only，与训练 / 阈值设计零重叠） |
| stride | **1** |
| policy reset | **每一帧**独立 reset |
| 与 GT 比较 | 当前观测 `t` 上的 first action vs 有效 expert action at `t` |
| Gate 资格 | **唯一**具备 `eval_gate_v3` Pass / Hold 资格 |

**已完成证据**（不得改协议重跑冒充新 Pass）：  
`runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/`  
（10 ep / 2,593 帧；EE `0.0253 m`；grip BA `0.9943`；`gate_decision=pass`）

**明确禁止**：
- 为省算力把 clean 改成「每 ep 只评 5/10 步」或「抽帧当 canonical」；
- 用扰动实验数字改写或替代该 Pass。

### 2.2 Queued K5 diagnostic（保留，非 Gate）

| 项 | 冻结值 |
|---|---|
| chunk size | **10** |
| consume / `n_action_steps` | **5**（K5） |
| reset | **episode boundary**（非每帧） |
| 用途 | **queued diagnostic only** |
| Gate 资格 | **`queued_diagnostic_gate_eligible=false`** — 永不替代 canonical |

它回答的是「消费 action-chunk 队列时的离线诊断行为」，**不能**：
- 替代 clean canonical；
- 单独说明闭环任务能力（闭环任务能力看 S4 rollout）。

---

## 3. 为什么不做 H=5 / H=10 open-loop 预测误差

SmolVLA 会生成 action chunk，但在**同一个当前观测**下直接比较未来 5 或 10 个动作，有两个结构性问题：

1. **模型假设**：未来状态会按**模型自己的动作**演化；  
2. **GT 假设**：未来动作来自**专家状态**演化。

两条未来轨迹**不再处于完全相同的条件**。此时误差很难解释：
- 是模型未来动作差，还是模型设想的未来状态与专家未来状态不同？

因此本项目分工固定为：

| 问题 | 权威协议 |
|---|---|
| 专家态上当前动作是否拟合 | **canonical open-loop（first action, H=1）** |
| chunk 队列消费诊断 | **queued K5（已有）** |
| 真实未来 / 自主能力 | **S4 closed-loop rollout（已有 5-seed，不再扩展）** |

**禁止新增**「H=5 / H=10 open-loop multi-step prediction error」作为正式指标或 Gate 输入。

---

## 4. 新增：open-loop + 扰动（两层，登记不执行）

扰动**不建议**对全部 2,593 帧施加全条件扫描（周末工作量会重新膨胀）。采用两层抽样，且**每一层仍严格保持 first-action / H=1 / 扰动后 reset**。

### 4.1 第一层 — 快速扰动敏感性诊断

**目的**：得到阶段敏感性结论（哪一阶段对 nuisance / 轻度噪声最脆），不是新 Gate。

**阶段锚点（每条 episode 抽 6 个）**：

1. hover / approach  
2. descend 中段  
3. pre-close  
4. close transition  
5. early lift  
6. late lift  

**规模**：

| 量 | 计算 |
|---|---|
| 锚点数 | 6 × 10 episodes = **60** |
| 条件数 | clean + 轻度 + 中度 + 重度 = **4** |
| 独立推理次数 | 60 × 4 = **240** |

**单次协议（与 canonical 同语义）**：

```
perturb observation[t]  →  policy.reset()  →  first action  →  与有效 GT[t] 比较
```

**必须区分两类扰动**：

| 类型 | 定义 | 标签 / GT |
|---|---|---|
| **Nuisance perturbation** | 不改变正确动作（如 image brightness / blur / noise 在合理范围） | 继续用原 expert action at `t` |
| **State perturbation** | 会改变正确动作（如 EE / object 相关 state 噪声大到应改目标） | **必须由 scripted oracle 重新标注**目标动作；不得继续用原 GT |

未完成 oracle 重标的 state perturbation **不得**计入「相对 clean 的退化率」主表。

**建议报告字段**（实现时，非本轮交付）：
- 每阶段 × 每条件：EE error、quat error、grip 分类、是否错误闭爪、是否近静止 / 饱和；
- 相对 clean 的退化率（按阶段聚合）；
- `claims_task_success=false`；明确 `gate_eligible=false`。

### 4.2 第二层 — 闭爪时序专门窗口

**目的**：close timing 不能只靠单个锚点；专门看提前/延迟、debounce、漏 close。

**窗口定义（每条 episode）**：

- expert close 前 **10** 帧  
- close 帧本身 **1** 帧  
- close 后 **10** 帧  
→ **21 帧 / episode**；10 episodes → **210 帧**

**仍是**：每个观测 first action（H=1）+ 独立 reset；可叠加与第一层相同的扰动条件（实现时再定是否全条件或子集）。

**专门评测**：

- 是否提前或延迟闭爪；  
- 3 帧 debounce 是否成立；  
- 扰动后是否漏掉 close；  
- gripper 分类是否变化；  
- clip 是否改变 close timing（raw vs executed clip 分栏）。

**不得**用该窗口数字替代全帧 clean canonical Gate。

---

## 5. 周末推荐评测矩阵（最终建议）

| 部分 | 每次预测 | 评测范围 | Gate / 用途 | 现状 |
|---|---|---|---|---|
| **Clean canonical** | first action，H=1 | 10 条完整 episode、全帧、`stride=1`、每帧 reset | **唯一 Gate** | **已完成 Pass**；保持不变 |
| **扰动快速诊断** | first action，H=1 | 每条 6 个阶段锚点（共 60）× 4 条件 = 240 次 | 诊断 only | **已执行**（见上产物） |
| **Close 扰动诊断** | first action，H=1 | 每条 close 前后 21 帧 × 4 条件 = 840（实现选择：全条件可比） | 诊断 only | **已执行** |
| **Queue 诊断** | K5（chunk10 / consume5） | 现有 queued diagnostic 协议 | 诊断 only，无 Pass 资格 | **保留** |
| **自主能力** | K5 closed-loop | 已有 S4 有界 5-seed（权威 = relight） | 任务 funnel Hold | **已完成；不再扩展 seed** |

---

## 6. 明确不做

1. 把 clean canonical 缩成「只跑 5/10 步」以省算力；  
2. 对全部 2,593 帧做全条件扰动扫描作为默认方案；  
3. 新增 H=5 / H=10 open-loop multi-step 误差指标；  
4. 用扰动或 queued 结果改写 `eval_gate_v3` / 宣称任务成功；  
5. 因扰动诊断自动扩 Isaac seed、重训或采数；  
6. 把 nuisance 与必须 oracle 重标的 state perturbation 混在同一「退化率」主指标里。

---

## 7. 执行闸门

启动第一层或第二层实现 / 跑数前，必须同时满足：

1. 显式人工批准（本设计文档**不等于**批准）；  
2. 扰动表（nuisance vs state）与 oracle 重标规则写死；  
3. 输出目录与 clean Pass 报告**物理隔离**；  
4. 报告头写明 `gate_eligible=false`、`claims_task_success=false`；  
5. 不修改 `configs/smolvla_s3/eval_gate_v3.yaml` / lock / 历史 open-loop JSON。
