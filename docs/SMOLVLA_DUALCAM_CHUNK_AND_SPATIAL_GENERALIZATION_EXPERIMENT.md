# SmolVLA 双相机 Chunk 合同与空间泛化隔离实验

状态：2026-08-21 冻结后执行。仿真证据限定为 MuJoCo；不声明 Isaac、真机、Sim2Real 或任务成功，除非本实验的连续 GT 明确给出对应子目标成功。

## 1. 直接问题

当前双相机 checkpoint 在专家状态分布的 canonical first-action 离线评测为 Pass，但一次 MuJoCo 闭环运行在 `reach` 阶段失败。该运行完成 100/100 条接口动作，夹爪始终保持打开，并且 100 条命令的 chunk index 分布为 `0:77, 1:21, 2:2, 3:0, 4:0`。

本实验只回答两个问题：

1. 异步推理结果是否截断尚未消费完的 K=5 active chunk；
2. 修复执行合同后，策略在训练位置与空间分布外位置分别学会到什么程度。

## 2. 冻结事实与边界

- checkpoint：`runs/smolvla_wrist_ablation_v1_B/train_20260818_retry2/lerobot_run/checkpoints/005460/pretrained_model`；
- 输入：`observation.state[15] + scene RGB + wrist RGB`；
- 输出：`absolute_eef_gripper_v0`，action8，chunk10，执行 K=5；
- 控制合同：10 Hz，K=5，名义覆盖 0.5 s，重规划周期 0.5 s；
- 训练指令与运行指令均为 `pick up the red box and place it in the left bin`；
- 训练位置：P0 `(0.36,-0.10)`、P1 `(0.40,0.10)`、P2 `(0.44,-0.06)`、P3 `(0.38,0.06)`；P4 `(0.48,0.00)` 仅属于 benchmark；
- 本次分布外复现位置：seed42 `(0.41115414,-0.14249677)`；其 y 超出训练最小值，距最近训练点约 0.067 m；
- 不重训、不改 action/state/camera schema、不改控制器增益、不改相机几何、不进入 Isaac。

## 3. 假设

| 假设 | 可证伪观察 | 处置 |
| --- | --- | --- |
| H1 active chunk 被异步结果提前替换 | 同一 observation sequence 大量只执行 index0，index3/4 缺失 | active/pending 双槽；新结果只能替换 pending，不能截断 active |
| H2 主要是空间覆盖不足 | 训练位置可 Reach/Grasp，而 seed42 失败 | 增加连续 XY 与边界位置数据，不把结果归因于标定 |
| H3 闭环 BC 本身未形成 | 合同修复后四个训练位置仍不能 Reach/Grasp | 采集 policy-visited recovery/DAgger-like 示教，再考虑重训 |
| H4 运行接口仍是 blocker | 无完整 report、控制器不 active、EE 位移小于 1 mm 或 runtime ERROR | 结果记为 runtime blocked，禁止评价策略 |

H1 修复采用边界切换，不在此轮引入新的 temporal-ensemble 算法：

- active chunk 必须按 10 Hz 消费至 K=5 或被 safety/hold/TTL 明确清空；
- 推理与 active 执行并行；
- 新完成结果进入 latest-only pending；
- active 消费完后才原子切换 pending；
- clear/reset 必须同时清空 active 与 pending。

运行时年龄预算冻结为：传感器新鲜度仍为 0.5 s、command TTL 仍为 0.1 s；仅 policy source-observation age 使用 2.5 s。其预算覆盖约 0.5 s 远程推理、active K=5 的 0.5 s、pending 等待和 0.5 s 调度余量。控制定时器只复制 joint/gripper/EE，不得在 50 Hz 心跳和 10 Hz 命令消费路径复制两路相机数组；完整图像只由 inference snapshot 读取。

一次 5 Hz 双相机发布率 probe 没有改善调度，因此正式合同恢复训练一致的 10 Hz 双相机。推理 snapshot 的双相机 freshness 仍为 0.5 s；控制消费只读取 joint/gripper/EE，使用独立 2.5 s timeout，并继续由 safety watchdog、command TTL 与 policy source-age 三道门禁约束。不得用 control-state timeout 放宽相机 freshness。

## 4. 实验顺序

### Gate C0：文档与工作树

- 记录三仓 HEAD 和 dirty tree；
- 中游拥有实验文档与最终证据；
- 上游只拥有 runtime、runner 与测试修改；
- 下游不修改。

### Gate C1：合同单元测试

必须证明：

