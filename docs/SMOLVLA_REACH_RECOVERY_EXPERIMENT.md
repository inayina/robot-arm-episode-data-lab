# SmolVLA Reach Recovery v1 实验规范

状态：`FORMAL MIXED TRAINING COMPLETE / ISAAC NOT AUTHORIZED`  
冻结日期：2026-08-21  
实验 ID：`smolvla_reach_recovery_v1`

最终执行状态（2026-08-21）：Scene Contract v2 下 P0/P1/P2/P3 新源轨迹均完成 40 动作连续 `EXECUTED` 校验；16 条 train recovery 与 8 条 validation recovery 全部通过双相机 capture QA。随后已生成并验收正式 mixed release，完成远程 LoRA 训练与 checkpoint finalize。已生成 [recovery release lock](../evidence/smolvla_reach_recovery_v1_release_20260821T/manifest.json)。该 lock 仍只冻结 recovery 数据；正式训练使用下方独立 mixed release。训练完成不等于 learned policy 已通过闭环任务成功，Isaac 仍未授权。

## 1. 目标与直接判定

目标是让当前双相机 SmolVLA 在 MuJoCo 四个训练位点形成可重复的闭环 `Reach`。上游 canonical GT 定义保持不变：EE 与物体初始位置的 XY 距离不大于 `0.05 m`。专家采集使用更严格的 `0.02 m` 对准目标，为闭环误差留出余量。

当前起点是 P0--P3 在干净 runtime 下均完成 100/100 动作与 20/20 个 K=5 chunk，但 Reach/Grasp/Lift 全为 false。该结果支持 `NOT_LEARNED_CLOSED_LOOP`，不支持标定故障、空间 OOD、Isaac、真机或任务成功结论。

## 2. 假设

| 假设 | 可证伪证据 | 决策 |
| --- | --- | --- |
| H1 专家状态分布与 policy 闭环访问状态不一致 | 在 policy trace 前缀终点采集专家纠偏后，Reach 明显改善 | 构建 policy-visited recovery mixed release |
| H2 仅增加训练步数即可修复 | 不改变数据只增加 epoch 才改善 | 本轮禁止该实验，避免与 H1 混淆 |
| H3 replay/接管污染训练标签 | episode 含 prefix policy action、Hold fill、双 publisher 或缺 GT | fail-closed discard，不进入 release |

方法属于 DAgger-like 数据聚合，但不是自动 DAgger：policy 状态来自已冻结的真实闭环 trace，标签来自随后执行的 scripted expert recovery。

## 3. 原冻结输入与场景合同审计

| case | XY | yaw | source actions SHA256 |
| --- | --- | ---: | --- |
| P0 | `(0.36,-0.10)` | `-6.74912045°` | `cc48990a4e2e2882187ccbe0e857dd20a7fc4d17885cb0d84668507c230d199c` |
| P1 | `(0.40,0.10)` | `-6.74912045°` | `58fc074ea7638a3588bfd9b43d09020b20f08e039f12b76425d8119e8103ae16` |
| P2 | `(0.44,-0.06)` | `-6.74912045°` | `42174428094acb2b2ef1ffd575ebfcd2ca8a6f403820d743b0c92a5fa5d22762` |
| P3 | `(0.38,0.06)` | `-6.74912045°` | `2f4eb50ffda1a0585816983704126a7ecda0263fc2c2b50e25b3e00be03c4c26` |

共同合同：MuJoCo、scene+wrist 320×240@10 Hz、`state[15]`、absolute EEF8、任务文本 `pick up the red box and place it in the left bin`、`grasp_assist=false`。物体 pose 只允许 scripted expert 与上游 GT 使用，禁止进入 policy input。

2026-08-21 runtime pilot 暴露了固定场景碰撞：原配置只固定红块，蓝柱和绿球仍使用 MuJoCo fallback 位置。P1 红块 `(0.40,0.10)` 与蓝柱 fallback `(0.40,0.10)` 完全重叠；P2 红块与绿球相距约 `0.061 m`；P3 红块与蓝柱相距约 `0.045 m`。P1 实测 reset 后红块被弹至 `(0.284,-1.255)`，因此该 trial 被 fail-closed discard。

由此冻结以下修订：

