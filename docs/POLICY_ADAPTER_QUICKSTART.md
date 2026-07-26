# Policy Adapter 一页速查

**范围**：中游离线契约与注册表；**不**改 Isaac/PyBullet 执行逻辑，**不**下载 VLA，**不**训练，**不**跑 E4。

## 1. 已注册策略（冻结身份）

| registry_id | 含义 | status |
|---|---|---|
| `scene_act_lerobot_e3_nominal` | E3 ACT diagnostic（sha256 `948e2949…`） | verified；task **0/20** |
| `isaac_scripted_oracle_v2b` | scripted oracle 物理对照 | verified；lift 5/5，不声称 task success |
| `moveit_rule_baseline` | 规则/MoveIt 基线占位 | documented_plan_only |

路径：`evaluation/registry/policies/` + `index.json`。

```python
from evaluation.policies import load_policy_metadata, load_registry_index

meta = load_policy_metadata("scene_act_lerobot_e3_nominal")
assert meta["claims_task_success"] is False
```

## 2. 薄接口

```python
from evaluation.policies import FixturePolicyAdapter, load_policy_metadata

identity = load_policy_metadata("scene_act_lerobot_e3_nominal")
adapter = FixturePolicyAdapter(identity)
adapter.load_policy(None)          # fixture：不读真实 checkpoint
adapter.reset({"seed": 3000, "suite_id": "baseline"})
obs = adapter.build_observation({"state": [0.0] * 8})
raw = adapter.predict_action(obs, instruction="pick up the red block")
action = adapter.export_action(adapter.validate_action(raw))
report = adapter.report_metadata()  # claims_task_success == False
adapter.close()
```

正式运行时包装应落在**上游**；本仓只提供 ABC + fixture。

### 2.1 上游薄挂载（已实现，不接 VLA）

上游包：`ros2-arm-teleoperation-suite` → `isaac_sim_adapter.policy_adapters`

| 类 | 包装 | 输出 |
|---|---|---|
| `SceneActPolicyAdapter` | `SceneACTRuntime` | `ee_delta_gripper[7]` + metadata（含 `deploy_n_action_steps`） |
| `ScriptedOraclePolicyAdapter` | `scripted_oracle` 目标/相位 | 有界 EE delta + gripper；**不**声称 task success |

身份卡仍读本仓 registry JSON（例如 `evaluation/registry/policies/scene_act_lerobot_e3_nominal.json`）。  
**不改** E3/E3.5/E3.6 权威数字。

## 3. Absolute-EEF fixture 导出（Gate V2 前置，已实现）

```bash
python3 training/scripts/export_absolute_eef_fixture.py \
  --input-jsonl evaluation/examples/absolute_eef_upstream_rows_fixture.jsonl \
  --output-jsonl /tmp/absolute_eef.jsonl

# 真实上游 episode（action[8]）
python3 training/scripts/export_absolute_eef_fixture.py \
  --input-parquet /path/to/episode_000000.parquet \
  --prefer-cmd-neq-measured --max-frames 5 \
  --output-jsonl evaluation/examples/absolute_eef_from_episode52_sample.jsonl
```

- 语义：`absolute_eef_gripper_v0`（**拒绝** `ee_delta_gripper[7]`）
- 库：`evaluation/vla_contract/absolute_eef.py`
- 测试：`tests/test_absolute_eef_export.py`、`tests/test_absolute_eef_episode_and_home_diag.py`

## 4. Benchmark 三切片（spec only）

Schema：`evaluation/schemas/benchmark_spec.schema.json`  
Fixture：`evaluation/examples/benchmark_spec_baseline_id_ood_fixture.json`

- `baseline`：`enabled=true`（链路冒烟）
- `id` / `ood_position`：`enabled=false`，直到 `hard_gate.current_learned_policy_lift_verified`

## 5. 测试

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q \
  tests/test_evaluation_contract.py \
  tests/test_policy_adapter.py \
  tests/test_absolute_eef_export.py \
  tests/test_absolute_eef_episode_and_home_diag.py
```

## 6. 禁止

改写 evidence/checkpoint；把 interface PASS 写成 task success；跳过 Gate 接 VLA/Isaac；
启用 OOD 大规模矩阵；本机 6GB 上启动 SmolVLA LoRA；自动恢复 LingBot Gate V1 / 下载 LingBot 6B；
因 SmolVLA S2 接口 Pass、S3 Ready 或 open-loop Pass 自动进入正式训练 / S4；
把有界 S4 的 `ran_isaac=true` / interface 5/5 / reach-grasp 计数写成任务成功、在线自主抓取或 Sim2Real；
因 S4 lift 0/5 自动扩种子、重训或再跑 Isaac。

## 7. SmolVLA（当前活动候选：S3 open-loop Pass / 有界 S4 Hold）

- S0–S2：[`SMOLVLA_GATE_S2_OPEN_LOOP.md`](SMOLVLA_GATE_S2_OPEN_LOOP.md)（接口 Pass；base zero-shot absolute-EEF open-loop No-Go）。
- S3 v1（历史）：[`SMOLVLA_GATE_S3_READY.md`](SMOLVLA_GATE_S3_READY.md) — **Historical / Superseded**，其「不得进 Isaac」为当时状态。
- **Recovery v3（当前）**：5,705-step LoRA + 独立 prospective 全帧 open-loop 在冻结 `eval_gate_v3` 下 **Pass**（EE `0.0253 m`、grip BA `0.9943`）；见 [`portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md`](portfolio/SMOLVLA_RECOVERY_V3_PORTFOLIO.md)。
- **有界 Isaac S4（已跑）**：人工批准 seeds 1–5，`ran_isaac=true`；interface 5/5、lift **0/5** → **Hold**；不扩种子、不重训、不声称任务成功。
- 后续任何训练 / 扩种子 / 再跑 Isaac 须**另行人工批准**；路线见 [`FUTURE_WORK_ROADMAP.md`](FUTURE_WORK_ROADMAP.md)。
- LingBot 执行路线：**Closed / Archived**（[`VLA_GATE_V0_COMPATIBILITY_AUDIT.md`](VLA_GATE_V0_COMPATIBILITY_AUDIT.md)）；V0.5 absolute EEF 契约为**模型无关**保留。

详情：[`POLICY_ADAPTER_CONTRACT.md`](POLICY_ADAPTER_CONTRACT.md) · [`THREE_REPO_CANONICAL_FACTS.md`](portfolio/THREE_REPO_CANONICAL_FACTS.md)