1. active 已消费 index `0,1,2` 时，新结果到达不会使下一条回到新 chunk index0；
2. 旧 active 继续给出 `3,4`；
3. 随后切换到最新 pending 的 index0；
4. 多个 pending 到达时只保留 observation sequence 最新者；
5. hold/reset 同时清空 active 与 pending。

### Gate C2：bridge-only/runtime 验证

- 运行上游 policy runtime 测试；
- 运行 Python 语法与 shell 语法检查；
- reset 后的 safety gate 可在 10 s 有界窗口内重复读取，但必须观察到明确 `ok:true`，不得把消息竞态当作 safety Pass；
- 若测试未通过，不启动 MuJoCo。

### Gate C3：MuJoCo 双相机闭环矩阵

使用同一 checkpoint、同一任务文本和同一 yaw，依次执行：

| case | XY | 分布标签 |
| --- | --- | --- |
| P0 | `(0.36,-0.10)` | train-ID |
| P1 | `(0.40,0.10)` | train-ID |
| P2 | `(0.44,-0.06)` | train-ID |
| P3 | `(0.38,0.06)` | train-ID |
| seed42 | `(0.41115414,-0.14249677)` | spatial-OOD |

每个 case 首次运行 100 条动作。若首次产生真实 Lift，runner 可在相同 XY 下做确认运行；不得把接口 PASS 当作触发条件。

## 5. 指标与判定

每个 case 必须保存：

- `report.json`、`actions.jsonl`、连续 GT；合同隔离阶段关闭额外视频编码，合同通过后至少为一个最终证据 case 保存 scene/wrist 视频；
- requested/completed、runtime validity、控制器状态、最大 EE/joint 位移；
- chunk index 直方图、每个 observation sequence 实际消费长度；
- gripper min、first close index；
- EE 到物体的 XY start/best/end；
- Reach、Grasp、Lift、object Δz。

判定口径：

- `RUNTIME_BLOCKED`：合同、观测、安全、控制器或报告不完整；
- `NOT_LEARNED_CLOSED_LOOP`：四个 train-ID 均没有 Reach，或均不进入下降/闭爪；
- `NARROW_ID_POLICY`：train-ID 存在可重复 Reach/Grasp，但 spatial-OOD 明显失败；
- `PARTIAL_REACH_ONLY`：有 Reach，无 Grasp；
- `TASK_SUCCESS_CONFIRMED`：连续 GT 明确 Reach、Grasp、Lift，且确认运行保持一致；
- 单次结果只能支持对应 case，不自动推广为总体成功率。

## 6. 后续决策

- 若 H1 修复后 train-ID 明显改善：保留 checkpoint，继续完善 pending/fusion 遥测；
- 若 train-ID 成功、OOD 失败：采集连续 XY，覆盖 `y=-0.15` 附近及位置间插值；
- 若 train-ID 仍失败：优先采集策略实际访问状态上的恢复示教，并平衡 Align/Descend/Close/Lift；之后才批准一次重训；
- 不通过本实验直接增加 epoch、放宽 TTL、堆 GPU 或修改标定。

## 7. 物理收尾

每次运行必须有硬超时。实验结束无论成功或失败，都必须清理本次启动的 MuJoCo、ROS 2、视频、GT、policy runtime、本地 SSH tunnel 与远程 inference server，并确认没有残留进程。

## 8. 2026-08-21 执行记录

### 8.1 静态与合同测试

- 上游相关测试：`49 passed, 2 skipped`；
- Python compile 与 runner `bash -n`：Pass；
- active/pending 单元合同：active 不被 pending 直接覆盖、latest-only pending、clear 同时清空两槽，均 Pass。

### 8.2 P0 与 timing probes

P0 固定为 `(0.36,-0.10)`、seed42 yaw，checkpoint 与任务文本均未改变。

| evidence | 负载/门限 | completed | elapsed | full K=5 sequences | grip min | GT |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `smolvla_dualcam_chunkfix2_P0_20260821` | 双路视频，source-age 2.5 s | 100/100 | 179.4 s | 5 | 0.9448 | Reach/Grasp/Lift false |
| `smolvla_dualcam_chunkfix4_P0_20260821` | 无视频，source-age 2.5 s | 100/100 | 99.5 s | 10 | 0.9543 | Reach/Grasp/Lift false |
| `smolvla_dualcam_age5_probe_P0_20260821` | 无视频，source-age 5 s，25 actions | 25/25 | 29.1 s | 3 | 0.9625 | 非正式短 probe |
| `smolvla_dualcam_cam5_probe_P0_20260821` | 相机 5 Hz，25 actions | 25/25 | 37.1 s | 1 | 0.9481 | 非正式短 probe |
| `smolvla_dualcam_controlstate_probe_P0_20260821` | 独立 control-state timeout，25 actions | 25/25 | 29.2 s | 1 | 0.9642 | 非正式短 probe |

