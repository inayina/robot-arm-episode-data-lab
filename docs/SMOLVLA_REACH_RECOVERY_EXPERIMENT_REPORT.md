# SmolVLA Reach Recovery v1 实验报告

报告状态：`FORMAL MIXED TRAINING COMPLETE / ISAAC NOT AUTHORIZED`  
报告日期：2026-08-21  
实验规范：[SMOLVLA_REACH_RECOVERY_EXPERIMENT.md](SMOLVLA_REACH_RECOVERY_EXPERIMENT.md)

## Final closure

本轮 Scene Contract v2 recovery 数据采集已完成并通过收口门禁：

| 集合 | 设计 | QA Pass | GT Reach/Grasp/Lift | 帧数 |
| --- | ---: | ---: | ---: | ---: |
| train recovery | 16 | 16/16 | 16/16/16 | 3340 |
| validation recovery | 8 | 8/8 | 8/8/8 | 1708 |

四个位点的新源轨迹均为 40 动作连续 `EXECUTED` 前缀；P1 尾部出现的 queue-underrun HOLD 被排除，没有进入 recovery 数据。策略 Stage A 仍统一为 `D_NO_MEANINGFUL_APPROACH`，所以当前结论是：策略闭环尚未学会 Reach；但 policy-visited recovery 标签链已可重复地产生有效双相机数据。GT 成功来自 `scripted_oracle_privileged_gt`，不等于 learned-policy 成功。

release lock：[manifest.json](../evidence/smolvla_reach_recovery_v1_release_20260821T/manifest.json)。它冻结 24 条 recovery episode（16 train + 8 validation）、场景锁、每条 sidecar/parquet/QA SHA；不包含原始 36 条正式训练数据。

## Formal mixed release / training closure

正式 mixed release 已通过本地与远程 release/train-root 校验，并在已通过 REAL preflight 的远程 GPU 上完成唯一配置训练：

| 项目 | 结果 |
| --- | --- |
| release | `smolvla_s3_mixed_recovery_v2_20260821T` |
| release 总量 | 64 episodes / 14,736 frames |
| train / validation / benchmark | 52 / 8 / 4 episodes；12,071 / 1,708 frames（benchmark 4 条仅保留作诊断） |
| 训练输入 | scene+wrist 双相机、`state[15]`、absolute EEF action[8] |
| 配置 | [`lora_train_mixed_recovery_v1.yaml`](../configs/smolvla_s3/lora_train_mixed_recovery_v1.yaml)，seed42，LoRA r=64、alpha=64、dropout=0.05 |
| 训练 | 7,545 steps，batch 8，bf16，约 44 分钟；最终 step=7,545 |
| checkpoint | `runs/smolvla_s3_mixed_recovery_v2/formal_train_20260821T_retry3/lerobot_run/checkpoints/007545/pretrained_model`（远程 GPU） |
| checkpoint audit | Pass；最终 adapter SHA256 `49d01a4445a59b066558af8472b5d01f3e538767ada589f08b072aae80528981` |

本次训练结论仅为：mixed 数据合同、训练执行和 checkpoint 配置审计均完成。训练 loss 下降不能替代闭环任务指标；本轮没有据此宣称 Reach/Grasp/Lift 成功、Isaac 成功、Sim2Real 或真机成功。Isaac/视频需另行授权。

## MuJoCo same-environment closed-loop result

随后使用最终 `007545` checkpoint，在同一 Scene Contract v2、MuJoCo、scene+wrist 双相机和本机 continuous GT evaluator 下，对 P0--P3 各执行 100 actions：

| case | policy report | GT Reach | GT Grasp | GT Lift | Stage A | measured gripper min |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| P0 | Pass | 0 | 0 | 0 | `D_NO_MEANINGFUL_APPROACH` | 0.9639 |
| P1 | Pass | 0 | 0 | 0 | `D_NO_MEANINGFUL_APPROACH` | 0.9511 |
| P2 | Pass | 1 | 0 | 0 | `B_REACH_ALIGN_NO_GRASP` | 0.9341 |
| P3 | Pass | 0 | 0 | 0 | `D_NO_MEANINGFUL_APPROACH` | 0.9465 |

四次 runtime/preflight 均 Pass，动作均完成 100/100；远程 forward p50 约 398--463 ms。最终 train-ID 结果为 Reach `1/4`、Grasp `0/4`、Lift `0/4`：这说明 P2 有一次真实 Reach，但策略尚未稳定学会 Reach，更没有学会完整抓取。四个位点的夹爪 measured min 均高于 0.93，直接说明闭爪动作没有形成。该结论不涉及 Isaac，也不代表标定已完全排除。

证据：[MuJoCo final evidence](../evidence/smolvla_mixed_mujoco_trainid_20260821T_final/)。测试结束后本机进程、SSH 隧道和远程 GPU 推理服务均已清理。

本轮为采集稳定性新增并验证了两个运行时门禁修复：当前 launch 日志确认 controller active 的 fallback，以及 `sync_slop=0.12s / sync_queue_size=120`；recovery expert 的 ALIGN 段固定默认 5 秒、末端 XY 门禁仍为 2 cm。相关上游入口为 `scripts/run_mujoco_policy_visited_recovery.sh`。

回归：上游 recovery/runtime 测试 `34 passed`；中游新增 recovery/Scene Contract 测试 `5 passed`；扩展中游合同回归 `194 passed, 1 failed`。唯一失败是既有 train-split materialization 的无视频 fixture 与 video-tree fail-closed 检查冲突，不涉及本轮 recovery 产物；本轮 shell syntax、release lock integrity 和进程清理均 Pass。

