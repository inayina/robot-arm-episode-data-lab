# SmolVLA S3 Recovery gripper 输出范围 / clip / 归一化审计

**日期**：2026-07-23  
**状态**：本地 CPU saved-prediction audit Pass；`eval_gate_v1` 结论仍为 **Hold**；`eval_gate_v2` 已批准并冻结，evaluator v3 已实现；尚未做 prospective evaluation  
**范围**：Recovery v3 canonical first-action 与 K5 queued diagnostic；不训练、不推理、不运行 Isaac

## 1. 直接结论

1. checkpoint 的 action 归一化是 `MEAN_STD`；gripper mean/std 与
   `smolvla_s3_panda_abs_eef_scene_v3_phaseaware50` release 一致。
2. postprocessor 只做反归一化，不做物理范围 clamp；Panda absolute-EEF
   映射会把 `p[7]` clamp 到 `[0,1]`。
3. canonical 精确 OOB 为 `33.6068%`，但超出 `[0,1]` 边界超过 `0.05`
   的比例仅 `0.7032%`；clip MAE 为 `0.004358`，最大改变量
   `0.083454`。
4. K5 精确 OOB 为 `32.6985%`，超边界超过 `0.05` 的比例为
   `0.4981%`；clip MAE 为 `0.004078`，最大改变量 `0.094851`。
5. 两条 lane 的 clip 都没有改变开/关二分类，也没有改变 3 帧 debounce
   的首次关爪时序；保存的 `pred_gripper_cmd` 与 `clip(raw_pred[7])`
   最大误差为 `0`。

因此，v1 的“任何越界样本等价计数”能发现回归头不受界，但不能区分
`1.001` 与危险的大幅越界。当前证据支持提出一个同时保留精确 OOB、
再按越界幅度和行为不变量分级的独立 v2；它不支持把现有 v1 Hold
追溯改成 Pass。

## 2. 证据

| lane | raw range | 精确 OOB | 超界 >0.05 | clip MAE | clip max | 分类变化 | timing 变化 |
|---|---:|---:|---:|---:|---:|---:|---:|
| canonical first-action | `[-0.063720, 1.083454]` | `0.336068` | `0.007032` | `0.004358` | `0.083454` | `0` | `0 frames` |
| queued K5 diagnostic | `[-0.067052, 1.094851]` | `0.326985` | `0.004981` | `0.004078` | `0.094851` | `0` | `0 frames` |

归一化合同：

- action gripper 训练物理范围：`[0,1]`
- checkpoint gripper mean：`0.694409132`
- checkpoint gripper std：`0.453509390`
- 对应训练归一化范围：`[-1.531190, 0.673836]`
- canonical 预测对应归一化范围：`[-1.671694, 0.857855]`
- K5 预测对应归一化范围：`[-1.679041, 0.882985]`

机器可读证据：

- `training/scripts/audit_smolvla_s3_gripper_range_clip.py`
- `runs/smolvla_s3/gripper_range_clip_audit_20260723/gripper_range_clip_audit.json`
- `runs/smolvla_s3/gripper_range_clip_audit_20260723/gripper_range_clip_audit.md`
- `training/scripts/run_smolvla_s3_open_loop.py::_map_native8`
- Recovery checkpoint 的 `policy_preprocessor.json`、
  `policy_postprocessor.json` 与对应 safetensors state
- `data/releases/smolvla_s3_panda_abs_eef_scene_v3_phaseaware50/norm_stats.json`

## 3. 独立 `eval_gate_v2` 批准与冻结

历史提案保留在 `configs/smolvla_s3/eval_gate_v2_proposal.yaml`；批准后的
冻结门禁是 `configs/smolvla_s3/eval_gate_v2.yaml`，对应 lock 为
`configs/smolvla_s3/eval_gate_v2.lock.json`。

治理约束：

- 独立于 `configs/smolvla_s3/eval_gate.yaml`，并钉死 v1 SHA256；
- 状态为 `approved_frozen`，gate SHA256
  `31101fce204f6be6584635f52c6af4a88450412d39db0cf0bb60796d096daa0a`；
