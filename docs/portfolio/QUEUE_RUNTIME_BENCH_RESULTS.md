# S4 Queue Runtime 实测（P1-1）

**状态**：已执行（offline diagnostic；**非** Isaac 扩种子）  
**跑次**：`runs/smolvla_s3/queue_runtime_bench_20260726T040945Z/`  
**GPU**：NVIDIA RTX PRO 500 · peak ≈937 MiB · 每模式 150 ticks @ 10 Hz（实时 pacing）  
**诚实边界**：**Not task success / Not Sim2Real / Not real robot** · `gate_eligible=false` · `ran_isaac=false`

---

## 1. 问题

合同写明 `chunk10 / K5 / 10 Hz / replan 0.5 s / async_double_buffer=on`，但：

- 中游 `ActionChunkQueue` 仅有 CPU 契约测试；
- `recovery_decisions.yaml` 曾标 `async_double_buffer_runtime_implemented=false`；
- 上游 `smolvla_policy_inference_node` 仍在 inference timer 里**同步**调用 `select_action`（未接双缓冲）。

P1-1 回答：在真实 LoRA 延迟下，**同步重规划是否撑得住 100 ms 控制周期**，以及 **async double-buffer 能否把 GPU 成本藏进 K=5 窗口**。

---

## 2. 协议

| 项 | 值 |
|---|---|
| 模式 | `sync` vs `async_double_buffer` |
| 合同 | chunk=10 · execute K=5 · 10 Hz · replan 0.5 s |
| 观测流 | prospective eval10 第 1 条 episode 循环帧 |
| 推理 | `predict_action_chunk` → 取 10 步 → queue 只执行前 5 |
| Async 语义 | 执行当前 K 时预取下一块；**仅在队列空时 swap**（不截断当前 K） |
| pacing | 实时 10 Hz（否则预取没有墙钟重叠窗口） |

入口：`scripts/run_smolvla_s4_queue_runtime_bench.sh`

---

## 3. 结果（权威跑次）

| 指标 | sync | async_double_buffer |
|---|---:|---:|
| underrun rate | 0 | 0 |
| **deadline miss rate**（tick > 100 ms） | **0.20**（30/150） | **0.0067**（1/150，仅冷启动） |
| infer p50 / p95 / max (ms) | 163 / 182 / 207 | 157 / 172 / 174 |
| fits replan budget (max ≤ 500 ms) | true | true |
| infer_calls | 30 | 31 |

**结论（诊断口径）**：

1. 单次 chunk 推理 ≈160–180 ms，**小于** replan 预算 500 ms，但**大于**控制周期 100 ms。  
2. **Sync**：每 K 步重规划一次都会 deadline miss（约 20% ticks）——与当前在线节点「timer 内同步 infer」的风险一致。  
3. **Async double-buffer**：在 K 窗口内预取后，deadline miss 降到冷启动 1 次；chunk/K 调度在本机 GPU 上**时可隐藏**推理延迟。  
4. 这**不能**证明闭环抓取会成功，也**不**自动把上游在线路径改成 async。

---

## 4. 实现状态（诚实）

| 层 | 状态 |
|---|---|
| 中游 `ActionChunkQueue` + `AsyncDoubleBufferScheduler` | **已实现并实测** |
| Offline GPU bench | **已完成**（本页） |
| 上游 Isaac 节点接入双缓冲 | **未做**（仍 sync `select_action`） |
| `async_double_buffer_runtime_implemented` | 拆分为 offline measured / online pending（见 `recovery_decisions.yaml`） |

---

## 5. 明确不做

- 不改 `eval_gate_v3` / 不改写 Pass  
- 不扩 Isaac seed、不重训  
- 不声称任务成功 / Sim2Real  
- 不把本 bench 当作 online runtime 已落地