下一 Gate：单独授权有界闭环评测；本报告不自动授权 Isaac、扩 seed 或追加训练。

> 下方第 1--7 节保留为本轮早期 pilot 的历史记录；最终数字和当前状态以本节及 release lock 为准。

## 1. 执行摘要

本轮已完成不依赖远程 GPU 的 L0 实现和两次有界 runtime pilot。P0/prefix25 从未 Reach 的 trace 访问状态成功恢复到 GT Reach/Grasp/Lift，提交 91 帧双相机 episode，并通过中游 capture QA。该结果只验证 recovery 采集链，不代表 SmolVLA 已学会 Reach。

P1/prefix25 被 fail-closed discard。直接原因不是专家控制失败，而是原固定场景只设置红块：P1 红块与蓝柱默认位置重叠，reset 后红块被弹出工作空间。该发现同时阻断原 P1--P3 trace 作为 recovery source；批量 40 条采集没有启动。

## 2. 已实现

| 仓库 | 产物 | 状态 |
| --- | --- | --- |
| 上游 | `isaac_sim_adapter/policy_trace_replay.py` | sequential EXECUTED/bounded EEF8/SHA/timing fail-closed loader |
| 上游 | `scripts/mujoco_policy_visited_recovery.py` | prefix replay 后才录制；scripted recovery；GT Lift 才 commit |
| 上游 | `scripts/run_mujoco_policy_visited_recovery.sh` | MuJoCo 双相机有界 runner 与退出清理 |
| 中游 | `validate_policy_visited_recovery_capture.py` | human/scripted expert provenance + episode 合同验收 |
| 中游 | 本规范与本报告 | 实验矩阵、Gate、停止线与证据口径 |

## 3. 验证结果

| 验证项 | 结果 |
| --- | --- |
| upstream replay/coordinator/runtime 合同测试 | `34 passed` |
| midstream capture/phase/adapter/Scene Contract v2 测试 | `19 passed` |
| Python AST、shell syntax、diff whitespace | Pass |
| P0/prefix25 runtime pilot | accepted + capture QA Pass |
| P1/prefix25 cross-position pilot | correctly rejected; no episode committed |
| 退出清理 | Pass；未保留 MuJoCo/ROS/recorder/GT 进程 |

首个 P0 pilot 的 GT recorder 在旧 runner 中被 SIGTERM 后出现 `rclpy context invalid` 退出 traceback，导致独立 `episode_results.jsonl` 为空。它不改变 coordinator 已取得的 live GT snapshot、recorder commit 或 episode 内的 upstream task phases。runner 已加入 `--exit-on-report`；P1 复测自然产出一条 GT result 且无 traceback。

## 4. 结果表

| case | prefix | repeat | runtime | GT Reach | GT Grasp | GT Lift | recorder | capture QA | episode |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| P0 | 25 | 0 | `CAPTURE_ACCEPTED_PENDING_MIDSTREAM_QA` | 1 | 1 | 1 | commit, 91 frames | Pass | `episode_000000` |
| P1 | 25 | 0 | `CAPTURE_REJECTED` | false | false | false | discard, 0 frames | not run | none |

P0 关键量：source trace SHA256 `55af6e...5e0b`；25 动作 recorded duration `4.654 s`；prefix 终点 EE-object XY `0.0939 m`，高于 Reach 阈值 `0.05 m`；expert ALIGN 后 `0.00486 m`；最终 live GT 为 `Reach=1, Grasp=1, Lift=1`。source prefix 含 1 条 bounded clipping，replay 使用的是已执行 `bounded_action`。

P1 关键量：期望红块 `(0.40,0.10)`，实测 recovery 接管时红块 `(0.284,-1.255)`；ALIGN 后仍相差 `0.619 m`，因此 discard。配置静态审计还发现 P2 红块/绿球间距约 `0.061 m`，P3 红块/蓝柱间距约 `0.045 m`。

## 5. 采集阶段历史结论

采集机制已由 P0 runtime 数据验证，但四位点数据矩阵尚不具备有效场景前提。该段记录的是正式 mixed release 之前的历史 Current Gate；Scene Contract v2 随后已完成验收，正式训练结果见本报告顶部的 closure。

Scene Contract v2 已在本地落地：蓝柱固定 `(0.55,-0.18)`、绿球固定 `(0.55,0.18)`，四个位点的任意物体两两 XY 间距均不小于 `0.15 m`；四个 YAML 的 SHA256 已冻结在 `configs/smolvla_s3/recovery_scene_v2/lock.json`。P1 真实 MuJoCo probe 两次读取相隔约 `17.5 s`，红块均为 `(0.400000,0.100000,0.024985)`，未再发生弹飞。该 probe 只验收场景稳定，不是 policy rollout。

## 6. 声明边界

本报告不声明 learned-policy Reach、抓取成功、Isaac、Sim2Real 或真机。Scripted expert 的 GT Lift 只证明该 recovery episode 的标签链可用，不代表当前 SmolVLA 已学会策略。

## 7. 证据入口

- P0 accepted pilot：`evidence/smolvla_reach_recovery_P0_k25_r0_20260821T_reachpilot01/`
- P0 capture QA：上述目录的 `capture_validation_report.json`
- P1 rejected pilot：`evidence/smolvla_reach_recovery_P1_k25_r0_20260821T_reachpilot02/`
- P1 fail-closed 原因：上述目录的 `execution_report.json`
- Scene Contract v2 P1 runtime probe：`evidence/smolvla_recovery_scene_v2_P1_probe_20260821/runtime_probe.json`