- 旧 source trace 仅保留为历史 pilot；本 release 只使用上表 Scene Contract v2 trace；
- P0--P3 新 trace 的 40 动作连续前缀已通过 loader 校验；P1 原有尾部 HOLD 不进入 recovery source；
- Scene Contract v2 必须显式固定红块、蓝柱、绿球，并要求任意两物体 XY 间距至少 `0.15 m`；
- Scene Contract v2 冻结蓝柱 `(0.55,-0.18)`、绿球 `(0.55,0.18)`，红块仍使用 P0--P3 各自目标位点；干扰物保留在双相机画面中，但不允许与目标或夹爪接近区重叠；
- target-only 场景只允许作为独立 A/B 诊断，不混入 recovery train/validation release；
- Scene Contract v2 生效后已用当前策略重新生成 P0--P3 trace；不能把旧 action replay 冒充为新场景中的 policy-visited state；
- （采集阶段历史记录）新 trace 生成使用远程 GPU 推理服务，但当时未训练；正式 mixed training closure 见第 7 节。

## 4. 执行链

```text
固定 MuJoCo reset
  → 校验 actions.jsonl 只含连续 EXECUTED bounded_action[8]
  → 按 command_emitted_monotonic_ns 重放前缀
  → 前缀结束后才启动 recorder
  → scripted expert: Align → Hover → Descend → Close → Lift
  → ContinuousTaskEvaluator 观察 Reach/Grasp/Lift
  → GT Lift=true 才 commit，否则 discard
  → 中游 recovery capture validator
```

重放器与 expert 共用一个 ROS 节点和一组 publisher；执行前要求 `/teleop/cmd_pose`、`/teleop/gripper_cmd` publisher count 均为 1。这样不存在 policy→expert 的双 publisher 竞争。录制在 prefix 完成后才开始，因此错误 policy action 不进入训练 episode。

## 5. 数据矩阵（Scene Contract v2 trace 验收后执行）

### Train recovery：16 accepted episodes（已完成）

P0--P3 每点使用 prefix count `25/37`，每个前缀两次 accepted recovery。当前远程完整 forward 延迟约 `0.50 s`，接近 K=5 的 `0.50 s` replenishment budget；超过早期 prefix 的 source trace 出现 queue-underrun HOLD，因此不把 HOLD 后的 action 混进 recovery：

```text
4 positions × 2 early prefix states × 2 repeats = 16 train recovery episodes
```

### Recovery validation：8 accepted episodes（已完成）

P0--P3 每点使用 prefix count `30/40`，每个前缀一次，全部从训练 split 排除。所有 validation prefix 必须来自同一 Scene Contract 下连续 `EXECUTED` trace：

```text
4 positions × 2 held-out prefix states = 8 recovery validation episodes
```

这些 validation episode 只对 prefix state 做留出，不声称是独立 policy rollout 或空间 OOD。最终泛化判定由训练后新的闭环 rollout 承担。

## 6. 单条 episode 验收

必须全部满足：

- source trace SHA、case、prefix count 和 replay timing 有记录；
- 单一 command authority；
- recording 在 prefix 结束后开始；
- `command_missing=false`、`action_fill=teleop_command`、双相机完整、10 Hz；
- expert source 明确为 `scripted_oracle_privileged_gt`；
- Align 最终 XY ≤ `0.02 m`；
- upstream continuous GT 含 `LIFT`；
- recorder commit 成功；
- `validate_policy_visited_recovery_capture.py` Pass。

任一条件失败必须 discard，不允许手工把失败 episode 改成 success。

## 7. 正式 mixed release 与训练结果

正式训练已按唯一配置执行，且未把 validation/benchmark episode 放入训练根：

| 项目 | 结果 |
| --- | --- |
| release | `smolvla_s3_mixed_recovery_v2_20260821T` |
| release 内容 | 64 episodes / 14,736 frames；train 52 / 12,071，validation 8 / 1,708，benchmark 4 |
| train 组成 | 原始双相机 train 36 + recovery train 16 |
| 输入合同 | scene+wrist 双相机、`state[15]`、absolute EEF action[8] |
| 训练配置 | [`configs/smolvla_s3/lora_train_mixed_recovery_v1.yaml`](../configs/smolvla_s3/lora_train_mixed_recovery_v1.yaml)，seed42，LoRA r=64/alpha=64 |
| 训练 | 7,545 steps，batch 8，bf16，约 44 分钟；最终训练步 `7545` |
| checkpoint | 远程 `runs/smolvla_s3_mixed_recovery_v2/formal_train_20260821T_retry3/lerobot_run/checkpoints/007545/pretrained_model` |
| checkpoint audit | Pass；双相机、state/action 维度、LoRA 参数、训练步数和 pre/post-process metadata 一致 |