结论：关闭额外视频明显减少墙钟时间，但没有修复策略行为；降低相机率和放宽 source-age 不能修复 chunk 消费，且会引入陈旧动作，因此不得作为正式方案。P0 的接口与控制链可运行，但策略保持开爪且没有达到 Reach。与此同时，在线 K=5 timing 尚未达到本文件 Gate C1 的运行时验收，P0 只能记为 `TIMING_IMPERFECT_POLICY_FAIL`，不能单独升级为全位置的 `NOT_LEARNED_CLOSED_LOOP`。

P1/P2/P3/seed42 矩阵在 P0 失败后需要新的显式人工批准；未批准前停止扩展。若批准，所有后续 case 继续无视频运行，只有真实 Lift case 才追加双路视频确认。

### 8.3 runtime-hold 与 callback-group 根因修复

进一步遥测确认，旧运行中的 `HELD` 不是模型推理失败。上游节点存在两项执行生命周期问题：

1. `/policy/runtime_hold` 的重复同值消息会重复清空 active/pending；已改为只在 `false→true` 或 `true→false` 边沿执行清队列与恢复重规划；
2. 50 Hz 目标/心跳 timer 与 10 Hz chunk 消费 timer 共用同一个 `MutuallyExclusiveCallbackGroup`，持续就绪的 50 Hz timer 会饿死 chunk 消费，导致 source observation 老化并进入 queue hold；已拆为独立 callback groups。

回归测试为 `52 passed`。修复后的 P0 时序证据：

| evidence | actions | policy elapsed | command interval P50/P95 | full K=5 | queue hold | GT |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `smolvla_dualcam_timergroup_probe_P0_20260821` | 25/25 | 5.85 s | 102/215 ms | 5/5 | 0 | 短时序 probe，无任务结论 |
| `smolvla_dualcam_timergroup_P0_20260821` | 100/100 | 20.44 s | 153/383 ms | 20/20 | 1 | Reach/Grasp/Lift false |

正式 P0 中 100 条命令全部 `EXECUTED`，chunk index 为严格均衡的 `0:20, 1:20, 2:20, 3:20, 4:20`，`runtime_hold_transition_count=0`。因此 H1 的 active/pending 截断与 callback starvation 已从当前 P0 排除。P0 仍保持开爪（`grip_min=0.9392`）且无有效接近，应记为运行时合同干净的 train-ID policy failure。它只证明 P0，不自动代表 P1/P2/P3。

## 9. 达到闭环学会策略的持续路线

目标只由连续 GT 的 `Reach→Grasp→Lift` 定义。接口、离线 first-action、动作数量和 EE 有位移均不能替代该目标。

### L0：冻结可执行运行时

- 保留 active/pending、独立 callback groups、10 Hz、K=5、TTL 与 safety fail-closed；
- 每轮要求 100/100、K=5 完整率 100%、无 external hold transition、无动作限幅异常；
- L0 不通过时禁止评价模型和采集训练修复数据。

### L1：定位训练分布内失败起点

- 依次运行 P0/P1/P2/P3；
- 对每条轨迹记录 first failure onset：未对准、未下降、未闭爪、闭爪未接触或接触后未抬升；
- 若四个 train-ID 均失败，停止空间 OOD 归因，结论为当前 checkpoint 未形成可执行闭环策略。

### L2：policy-visited recovery 示教

- 让当前策略运行到 first failure onset，立即 Hold；
- 从策略实际访问到的状态接管，录制专家恢复到 Lift 的后半段轨迹；
- recovery 样本按 `Align / Descend / Close / Lift` 和失败类型分桶，避免再次由 Hover/Open 帧主导；
- 保持双相机、`state[15]`、action8、相同任务文本、`grasp_assist=false`；`object_pose` 只作 GT/采样信息，不进入 policy input；
- 原始成功示教与 recovery 示教共同进入 train-only mixed release，另留未参与阈值设计的 recovery validation/benchmark。

这一路线是 DAgger-like，但不声称已经实现自动 DAgger：当前计划是有界的人类/脚本接管恢复示教，先补齐策略部署时真实访问状态的标签。

### L3：一次受控微调

- 从当前双相机 B checkpoint 继续 LoRA，不重新下载基座；
- 冻结 `state15 + scene + wrist / action8 / chunk10 / K5` 合同；
- 训练前必须通过 immutable release、split、phase balance、checkpoint dependency audit；
- 只批准一次正式微调；以 held-out recovery 行为指标和 checkpoint audit 选 checkpoint，不以 train loss 单独选模。

