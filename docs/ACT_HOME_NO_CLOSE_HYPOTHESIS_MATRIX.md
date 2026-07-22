# ACT HOME_NO_CLOSE：假设—证据矩阵与止损持有

**状态（2026-07-21）**：ACT 保留为 **失败但有价值的 diagnostic baseline**。  
**禁止**：删除/覆盖 E3 0/20 与 E3.6 证据；盲训；普通下降扩采；盲扫 stage weight；完整 E4。  
**物理对照**：E3.5 scripted oracle lift **5/5**（`task_success_claimed=false`）。

权威行为证据：[`../evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json`](../evidence/e3p6_closelift40_5seed_home_20260720/smoke5_gate.json)

- seeds 2200–2204；`lift_count=0`；`gate_pass_ge1=false`
- 5/5 `verdict=HOME_NO_CLOSE`；`grip_min=1.0`；`z_span≈0.014`；`status=PASS`（interface）
- GT：`failure_stage=reach` / `gripper never closed below 0.120`

---

## 1. 持有决议

| 决议 | 状态 |
|---|---|
| 保留 E3 / E3.6 / oracle 证据目录 | 必须 |
| 不把 0/20 或 0/5 隐藏或改写为成功 | 必须 |
| 无新假设时不继续训练 | 必须 |
| 仅在下表「最小证据」产出后，才允许**有假设**的小回归 | 条件允许 |
| 完整 E4 / OOD 矩阵 | **No-Go**（见 Benchmark 硬门禁） |

---

## 2. 假设—证据矩阵

| 假设 | 先验（现码） | 最小验证证据（只读/小诊断，非再训） | 当前状态 |
|---|---|---|---|
| observation / history 不足 | 训练与部署强制 `n_obs_steps=1`（`train_act_lerobot.py` / `scene_act_runtime.py`） | 对比 chunk 内后续步是否含 close；home 帧 vs close 帧条件分布 | **未跑新诊断**；先验高 |
| language / scene conditioning 不足 | 推理 `infer(state, rgb)` **无 language**；单任务红块时语言近常数 | 统计 train instruction 唯一值；确认 `input_features` 无语言（已确认） | 语言假说对「指令泛化」重要，对当前 HOME_NO_CLOSE **非主因（基于证据的推断）** |
| home 阶段样本与动作分布 | 失败全在 reach / 未闭合 | 按 stage 统计 gripper_cmd；home 帧 action≈0 占比；对照 oracle close 段 | **已跑只读诊断**（`act_home_no_close_diag_fixture.json`）；home_like 近零 delta 占比高；**尚未**单独授权再训 |
| action normalization | checkpoint 含 action mean/std | smoke 日志 raw/denorm 直方图；close 目标是否塌缩到 open | **未验证** |
| action chunk | 部署强调勿只取 chunk[0]；`select_action` 队列 | 确认评测 `deploy_n_action_steps`；可选对比 8 vs 50 的 grip_min（小回归，非重训） | E3.6 日志确认 **deploy_n_action_steps=8 / chunk_size=50**；8 vs 50 对比 **未跑** |
| 图像/状态时间对齐 | 训练 10 Hz 相机 vs Isaac 在线 | obs age / 丢帧；scene vs joint stamp | **未验证** |
| 模型容量 / 训练不足 | 已有止损：定向 40-ep 仍 0/5 | 仅当分布诊断显示 close 可学且 infer 系统偏置时再开有假设小回归 | **当前不作为下一步** |
| train / inference obs 不一致 | 训练与 `preprocess_rgb` 应对齐 | 逐项比对 resize/crop/mean-std；state 含 gripper；缺图混入检查 | **未跑新逐项审计**；先验中高 |

---

## 3. 允许的下一步（若重启 ACT 诊断）

1. 只读分布脚本：home vs close 的 gripper_cmd / delta 直方图（不训）。
2. 确认某次 smoke 的 `deploy_n_action_steps` 与 chunk 消费日志。
3. 若（1）（2）给出明确可证伪假设，再开 **≤5 seed** 有界回归；仍禁止 E4。

**落地（2026-07-21，只读）**：

| 产物 | 路径 |
|---|---|
| 诊断库 | `evaluation/diagnostics/home_no_close.py` |
| CLI | `training/scripts/diagnose_home_no_close.py` |
| 样例报告 | `evaluation/examples/act_home_no_close_diag_fixture.json` |
| 测试 | `tests/test_absolute_eef_episode_and_home_diag.py` |

```bash
python3 training/scripts/diagnose_home_no_close.py \
  --frames-jsonl data/releases/e2_500hz_random35_closelift_20260720/frames.jsonl \
  --evidence-dir evidence/e3p6_closelift40_5seed_home_20260720 \
  --output-json /tmp/home_no_close_diag.json
```

已确认 E3.6 smoke：`deploy_n_action_steps=8`，`chunk_size=50`（`seeds/*/policy.log`）。  
直方图见样例报告；**尚未**形成可授权 ≤5 seed 回归的单一可证伪假设（仍止损）。

---

## 4. 验收

- [x] 止损与假设矩阵成文
- [x] Canonical facts / model card 指向本文件
- [x] 未启动训练、扩采或 E4
- [x] 只读 home/close 直方图 + deploy_n_action_steps 诊断脚本（不训）
