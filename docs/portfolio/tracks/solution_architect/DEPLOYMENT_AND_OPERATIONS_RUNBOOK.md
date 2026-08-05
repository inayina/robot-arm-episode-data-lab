# Deployment and Operations Runbook

**版本**：v0.1  
**状态**：Documentation complete；reference PoC drill pending  
**用途**：规定解决方案 PoC 的环境预检、启停、证据目录、故障处理、清理、回滚和移交。  
**边界**：默认只授权 CPU/offline/mock/replay；运行健康或接口通过不等于任务成功（Not task success）；GPU、ROS live、Isaac、训练和真实硬件需单独批准。

返回：[解决方案架构文档包](README.md)

---

## 1. Deployment Profiles

| Profile | 默认授权 | 主要命令 | 退出责任 |
|---|---|---|---|
| A Local CPU | 是 | pytest、schema、report、docs | 删除/保留 `/tmp` evidence 按约定 |
| B Lab GPU | 否 | checkpoint forward、offline eval | 记录 GPU/依赖/计费，停止 worker |
| C Simulation | 否 | bounded MuJoCo/Isaac/ROS | timeout + Nuke On Done |
| D Robot Edge | 否 | Hardware Pending | 现场安全 SOP + 双人验收 |

---

## 2. 环境预检

每次 PoC 创建独立 run directory，禁止覆盖历史证据：

```bash
POC_RUN_ROOT="$(mktemp -d /tmp/solution_poc.XXXXXX)"
```

记录：

- 三仓 commit 与 dirty status；
- Python/ROS/CUDA/driver/关键依赖版本；
- contract/schema/gate SHA；
- CPU/GPU/内存/磁盘；
- hostname、timezone、run owner；
- 授权范围和禁止项。

有未提交变更时可以继续只读 PoC，但必须在 report 中记录，不能把 dirty tree 冒充冻结 release。

---

## 3. Local CPU 启动顺序

```bash
cd /home/ina/robot-sim-lab/robot-arm-episode-data-lab
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_policy_runtime_contract.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_policy_trace_bundle_contract.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_unified_eval_report.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_portfolio_docs_consistency.py
```

统一报告可使用冻结证据重出到新目录；不得修改源 JSON：

```bash
python3 training/scripts/normalize_unified_eval_report.py \
  --open-loop runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z/s3_open_loop_summary.json \
  --policy-runner evidence/downstream/smolvla_v3_ep0_benchmark_summary.json \
  --isaac-s4 evidence/smolvla_s4_bounded5_relight_20260724T151711Z/s4_gate.json \
  --risk-readiness evidence/downstream/smolvla_v3_ep0_risk_offline_20260724T215900Z.json \
  --out-dir "$POC_RUN_ROOT/unified" \
  --bundle-out "$POC_RUN_ROOT/unified/bundle.json" \
  --bundle-id solution_poc_reference
```

---

## 4. ROS / Simulation 生命周期

只有获得批准后才允许启动。所有常驻命令必须使用 `timeout` 或节点自退出参数：

```bash
timeout 60s ros2 launch <package> <launch_file> <bounded_parameters>
```

结束前必须执行：

```bash
pkill -9 -f "teleop_bringup" || true
pkill -9 -f "mujoco_sim" || true
pkill -9 -f "lerobot_recorder" || true
pkill -9 -f "servo_node" || true
pkill -9 -f "ros2_control" || true
```

不得把清理推给客户或下一轮演示。清理后应检查没有本轮拉起的相关进程。

---

## 5. Evidence Directory

```text
solution_poc_<run_id>/
├── scope/
├── environment/
├── onboarding/
├── tests/
├── unified/
├── traces/
├── screenshots/
├── issue_register.yaml
├── acceptance_report.yaml
└── README.md
```

每个 artifact 记录 `producer`、`source_path`、`sha256`、`created_at`、`contract_version` 和 `claims`。截图不能替代 JSON/trace。

---

## 6. 健康检查

| 检查 | 正常 | 异常动作 |
|---|---|---|
| contract/schema | validator Pass | stop / invalid |
| source identity | commit/hash 完整 | Hold |
| disk/memory | 预算内 | stop before corruption |
| policy/runtime | identity/rate/chunk 一致 | Hold |
| DDS/QoS | endpoint matched | investigate，不改 Task GT |
| command trace | sequence/parent/TTL 正常 | Hold/reject |
| Task GT | complete or explicitly unavailable | downgrade report |
| cleanup | no owned processes left | Nuke On Done |

---

## 7. Incident 与 Escalation

| Severity | 示例 | 默认动作 | 升级给谁 |
|---|---|---|---|
| P0 | E-stop 无效、未知命令执行、数据/结论被覆盖 | immediate stop / No-Go | Safety + Executive owner |
| P1 | hash mismatch、GT 缺失、sequence regression、测试器错误 | Hold / invalidate run | Technical + QA owner |
| P2 | 文档、非关键图表、可绕开的性能问题 | record / plan fix | Module owner |

Issue register 必须记录触发条件、证据、影响层、临时措施、root cause 状态、owner 和 due date。

---

## 8. Rollback

1. 停止当前进程并执行 cleanup；
2. 保留失败 evidence，不覆盖；
3. 恢复到冻结 artifact/contract hash；
4. 重新运行 CPU contract tests；
5. 新建 run ID，不复用失败目录；
6. 只有原失败被证明消除后才恢复下一阶段。

禁止用 `git reset --hard`、删除历史 JSON 或静默改 Gate 做“回滚”。

---

## 9. Handoff

移交包必须包含：

- scope 和 RACI；
- environment/contract/artifact identity；
- acceptance matrix；
- issue register 和 residual risks；
- exact reproduce commands；
- rollback/cleanup；
- next allowed/prohibited stage；
- claims/non-claims。

真实机器人阶段必须另附现场安全、标定、网络、硬件急停和操作员验收，不得复用仿真签字。