本 Gate 的结论是“正式训练产物有效且合同一致”。它不能单独证明 Reach/Grasp/Lift 学会，也没有运行 Isaac 或录制成功视频；下一步必须另行授权并执行有界闭环评测。

## 8. MuJoCo 同场景闭环测试结果

正式 mixed checkpoint 已在相同 Scene Contract v2 的 MuJoCo 双相机环境执行 P0--P3，各 100 actions；本次未运行 Isaac、未运行 seed42 OOD：

| case | runtime / preflight | Reach | Grasp | Lift | Stage A | gripper state min |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| P0 | Pass / Pass | 0/1 | 0/1 | 0/1 | `D_NO_MEANINGFUL_APPROACH` | 0.9639 |
| P1 | Pass / Pass | 0/1 | 0/1 | 0/1 | `D_NO_MEANINGFUL_APPROACH` | 0.9511 |
| P2 | Pass / Pass | 1/1 | 0/1 | 0/1 | `B_REACH_ALIGN_NO_GRASP` | 0.9341 |
| P3 | Pass / Pass | 0/1 | 0/1 | 0/1 | `D_NO_MEANINGFUL_APPROACH` | 0.9465 |

结论：策略在 P2 出现一次真实 GT Reach，但 train-ID 四个位点仅 `1/4 Reach`，未达到稳定 Reach 门槛；四个位点均未闭爪，Grasp/Lift 为 `0/4`。因此当前应标记为 `PARTIAL_REACH_ONLY / NOT_LEARNED_ROBUSTLY`，不能说策略已经学会。失败更直接表现为策略动作中的夹爪长期保持打开（最小 measured gripper 约 0.934），而不是 MuJoCo 双相机 runtime 或 safety 门禁失败。

证据目录：`evidence/smolvla_mixed_mujoco_trainid_20260821T_final/`。远程 GPU 仅承担 policy forward；MuJoCo、双相机、GT evaluator 和控制执行均在本机完成。

## 9. Release 与训练停止线

以下条目是 recovery 采集阶段的历史停止线；正式 mixed release/训练已在第 7 节完成。

当前只授权场景修复、策略 trace 更新、采集与本地验收；本轮已完成 recovery release acceptance：

- recovery-only lock 与正式 mixed release 均已生成并验收；训练使用 `smolvla_s3_mixed_recovery_v2_20260821T`；
- 正式训练已完成并通过 checkpoint audit；不自动进入 Isaac；
- Scene Contract v2 下重新生成 P1--P3 policy trace 需要用户重新开机，且只允许推理；
- 不追加训练、不改 checkpoint、不进入 Isaac、不扩 seed42；
- recovery lock 显式冻结 recovery train 16 + validation 8，validation episode index 为 `17..24`，不进入 train；
- 下一 Gate 是单独授权闭环评测；训练结果本身不构成任务成功。

## 10. 训练后 Reach Gate（未来，未授权执行）

P0--P3 每点独立运行三次、每次 100 动作：

- 每点至少 `2/3 Reach`；
- 总计至少 `10/12 Reach`；
- Reach 前不提前闭爪；
- 每轮 runtime 100/100、K=5 完整；
- 只有 ContinuousTaskEvaluator GT 可以给出 Reach。

未达到该 Gate 时回到对应 policy-visited bucket 补数据，不自动增加 epoch、放宽 TTL 或进入 OOD。

## 11. 本地入口

单条采集示例（仅适用于 source trace 已通过同一 Scene Contract 验收的 case）：

```bash
cd /home/ina/dev/ros2-arm-teleoperation-suite
CASE_ID=P0 PREFIX_COUNT=25 REPEAT_ID=0 \
  bash scripts/run_mujoco_policy_visited_recovery.sh
```

入口有硬超时并在退出时清理 MuJoCo、ROS 2、recorder、GT 和控制进程。
