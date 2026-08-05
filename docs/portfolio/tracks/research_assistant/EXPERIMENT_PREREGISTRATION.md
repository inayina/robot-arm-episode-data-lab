# Experiment Preregistration：闭环状态分布偏移诊断

**注册版本**：closed_loop_shift_prereg_v1  
**状态**：Executed on existing evidence / Amendment A applied before metric computation  
**执行授权**：用户已于 2026-07-30 明确批准 RA-WP2；没有授权新仿真、训练或采集  
**研究性质**：diagnostic only / gate ineligible  
**边界**：**Not causal proof / Not task success / Not Sim2Real / Not real robot**。

返回：[RA 科研助理文档包](README.md)

结果：[CLOSED_LOOP_SHIFT_RESULTS.md](CLOSED_LOOP_SHIFT_RESULTS.md)；权威报告：`evidence/closed_loop_shift_v1/report.json`。

---

## 1. 研究问题

**Primary**：自主闭环 `state[15]` 与训练专家状态之间的距离是否在行为失败前按时间或 phase 累积？

**Secondary**：偏移主要集中在哪些 state 维度与任务阶段？它与 Z 下降、gripper close、near-static 和 failure lane 的时间关系是什么？

## 2. 冻结假设

- **H2-primary**：至少一个失败前 phase 的 rollout-vs-train distance 高于早期 hover，并在多数完整 episode 中同向变化；
- **H2-null**：距离没有一致的阶段/时间趋势，或变化只出现在失败之后；
- **H5-alternative**：deadline/queue 指标比 state distance 更早、更稳定地预测行为退化；
- **H1-alternative**：偏移主要由 scene appearance 而非 `state[15]` 体现，本分析无法排除。

## 3. 冻结输入

| 输入 | 用途 | 资格 |
|---|---|---|
| Recovery v3 train-only 36 episodes | expert-state reference | current / train only |
| prospective eval-only 10 episodes | expert held-out descriptive reference | current；不进入 train reference 主统计 |
| authoritative relight S4 seeds 1–5 telemetry | autonomous rollout | current / bounded Hold |
| MuJoCo seed1 | sensitivity appendix | `early_stopped=true`，不进入主结论 |

必须从 [research_identity.yaml](research_identity.yaml) 读取 release、checkpoint、gate 和 evidence identity。若任一身份或 state ordering 无法验证，分析停止并标记 Invalid。

## 4. 排除规则

分析前冻结，不按结果修改：

- 仅排除无法解析、缺少完整 identity 或 state 维度不等于 15 的记录；
- episode 若缺关键 phase/GT，可保留描述统计，但不得进入对应 phase bootstrap；
- 不因距离大、策略失败或图形“不好看”删除 episode；
- `object_pose`、Task GT 和 phase 标签可用于诊断对齐，不得混入 policy-state distance；
- dark-scene first S4 只作 Historical/Superseded 对照，不进入主统计。

## 5. 指标与估计量

### Primary metrics

1. 每个 state 维度的 Wasserstein-1 distance；
2. 使用冻结训练统计的 standardized mean difference；
3. 一个预先选定的 multivariate distance：优先 energy distance；若实现改用 MMD，必须在看结果前记录 kernel/bandwidth；
4. distance-vs-time 和 phase-conditioned distance；
5. 与 `z_descent`、gripper close、near-static onset 的 episode 内时间差。

### Uncertainty

- bootstrap 单位必须是 episode，不是 frame；
- 默认 2,000 次 episode bootstrap，固定 RNG seed `20260730`；
- 报告 effect size、median 和 percentile 95% interval；
- N=5 只做有界描述，不以窄 CI 暗示总体泛化。

### Multiple comparisons

15 个 per-dimension 指标用于诊断，主结论依赖预注册 phase/global aggregate；per-dimension p-value 不作为 Gate，也不做选择性 headline。

## 6. Phase 定义

优先使用已记录 FSM/Task phase；若需从 trace 映射，规则必须在分析脚本中版本化：`hover → approach → descend → pre_close → close → lift`。无法唯一映射的帧标记 `unknown`，不按结果人工改 phase。

### Amendment A（2026-07-30，metric 计算前的数据审计）

实际输入审计发现：train state15 parquet 和 S4 `observations.jsonl` 均没有可靠 phase 字段，权威 relight S4 的 `gt_events.jsonl` 为空，observation 行也没有可用于 failure-onset 对齐的事件时间戳。因此：

- 原计划的真实 phase-conditioned 主分析标记 `unavailable`，不从轨迹外观事后手工贴标签；
- 增加六等分 normalized episode-progress bins，规则为 `floor(frame_index * 6 / episode_length)`；
- progress bins 只回答“shift 是否随相对运行进度变化”，不能命名为 hover/close/lift；
- failure-onset precedence 不可检验；
- H2 最多得到 `directional_support_from_progress_proxy_not_causal_proof`。

该修订由字段缺失触发，在任何 distance metric 计算前确定；没有修改指标、normalization、bootstrap 单位或 claims。

## 7. 支持/反驳判据

H2 可标记 `supported_directionally` 仅当：

- 主 aggregate distance 在失败前上升；
- 趋势在多数完整 S4 episode 同向；
- 至少一个行为退化事件发生在距离上升之后；
- 结论对是否包含 MuJoCo early-stop appendix 不敏感。

否则标记 `not_supported` 或 `inconclusive`。任何结果都必须保持：

```yaml
diagnostic_only: true
gate_eligible: false
claims_causal_proof: false
claims_task_success: false
claims_sim2real: false
```

## 8. 停止条件

- provenance、state normalization 或 timestamp alignment 不可确认；
- 有效完整 episode 少于 3；
- phase mapping 需要观察结果后人工调节；
- 运行需要新 Isaac、GPU、训练或数据采集；
- 分析代码没有合成数据单测和 report schema。

## 9. 实际产物

```text
evaluation/closed_loop_shift.py
training/scripts/analyze_closed_loop_shift.py
evaluation/schemas/closed_loop_shift_report.schema.json
tests/test_closed_loop_shift.py
evidence/closed_loop_shift_v1/report.json
docs/portfolio/tracks/research_assistant/CLOSED_LOOP_SHIFT_RESULTS.md
```

上述产物已实现。原预注册的真实 phase-conditioned/failure-onset 分析因字段缺失未完成；实际完成的是 Amendment A 定义的 normalized-progress proxy 分析。
