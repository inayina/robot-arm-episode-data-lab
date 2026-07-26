# Policy Runtime M6 Wiring Smoke Results

**日期**：2026-07-26  
**结果**：PASS  
**合同**：`panda_policy_runtime_v1`  
**证据边界**：真实 ROS 2/DDS wiring + mock PolicyBackend；未启动 PyBullet/Isaac、未加载模型、未训练、未切换 SmolVLA authoritative executor。

## 1. 运行拓扑

当前四泳道前端截图：下游 `ros2-moveit-pybullet-bridge/docs/assets/hoc-runtime-four-lane-dashboard.png`。
该图片来自确定性的 Playwright frontend fixture，参考诊断 DAG 与 state timeline，展示最终裁决、
原因链、四泳道 RUN→E_STOP→HOLD 历史和连续诊断。一级 Runtime Overview 已用浏览器测试固定为
1920×1080 无页面纵向滚动；Diagnostics / Historical 作为下钻层。它不冒充本次 live wiring 截图。
真实 wiring 结论仍以本报告和 `evidence_manifest.json` 为准。

三个独立 ROS 2 进程在 55 秒硬 timeout 内运行：

```text
M6 mock Policy Runtime
  ├─ /policy/command + /policy/runtime_health
  ├─ /policy/execution_report + /task/evaluation_status
  └─ /risk/status
       ↓
RiskToSafetyBridge (dry_run=false)
  ├─ R2 → /policy/runtime_hold=true
  └─ R3 → /safety/trigger_estop
       ↓
HOC → JSON report + panda_policy_trace_bundle_v1
```

复现入口：下游 `scripts/run_policy_runtime_m6_wiring_smoke.sh <evidence_dir>`。

## 2. 验收结果

| 项目 | 结果 | 直接证据 |
|---|---:|---|
| topic discovery | PASS | command 1、health 1、execution 2、risk 2、task GT 1 个订阅者 |
| command QoS | PASS | Reliable / Volatile / Manual-by-topic；deadline 150 ms、lifespan 250 ms、liveliness lease 200 ms |
| contract identity | PASS | descriptor SHA `e78176…e8e2` 贯穿 health |
| latency / queue / TTL metadata | PASS | 3 个 command 均携带 inference latency、queue depth 与 250 ms TTL |
| R2 feedback | PASS | `/policy/runtime_hold=true`；HOC actual decision 最终为 `HOLD` |
| R3 feedback | PASS | TriggerEstop service 收到一次请求；HOC actual decision 最终为 `E_STOP` |
| HOC trace | PASS | command 1–3 均关联 Brain / Execution / Safety / Task GT，`issues=[]` |
| M5 strict reload | PASS | 导出的 bundle 由下游严格 loader 读回 3 个 sequence |
| cleanup | PASS | probe、Risk bridge、HOC 均干净退出；无残留测试节点 |

Fast DDS endpoint discovery 将 KEEP_LAST depth 报告为 `0`（unknown）；本地 publisher 合同仍验证为 depth 1。证据同时保留 configured 与 discovered 两份视图，没有把 unknown 改写成 1。

## 3. M6 暴露并修复的两个真实断点

1. HOC 曾只用“最近 execution report”猜 Brain health 的 command 身份；跨 topic 抢跑会把 health 挂到上一 command。修复后 health 显式传播 `last_command_sequence + trace_run_id + episode_id`。
2. Risk bridge 收到 launch SIGINT 时会重复 shutdown 或以 KeyboardInterrupt 退出。修复后节点完成幂等、干净收尾。

## 4. 不可升级的结论

- `Task GT=UNAVAILABLE` 是本次正确结果，因为没有启动任务 evaluator。
- `EXECUTED / HELD / ESTOPPED` 是 mock runtime wiring 决策，不是 SmolVLA 策略表现。
- 本次不改变 Recovery v3 open-loop Pass 或 S4 lift 0/5 Hold。
- 本次不证明闭环抓取、Sim2Real、真机或 authoritative SmolVLA cutover。

持久化摘要与原始运行文件 SHA 见 `evidence/policy_runtime_m6_wiring_20260726/evidence_manifest.json`。
