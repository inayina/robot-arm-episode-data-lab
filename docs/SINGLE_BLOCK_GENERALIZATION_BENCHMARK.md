# 单方块受控泛化 Benchmark 规范

**版本**：`single_block_controlled_v0`（2026-07-21）  
**状态**：规范与 YAML **已冻结**；**不执行**完整 E4 / OOD 大规模矩阵。  
**唯一任务**：根据语言指令抓取指定方块，并放入固定目标区域。  
**禁止**：新增抽屉、叠放、双臂、柔性物体等任务类型。

机器可读配置：[`../configs/benchmarks/single_block_controlled_v0.yaml`](../configs/benchmarks/single_block_controlled_v0.yaml)

关联：[`EVALUATION_CONTRACT.md`](EVALUATION_CONTRACT.md)、[`POLICY_ADAPTER_CONTRACT.md`](POLICY_ADAPTER_CONTRACT.md)、[`EMBODIED_POLICY_EVALUATION_SOP.md`](EMBODIED_POLICY_EVALUATION_SOP.md)。

---

## 1. 硬门禁

在 **learned policy** 出现至少一次由上游 continuous GT 确认的稳定 **lift** 之前：

- 允许：Baseline 链路冒烟、oracle 对照、只读诊断；
- **禁止**：运行 OOD-position / OOD-appearance / OOD-composition 大规模矩阵；
- **禁止**：把 Baseline interface PASS 写成泛化成功。

当前 ACT：E3 overall 0/20；E3.6 lift 0/5 → 门禁 **未满足**。

---

## 2. 受控变量（因子，非新任务）

| 因子 | 说明 |
|---|---|
| block_position_xy | 桌面平面位置 |
| block_yaw | 绕 Z 朝向 |
| block_color | 外观颜色 |
| block_size | 边长尺度 |
| lighting | 光照强度/色温 |
| camera_offset | 相机外参微偏 |
| distractor | 有无干扰物 |
| language_paraphrase | 同任务不同自然语言 |

---

## 3. 切片定义

| 切片 ID | 训练集 | Validation | Benchmark 独占 | 建议 seeds | 最少 rollout | Go/No-Go（learned） |
|---|---|---|---|---|---|---|
| `baseline` | 可含同源演示 | 可含 | 否（链路冒烟） | 固定场景 × 3 | 3 | Interface+System PASS；oracle 可 lift；learned 至少 1 次 grasp/lift 信号才谈扩展 |
| `id` | 同分布新 episode | 是 | 否 | 10–20 | 10 | 至少 lift≥1 或达 place 阈值；否则 No-Go 扩矩阵 |
| `ood_position` | 否（未见 pos/yaw） | 否 | 是 | 20 | 20 | 仅 ID 稳定 lift 后 |
| `ood_appearance` | 否（未见色/尺寸/光） | 否 | 是 | 20 | 20 | 仅 ID 稳定 lift 后 |
| `ood_composition` | 属性见过、组合未见 | 否 | 是 | 20 | 20 | 仅 ID 稳定 lift 后 |
| `system_fault` | 否作为成功训练 | 可选注入 | 是 | 每故障类 ≥5 | 5+/类 | 期望 fail_safe 正确终态，**非** task success |

与现有 `episode_result.suite_id` 枚举（`nominal` / `object_pose` / `visual` / `camera` / `dynamics`）的映射：

| 本规范切片 | 建议写入的 `suite_id`（未来执行时） |
|---|---|
| baseline / id | `nominal` |
| ood_position | `object_pose` |
| ood_appearance | `visual` |
| camera_offset 因子主导 | `camera` |
| system_fault / 动力学扰动 | `dynamics` |

切片身份仍以本 YAML 的 `slice_id` 为准；避免 train/val/bench 泄漏靠 `split_role` 字段（train|validation|benchmark）。

---

## 4. 泄漏规则

1. `split_role=benchmark` 的因子组合不得出现在 train release 的场景身份中。
2. OOD 切片的未见因子值必须在 suite manifest 中显式列出 `held_out_values`。
3. 自然语言 paraphrase：train 可用固定模板；benchmark 独占 paraphrase 列表不得用于训练采样。
4. 中游 `filter_scope=training_split_only` 不替代本 Benchmark 泄漏检查。

---

## 5. 指标与报告

每切片分栏：Data / Offline / Interface / Behavior / Task / System。  
Task 仅 continuous GT。Interface PASS ≠ Task PASS。

---

## 6. 验收（本规范轮）

- [x] 切片表、泄漏规则、硬门禁成文 + YAML
- [x] 明确不跑完整 E4
- [ ] 实际 rollout（blocked）
