# M6 ROS 2/DDS Wiring Evidence

这是 2026-07-27 有界 M6 wiring smoke 的可公开精简证据。它来自三个真实 ROS 2 进程之间的
DDS 交互，PolicyBackend 为 mock；没有启动仿真器、模型或训练。

## 直接结论

- 3 个 command 均完成 Brain / Execution / Safety / Task GT 四泳道关联；`issues=[]`。
- Execution 依次为 `EXECUTED → HELD → ESTOPPED`。
- Safety 依次为 `R0 RUN → R2 HOLD → R3 E-STOP`。
- Task GT 始终为 `UNAVAILABLE`，因此该证据不声称任务成功。

机器可读摘录：[m6_timeline_summary.json](m6_timeline_summary.json)。  
面试展示图：[policy_runtime_m6_fault_response_timeline.png](../../policy_runtime_m6_fault_response_timeline.png)。

## 生成方式

原始运行入口位于下游仓库：

```bash
scripts/run_policy_runtime_m6_wiring_smoke.sh <evidence_dir>
```

从原始 `m6_wiring_smoke.json` 和 `hoc_runtime_report.json` 生成展示图与公开摘要：

```bash
python3 scripts/generate_m6_wiring_evidence_figure.py \
  --evidence-dir evidence/policy_runtime_m6_wiring_20260727T075600Z \
  --output docs/portfolio/policy_runtime_m6_fault_response_timeline.png \
  --summary-output docs/portfolio/public_evidence/m6_wiring_20260727/m6_timeline_summary.json
```

摘要中的 `source_sha256` 绑定本次两份原始 JSON；图片中的每个 command、裁决与相对 trace
时间均由脚本读取，不是手工填写。

## 不能升级的结论

该证据不证明 SmolVLA 在线执行、闭环抓取、任务成功、物理力矩归零、实体急停、Sim2Real
或真机能力。