### L4：闭环验收与视频

- 先无视频运行 P0/P1/P2/P3；至少出现真实 Lift 后，在同一位置做独立确认运行；
- 只有确认运行保持 Reach/Grasp/Lift 才录 scene+wrist 成功视频；
- train-ID 成功后才运行 seed42 spatial-OOD，避免把“根本没学会”误写成“泛化不足”；
- 若微调后仍在相同 failure onset 失败，停止追加 epoch，回到 L2 增加对应 failure bucket，而不是放宽 TTL、改标定或堆 GPU。

### 9.1 L1 执行结果与停止线（2026-08-21）

用户批准的 P1/P2/P3 已在与 P0 相同的无视频、MuJoCo、双相机、10 Hz/K=5 合同下完成；未进入 Isaac、未重训、未运行 seed42。每个 case 都完成了 100 条命令和 20 个完整 K=5 chunk，因此这不是由动作预算不足或 chunk 截断造成的早期行为缺失。

| case | XY | policy elapsed | completed | K=5 complete | gripper min | queue hold | GT / 判定 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| P0 | `(0.36,-0.10)` | 20.44 s | 100/100 | 20/20 | 0.9392 | 1 | Reach/Grasp/Lift false; `D_NO_MEANINGFUL_APPROACH` |
| P1 | `(0.40,0.10)` | 22.02 s | 100/100 | 20/20 | 0.9059 | 0 | Reach/Grasp/Lift false; `D_NO_MEANINGFUL_APPROACH` |
| P2 | `(0.44,-0.06)` | 19.97 s | 100/100 | 20/20 | 0.9586 | 0 | Reach/Grasp/Lift false; `D_NO_MEANINGFUL_APPROACH` |
| P3 | `(0.38,0.06)` | 20.71 s | 100/100 | 20/20 | 0.9177 | 1 | Reach/Grasp/Lift false; `D_NO_MEANINGFUL_APPROACH` |

对应证据目录为 `evidence/smolvla_dualcam_timergroup_{P0,P1,P2,P3}_20260821/`。P0--P3 均是训练位点，且都未出现有意义接近或闭爪；因此结论是 `NOT_LEARNED_CLOSED_LOOP`：当前双相机 B checkpoint 没有形成可执行抓取策略。这个结论只针对该 checkpoint、冻结合同和这四个 MuJoCo 训练位点；它不等价于标定问题、空间泛化问题、Isaac 结论、真机结论或成功率估计。

**停止线：**不再执行 seed42 spatial-OOD。空间 OOD 只在至少一个 train-ID 位置出现可复现 Reach/Grasp 后才有归因价值。下一 Gate 是 L2 的 policy-visited recovery 数据采集合同与本地验收；不生成 release、不启动训练、不产生 GPU 计费，直到 recovery release 通过并另获确认。

### 9.2 L2 本地采集与验收实现

已增加 `training/scripts/validate_policy_visited_recovery_capture.py` 和模板 `configs/smolvla_s3/policy_visited_recovery_capture.template.json`。它不启动仿真、不自动接管、更不生成 release；职责是把人工填写的 policy-failure handoff 与上游真实 episode sidecar 绑定并 fail-closed 验收。

每条候选 recovery episode 必须同时满足：

- 有一个已有的 P0--P3 policy evidence 目录、failure type 与明确的 failure-onset action index；
- `simulator_backend=mujoco`、双相机 `scene+wrist`、10 Hz、`state[15]`、原任务文本和 `grasp_assist_enabled=false`；
- 上游 `upstream_gate=teleop`，`action_fill=teleop_command`，`command_missing=false`，不接收 policy Hold 填充动作；
- 上游连续任务 GT 的 `task_phases` 含 `LIFT`，且 episode 已成功提交；
- 每条样本声明其覆盖的 `ALIGN/DESCEND/CLOSE/LIFT` bucket。未覆盖的 bucket 只报 warning，不能被误写成已平衡。

采集时应先让 policy 在已知失败位点运行，再停止 policy publisher；由操作者用独占的 teleop publisher 从当时机器人状态接管并录制至 Lift。当前上游没有已实现的自动 policy-to-teleop 交接器，因此这一步必须人工确认发布者所有权，不能让两个 publisher 并行写 `/teleop/cmd_pose`。完成后以如下命令生成验收报告；Pass 的 `next_gate` 仍是 `release_not_authorized`：

```bash
python3 training/scripts/validate_policy_visited_recovery_capture.py \
  --capture-manifest <filled-capture.json> \
  --output-report <capture-report.json>
```