- 禁止覆盖 v1、禁止追溯改判 Recovery v3；
- K5 queued diagnostic 永远不能获得 canonical Pass；
- evaluator v3 已实现；Pass 必须提供 run-specific prospective manifest，
  且 gate/splits SHA 匹配、评测 refs 精确匹配、train/design overlap 均为 0；
- 历史 saved report 在 evaluator v3 下明确保持 Hold，唯一失败项为
  `prospective_eligibility`；
- 不授权 Isaac。

gripper 严重度冻结门槛：

| 指标 | frozen v2 |
|---|---:|
| 精确 raw OOB | 继续报告，不单独决定 Pass |
| OOB 超出边界的 epsilon | `0.05` |
| 超界 > epsilon 比例 | `≤0.01` |
| clip adjustment MAE | `≤0.01` |
| clip adjustment max | `≤0.10` |
| raw range | `[-0.10, 1.10]` |
| clip 后开/关分类变化 | `0` |
| clip 后首次关爪时序变化 | `0 frames` |
| mapped command | 必须有限、位于 `[0,1]` 且等于 clip(raw) |

非 gripper 指标沿用 v1 门槛并在 evaluator v3 中显式实现。由于这些阈值
是在查看 Recovery v3 后提出，Recovery v3 只能作为设计证据，不能作为
v2 的通过样本。评测 manifest 模板为
`configs/smolvla_s3/prospective_eval_manifest.template.yaml`。

### 3.1 为什么 prospective gate 仍用 canonical first-action

canonical 模式对每个 expert observation 清空 action queue，只评估新观测
产生的第一动作，因此每帧会触发一次 policy forward；这是离线隔离单步
策略误差的门禁协议，不是未来部署频率。

K5 queued diagnostic 一次 forward 产生 action chunk，后续 4 帧主要消费
缓存动作。Recovery K5 的 P50/P95 为约 `15/424 ms`，符合多数 cache hit、
周期性 full-forward 的结构；EE、gripper 和 timing 指标也接近或略优于
canonical。这支持在通过门禁后把 K5 用作 Isaac/runtime 初始执行配置。
但 K5 的第 2–5 个动作不会使用中间新观测重新规划，离线专家轨迹也没有
执行策略动作后的真实状态反馈，因此不能替代一次 canonical prospective
gate。K5 始终 `temporal_metrics_gate_eligible=false`。

## 4. 证据分级

### 已实现

- CPU saved-prediction 审计器、回归测试和审计产物。
- checkpoint/release mean/std 一致性核验。
- absolute-EEF 执行映射的 `[0,1]` clip 及保存结果一致性核验。
- 独立、批准冻结、不可追溯的 v2 gate 与 threshold lock。
- evaluator v3 severity 计算、Pass/Hold/No-Go、prospective manifest
  校验及 fail-closed shell 入口；canonical v2 缺失/无效 manifest 时不会
  启动 policy inference。
- evaluator v3 契约测试；历史 saved report 在 v2 下重新审计为 Hold。

### 文档声明，代码未确认

- 新的 prospective held-out 数据选择、run manifest 和 GPU evaluation
  尚未执行；当前没有 v2 Pass。

### 基于证据的推断

- 精确 OOB 主要由边界附近的小幅回归 overshoot 构成，而不是归一化统计
  配错；该判断由幅度分布和 mean/std 一致性支持。
- 严重度门禁比单一精确 OOB 比率更适合执行安全评估，但必须经未来独立
  prospective evaluation 才能验证。

### 通用背景知识

- 无界回归头即使训练标签有界，也可能在反归一化后略微超出标签范围；
  执行前 clamp 是安全措施，但不能代替任务级闭环评测。

## 5. 下一步

当前本地实现已收口，不需要重训。下一步是选择未参与阈值设计且与 train
零重叠的 held-out episode，复制并填写 prospective manifest；该 GPU
评测仍需单独批准。只有新的 canonical prospective evaluation 通过后，
才可另行申请 Isaac。
