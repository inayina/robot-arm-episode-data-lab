# Policy Onboarding Guide

**版本**：v0.2  
**状态**：Documentation + templates + CPU validator + four frozen fixtures complete  
**目的**：让一个新策略在进入训练评测、replay 或 runtime 前声明完整身份和语义。  
**边界**：Onboarding Pass 只代表合同可进入下一层，不代表模型精度、闭环任务成功或生产可用。

返回：[解决方案架构文档包](README.md)

---

## 1. Onboarding 包

```text
policy_onboarding/
├── policy_identity.yaml
├── observation_schema.yaml
├── action_schema.yaml
├── runtime_contract.yaml
├── artifact_manifest.json
├── adapter_mapping.yaml
└── preflight_report.json       # validator 输出，不由提交方预填 Pass
```

模板位于 [templates/](templates/)。`preflight_report.json` 必须由 validator 生成；客户不得直接提交一个自称 `PASS` 的报告作为证据。

---

## 2. 预检顺序

| Gate | 检查 | 失败状态 |
|---|---|---|
| G0 Identity | policy/version/artifact/release/benchmark 身份完整 | invalid |
| G1 Integrity | artifact 路径、SHA256、license、依赖 lock | invalid |
| G2 Observation | key/order/shape/dtype/unit/norm/camera | invalid |
| G3 Action | schema/version/dim/channel/frame/unit/gripper | invalid |
| G4 Runtime | chunk/K/rate/timeout/TTL/reset/workspace | Hold / invalid |
| G5 Adapter | source→execution mapping 具名且版本化 | invalid |
| G6 Claims | task/Sim2Real/autonomous claims 恒 false | invalid |
| G7 Evidence | provenance、owner、next gate 完整 | Hold / invalid |

必须按顺序执行，不能因后端“似乎能跑”跳过前面的语义检查。

---

## 3. Policy Identity

最小字段：

- `contract_version: solution_policy_onboarding_v1`；
- `policy_name`、`policy_version`、`policy_family`；
- `artifact_kind`、`artifact_path`、`checkpoint_sha256`；
- `dataset_release_id`、可用时的 `release_content_sha256`；
- `benchmark_version`；
- `observation_schema_version`、`action_schema_version`；
- `runtime_contract_version`；
- `owner`、`license`、`created_at`；
- 所有 `claims_*: false`。

mock/oracle 可以使用有文档定义的 sentinel；真实 checkpoint 必须使用 64 位小写 SHA256。

---

## 4. Observation Contract

每个 feature 必须声明：

| 字段 | 示例 |
|---|---|
| key | `observation.state` |
| shape | `[15]` |
| dtype | `float32` |
| order | `joint[7] + ee_pose_xyzw[7] + gripper[1]` |
| unit/range | rad、m、unit quaternion、[0,1] |
| normalization | checkpoint-bound stats / none |
| required | true/false |
| privileged | true/false |

相机需额外声明 key、shape、color space、frame rate、timestamp 和 missing-feature 语义。`object_pose` 如为 privileged，不得进入 policy input。

---

## 5. Action Contract

当前 Panda 主线支持两种明确语义：

| Schema | Dim | 语义 | 用途 |
|---|---:|---|---|
| `panda_absolute_eef_gripper_v0` | 8 | xyz + quat xyzw + gripper | VLA/在线执行主语义 |
| `panda_ee_delta_gripper_v0` | 7 | delta xyz + delta rpy + gripper | ACT / replay compatibility |

Action schema 必须声明 channel order、reference frame、unit、range 和 postprocessing。55-D 或其它通道切片在没有官方 Panda config 证据时必须 `invalid`，不能推测映射。

---

## 6. Runtime Contract

最小字段：

- policy rate、control rate；
- `chunk_size`、`execute_k`、`replan_period_s`；
- reset boundary；
- inference timeout / command TTL；
- workspace、gripper 和 joint limits；
- queue mode（sync / offline async evidence / online async）；
- Hold / E-stop reason mapping；
- expected execution adapter。

Recovery v3 的历史证据是 chunk10/K5/10 Hz；该值不是所有客户策略的默认值，必须由 policy identity 和 runtime contract 共同声明。

---

## 7. Adapter Mapping

每个转换必须记录：

```yaml
adapter_name: ""
adapter_version: ""
source_action_schema_version: ""
execution_action_schema_version: ""
required_state_keys: []
transformations: []
limits: {}
lossless: false
online_authorized: false
```

offline absolute→delta handoff 不能自动证明在线转换等价；`mock_ik` 也不能冒充真实 Panda IK backend。

---

## 8. Artifact Manifest

每个文件至少记录：relative path、SHA256、size、artifact role、required/optional。禁止：

- 使用未解析的网络 latest tag；
- 只记录目录名、不记录文件 hash；
- 在运行后静默替换 checkpoint/norm/schema；
- 把 secret/token 写入 manifest。

依赖版本应有 lock 或 audit report，GPU/driver/CUDA/PEFT 等关键版本不匹配时默认 Hold。

---

## 9. Preflight Report

报告必须包含：

- bundle identity 与 source path；
- 每个 Gate 的 `pass | hold | invalid | not_run`；
- errors、warnings、evidence；
- verified hash 列表；
- cross-field checks；
- next allowed stage；
- claims 和 non-claims。

Pass 只允许进入 Offline/Interface 下一层；若没有 Task GT，`next_allowed_stage` 不得写 task-success evaluation。

---

## 10. 必备错误 fixtures

| Fixture | 变更 | 期望 |
|---|---|---|
| valid_bundle | 所有身份、dim、hash、runtime 一致 | PASS to next layer |
| invalid_action_dim | schema 写 dim=8，sample/action 只有 7 | `action_dimension_invalid` |
| invalid_hash | manifest hash 与 artifact bytes 不一致 | `contract_mismatch` / invalid |
| invalid_sequence | command sequence 回退 | `command_sequence_regression` / Hold |

上述四个 fixture 已在 `evaluation/examples/policy_onboarding_fixture/` 固化。它们使用一份合法基准包和显式内存内 mutation；不修改基准文件，也不加载真实模型。

一键运行四个案例：

```bash
python3 scripts/run_policy_onboarding_poc.py \
  --output-dir /tmp/policy_onboarding_poc
```

单独验证一个包或 fixture：

```bash
python3 scripts/validate_policy_onboarding.py \
  --bundle evaluation/examples/policy_onboarding_fixture/base \
  --case evaluation/examples/policy_onboarding_fixture/cases/invalid_action_dim.json \
  --output /tmp/invalid_action_dim.preflight_report.json
```

单包 CLI 退出码为 `0=pass`、`2=hold`、`3=invalid`、`4=could not run`。PoC 聚合命令在四个实际结果均匹配预期时退出 `0`；这不代表四个包都通过，而是代表负向错误被正确拦截。

---

## 11. Onboarding Exit Criteria

- identity、artifact、observation、action、runtime 和 adapter 全部可追溯；
- 真实 artifact hash 已验证；
- action/observation 语义不依赖猜测；
- claims 全部保持 false；
- 有明确 `next_allowed_stage`；
- 任何 Hold/invalid 都有 owner 和 remediation；
- 未经批准的 GPU、simulation、authoritative 或 hardware 阶段保持禁止。
