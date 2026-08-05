# Negative Results and Threats to Validity

**版本**：v1.0  
**目的**：把 Hold、Invalid、Superseded 和 early-stop 转化为研究信息，而不是从主叙事中删除。  
**边界**：负结果不证明策略在所有条件下必然失败，也不证明任务成功（Not task success）、Sim2Real 或真机。

返回：[RA 科研助理文档包](README.md)

---

## 1. 关键负结果

### N1：ACT E3 nominal20 为 0/20

连续 Task GT 下 place 0/20，Wilson 95% CI 约 `[0.000, 0.161]`。它触发了止损：ACT 冻结为 diagnostic baseline，完整 E4 100+ rollout 不再执行。研究价值是识别 floor effect——在 baseline 尚无 lift/place 时扩 OOD 矩阵不会提供有效泛化比较。

### N2：SmolVLA Recovery v3 offline Pass，但 S4 lift 0/5

0/5 的 Wilson 95% 上界仍约 `0.434`，因此不能外推“总体成功率为 0”；但在冻结的 bounded protocol 中已足以触发 Hold 和禁止自动扩 seeds。它建立了主要研究问题，而不是一个可隐藏的失败。

### N3：scripted oracle v1 也 lift 0/5

该结果一度反驳“learned policy 是唯一失败源”。修正物理链后 oracle v2b lift 5/5；5/5 的 Wilson 95% 下界约 `0.566`，同样不能外推为普遍 100% 成功。其作用是证明名义链存在可行上界，不是证明 learned policy 成功。

### N4：修光后指标比近黑首轮更差

首轮 near-black 的 reach 3/5、grasp 1/5 被同 seeds relight 复测改为 reach 1/5、grasp/lift 0/5。更差的结果更可信：首轮几何重叠和宽松夹爪阈值造成虚高，已标记 Superseded。

### N5：MuJoCo 对照人工提前停止

当前只有 seed1 完整 GT，suite `early_stopped=true`、`seeds_completed=1`。它方向性支持“并非只在 Isaac 视觉域失败”，但不能构成 paired 5-seed 域对照，也不能证明 covariate shift 是唯一根因。

## 2. Threats to Internal Validity

| Threat | 风险 | 当前控制 | 仍未解决 |
|---|---|---|---|
| evaluator semantics | command 被误作 measured state | v0 结果隔离，continuous GT preflight | 真实硬件传感器未验证 |
| split contamination | 训练见过所谓 held-out episode | Recovery train-only + prospective eval 重采 | 预训练基础模型的数据不可完全审计 |
| phase labeling | 结果后人工调 phase 可产生偏差 | 字段审计后冻结 Amendment A，只报 normalized-progress proxy | 真实 phase / failure-onset 仍不可用 |
| correlated frames | 把连续帧当 iid 会缩窄区间 | 已实现 episode-level median bootstrap | closed-loop 仍只有 5 episodes，区间较宽 |
| action timing | sync miss 可能混入 behavior failure | queue bench 分栏 | online async 未接线 |
| fixture/mock evidence | 合同通过可能被误当物理执行 | artifact 明确标注 mock/fixture | 真实策略 cutover 未验证 |

## 3. Threats to Construct Validity

- EE RMSE 和 gripper BA 只度量 expert-state first action，不是 autonomous recovery；
- interface 5/5 只证明命令链工作，不证明物体被抓起；
- reach/grasp 阈值可能受几何重叠和 gripper threshold 影响，lift 是更严格的物理结果；
- risk/system health 与 Task GT 正交，不能用安全链健康覆盖任务失败；
- state-space distance 是分布代理，不天然等于 causality 或 control relevance。

## 4. Threats to External Validity

- 单一 Panda、本体、单红块、固定任务和有限初始条件；
- Isaac S4 只有 5 seeds；
- 无真实机器人、无 Sim2Real；
- Recovery v3 是一个 checkpoint，不能代表所有 VLA/BC；
- oracle 上界依赖当前物理参数和 task definition；
- 当前结论不能外推到双臂、长时任务或多物体场景。

## 5. Threats to Reproducibility

- GPU/driver/EGL 和 LeRobot/PEFT 版本会影响真实模型路径；
- 大型 checkpoint 和部分运行环境不在最小公开包；
- generated evidence 可能包含本地绝对路径；
- Historical/Superseded 产物必须保留状态标签，否则复现者可能选错权威 run；
- 完整闭环重跑需要人工批准，默认复现仅覆盖 CPU 合同和冻结证据核验。

## 6. 报告规则

每个结果必须同时写：协议、N、有效/缺失 episode、status、effect/CI、evidence path、可证明和不可证明。禁止用“趋势明显”“部分成功”替代原始 0/5、1/5 或 early-stop 状态。
