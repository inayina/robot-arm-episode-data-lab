# SmolVLA S3 Recovery 实施方案

**状态**：Phase 0 本地入口已实现（train-only split、state[15]、官方精确 PEFT 正则、chunk10/K5 与双评测模式）；Phase 1 wrist smoke 已完成并 **Hold**，v3 相机冻结为 **scene-only**；Phase 2 scene-only 50 条采集与 immutable v3 release 已获人工批准；GPU 视觉开销 probe、正式训练、AutoDL 计费与 Isaac 仍未授权  
**日期**：2026-07-23  
**范围**：Panda absolute-EEF + gripper、RGB、SmolVLA 后训练与离线/有界闭环评测  
**前置事实**：v1/v2 checkpoint audit 均 Pass，但 canonical 全帧 open-loop 均为 Hold；v2 late-close 未改善 timing / smoothness / saturation。

**Phase 0 落地入口（本轮）**：
- `training/scripts/prepare_smolvla_s3_merged_v30.py`：`--splits-json` / `--include-split` / `--validate-train-root` / `--state-contract recovery15`
- `scripts/materialize_smolvla_s3_train_root.sh`：train-only 根物化
- `training/scripts/audit_smolvla_s3_policy_inputs.py`：policy 输入 / PEFT / 相机 CPU profiler
- `configs/smolvla_s3/recovery_decisions.yaml`：**冻结** state[15] + 精确 PEFT 正则 + scene-only 相机决策
- `configs/smolvla_s3/lora_train_recovery_draft.yaml`：draft only，禁止直接训练
- `training/smolvla_s3/state15.py`：state[15] compose helper；train-only 物化与 native open-loop 已接入（尚未建 v3 release）
- `training/scripts/run_smolvla_s3_open_loop.py`：`canonical_first_action` 与 `queued_diagnostic` 分流；后者不得获得 canonical Pass
- 上游：`scripts/run_smolvla_s3_phase1_wrist_smoke.sh`（Phase1 已完成，禁止继续扩采）
- 中游审计：`training/scripts/audit_smolvla_s3_phase1_wrist_smoke.py`（含红目标可见性门禁）
- 测试：`tests/test_smolvla_s3_train_split_materialization.py`、`tests/test_smolvla_s3_policy_input_audit.py`、`tests/test_smolvla_s3_recovery_decisions.py`

---

## 0. 直接结论

下一轮不能从“再加一些 late-close 数据、再跑 1000 steps”开始。以下三个阻断项的本地入口已于 2026-07-23 修复，并由 SmolVLA 回归测试覆盖；GPU 侧仍需无训练 probe：

1. **训练 split 泄漏**：release 为 12 train / 4 validation / 4 benchmark，但 AutoDL 合并根含 20 episodes，训练日志也显示 `dataset.num_episodes=20`；当前入口未按 release split 过滤。
2. **Panda 输入契约未钉死**：源数据 `observation.state[7]`，最终 checkpoint metadata 却声明 `observation.state[6]`；`ee_pose`、`object_pose`、`ft`、`gripper` 虽被 evaluator 放进 batch，但 checkpoint preprocessor 未声明这些字段。必须确认模型实际收到的 key / shape / mask，不能继续靠猜。
3. **PEFT 适配面过窄**：当前只审计到 `q_proj/v_proj`。官方 LeRobot PEFT 路线还强调任务相关 state/action projection；Panda 是新的 embodiment + absolute-EEF action，不能默认只改注意力投影就足够。

只有 Phase 0 全部 Pass，才允许考虑一套参考官方规模、严格隔离 split 的新实验。该实验不是 v2 的自动重试；需要新的人工批准与 GPU 预算。

---

## 1. 外部成功方法与本项目差距

### 1.1 官方一手参考

- [SmolVLA 官方文档](https://huggingface.co/docs/lerobot/smolvla)：
  - 建议单任务约 **50 episodes** 起步；
  - 示例为 5 个方块位置 × 每位置 10 episodes；
  - 文档明确说明类似任务 25 episodes 表现不好；
  - fine-tune 示例为 batch 64 / 20k steps。
- [LeRobot PEFT 文档](https://huggingface.co/docs/lerobot/peft_training)：
  - SmolVLA LoRA 示例使用 `r=64, alpha=64`；
  - 官方示例训练预算远大于 1k steps；
  - state/action projection 被视为 task-dependent 适配点。
- [SmolVLA 论文](https://arxiv.org/abs/2506.01844)：
  - base 预训练约 22.9K episodes / 10.6M frames；
  - chunk size 10–50 是较合理区间；
  - 执行 1 或 10 个动作后重新观测，明显优于执行完整 50-step chunk；
  - 异步推理解耦感知/预测与动作执行。

### 1.2 差距表

| 项 | 官方参考形态 | 当前 v2 | Recovery 目标 |
|---|---|---|---|
| 数据量 | 约 50 episodes 起步 | 20 episodes | 50 条、位置分层 |
| 变化覆盖 | 每个变化重复多次 | seed 变化，位置覆盖窄 | 5 个位置，每位置 10 |
| 训练覆盖 | 20k-step 量级示例 | 1k × batch4，约 0.52 epoch | 按有效 epoch 计算 |
| split | 训练与任务成功评测分开 | 20 条全进训练根 | train-only 物理根 |
| PEFT | q/v + task-dependent projections | q/v only | 构建探针后冻结显式 target set |
| state | embodiment-specific sensorimotor state | source[7] vs checkpoint[6] 未解释 | 明确 Panda state vector |
| chunk | 10–50；频繁重观测更好 | chunk50，评测每帧 reset | chunk10，执行 K=5 起步 |
| runtime | chunk / async | 无 Panda SmolVLA runtime wrapper | bounded async queue |
| 成功判定 | 多位置、多 trial 任务成功 | teacher-forced open-loop Hold | 离线 Pass 后才申请 Isaac |

---

## 2. 总体阶段与授权边界

```text
Phase 0 入口/契约修复（CPU + 小 GPU probe，不训练）
    ↓ Pass
Phase 1 相机与时序信息增益 smoke（2–4 ep，不训练）
    ↓ 人工确认
Phase 2 50-episode 新数据（新 release，绝不覆盖 v0/v1/v2）
    ↓ QA + 真 split Pass
Phase 3 一次正式 Recovery LoRA（按 epoch，checkpoint 选择）
    ↓ held-out canonical open-loop Pass
Phase 4 bounded queued-action simulation（另批）
    ↓ task-success gate
S4 Isaac 申请（仍需单独批准）
```

**当前授权**：Phase 0 契约冻结；Phase 1 已结束。原 4 条 wrist smoke
目标不可见；仅翻转视轴的 P0 重试仍未看到红目标，P1 按止损约定跳过；
v3 固定 `scene-only`。Phase 2 采集与 immutable v3 release 已单独获批；禁止继续
调 wrist、自动转正式训练或进入 Isaac。

---

## 3. Phase 0：先修入口与可观测性

### 3.1 P0-A：真正的 train-only LeRobot 根

**仓库**：中游 `robot-arm-episode-data-lab`

修改建议：

- 为 `training/scripts/prepare_smolvla_s3_merged_v30.py` 增加：
  - `--splits-json`
  - `--include-split train`
  - 对 episode ref 做精确选择与重新编号；
- 生成根的 `meta/info.json.total_episodes` 必须等于 release train 数；
- 训练入口写入：
  - release split SHA256；
  - 实际训练 episode ref；
  - 实际 `num_frames/num_episodes`；
- validator 交叉检查训练根与 `splits.json`，发现 validation/benchmark ref 立即 No-Go。

验收：

| Gate | Pass |
|---|---|
| v2 fixture train episodes | 12，而不是 20 |
| validation/benchmark 交集 | 0 |
| frame/episode 重新编号 | 连续且 LeRobotDataset 可加载 |
| manifest/release | 不修改 immutable v2 |

需要新增测试：`tests/test_smolvla_s3_train_split_materialization.py`。

### 3.2 P0-B：实际 policy 输入张量审计

新增只读工具：`training/scripts/audit_smolvla_s3_policy_inputs.py`。

对一批真实样本，在 `preprocess` 后、`policy.forward/select_action` 前记录：

- 输入 keys；
- 每个 tensor 的 shape / dtype / min / max；
- camera 数量、非零比例与视觉 mask；
- state 有效维度和 padding mask；
- action target 有效维度；
- language token 非空率；
- 是否存在 schema 中有字段但被 preprocessor 丢弃。

当前必须解释：

```text
source observation.state[7]
checkpoint config observation.state[6]
dataset extra: ee_pose/object_pose/ft/gripper
checkpoint preprocessor: 未声明这些 extra
```

Recovery 推荐的可部署 state 契约：

```text
observation.state[15] =
  joint_position[7]
  + ee_pose_xyzw[7]
  + measured_gripper[1]
```

- `ee_pose` 可由真实 Panda FK 获得；
- 不把仿真 GT `object_pose` 放进 policy state，避免破坏 Sim2Real-readiness；
- `ft` 先不纳入，除非真实端同步与标定完成；
- 模型内部仍 pad 到 `max_state_dim=32`。

state[15] 已由人工决定采用；train-only v3.0 物化和 native open-loop 已使用同一 compose helper。新 release、正式训练和运行时部署仍需分别过门禁。

### 3.3 P0-C：PEFT target 构建探针

当前配置：

```yaml
target_modules: [q_proj, v_proj]
```

新增无训练构建探针，输出所有：

- trainable parameter names；
- 每类参数数量；
- q/v LoRA；
- state projection；
- action input/output/time projection；
- vision encoder（必须冻结）；
- base VLM（必须冻结）。

Recovery 主配置不盲抄当前 LeRobot 文档的默认值，而是在钉死的 LeRobot 版本上冻结显式 resolved target set。目标是：

1. 保留 `q_proj/v_proj` LoRA；
2. 纳入 Panda task-dependent state/action projections（LoRA 或 explicit full-training modules，二选一并固定）；
3. vision encoder / base VLM 继续冻结；
4. checkpoint audit 必须检查所有 resolved targets，而不仅是 YAML 字符串。

Pass 条件：Panda state/action projections 确实可训练，且无非预期 base 参数解冻。

### 3.4 P0-D：相机与空视觉 token / latency 审计

当前 checkpoint metadata 同时出现：

- `camera1/camera2/camera3`
- `empty_camera_0/empty_camera_1`
- `empty_cameras=2`
- resize 到 `512×512`

以上是历史 v1/v2 checkpoint metadata，不得直接套到 Recovery。Recovery
policy schema 已显式缩为唯一视觉特征 `observation.images.camera1`，运行 batch
也提供该键。LeRobot 0.5.1 `SmolVLAPolicy.prepare_images` 只在“配置的视觉特征缺失”
时追加空图，因此 Recovery 的缺失数为 0；配置现已显式冻结
`empty_cameras=0`，预期追加空图数为 0。该结论由控制入口的
`_empty_camera_padding_contract` 与单测固定。

仍须以一次无训练 GPU full-forward probe 判定：

- 实际送入 VLM 的 image tensor 数；
- 每路视觉 token 数；
- 单路 scene 的 full-forward latency/VRAM；
- policy `select_action` 是否满足部署频率预算。

不得把“结构上没有空图补位”写成“GPU 延迟已经改善”；未跑 full-forward
probe 前没有实测加速结论。Phase 1 已冻结 scene-only，不再加第二相机。

### 3.5 Phase 0 总门禁

必须同时满足：

- train-only root 无泄漏；
- policy 输入维度与数据 schema 一致；
- state/action projections 按预期可训练；
- 视觉输入数量的配置/运行时契约一致，且 full-forward 开销另行实测；
- 相关测试全 Pass；
- 不使用 Isaac、不训练正式 checkpoint。

### 3.6 2026-07-23 本地入口验收

- train-only 物化支持 `--state-contract recovery15`，同步更新 parquet、`info.json`、`stats.json` 与 provenance；
- 正式训练入口从配置分别读取 `train.action_chunk_size=10` 与 `inference.action_steps=5`，不再强制 `K=chunk`；
- 正式训练入口显式覆盖 base checkpoint 的 policy schema 为 `state[15] + camera1(scene)` / `action[8]`，不再继承历史 base 的 `state[6] + camera1/2/3`；
- `inference.empty_cameras` 已显式冻结为 0；Recovery 只配置且提供
  `camera1`，按 LeRobot 0.5.1 missing-feature 语义预期追加空图为 0；
- Recovery 依赖门禁改为 AutoDL 已通过栈的精确版本审计（含
  `peft==0.19.1`），版本不一致会在 CUDA probe 前 fail closed；
- checkpoint 审计新增 policy + preprocessor 的 state dim、scene-only 非空相机集合、action dim、rename map、`n_action_steps`、`empty_cameras`、PEFT regex 与 `full_training_modules`；
- evaluator v2 明确区分 `canonical_first_action` 和 `queued_diagnostic`；queued 模式消费 policy queue，但强制 `temporal_metrics_gate_eligible=false`；
- evaluator v2 记录 latency mean / p50 / p95 / max；
- 本地 Recovery mock-preflight Pass；相关测试覆盖 empty-camera 与依赖版本门禁。
- AutoDL RTX 4090D 无训练 real preflight Pass：完整模型 live PEFT resolve、32 steps、74 个 trainable parameter names、无 OOM、adapter 保存成功；该 probe 未执行 policy forward 或推理延迟测量。

旧 preflight 发生在依赖/empty-camera 合同修订前，不能直接授权新配置训练；
新配置要求同一份 preflight report 含
`dependency_version_audit.passed=true`。这些属于“已实现”的本地契约与测试证据，
不等于 full-forward latency 已验证，也不等于正式 Recovery LoRA 已获批；它们
不改变已单独批准的 Phase 2 采集/release 范围。

---

## 4. Phase 1：第二相机信息增益 smoke（不训练）

**执行结果（2026-07-23）**：**Hold / scene-only**。原 4 条虽结构与同步
通过，但红目标在 wrist 最后 3 cm 视野中的可见率为 0；仅翻转相机视轴的
P0 单条重试仍为 0，画面转而看到停放的蓝圆柱/篮筐。P1 未执行。停止相机
调参，v3 采用 `smolvla_s3_panda_abs_eef_scene_v3_phaseaware50`。

**仓库**：上游 `ros2-arm-teleoperation-suite`

上游已有 `/camera/wrist/color/image_raw` 和 recorder 的
`observation.images.wrist`，但当前 Round-2 入口固定
`enable_wrist_camera:=false`。

只采 2–4 条 scene+wrist smoke，不做 release、不训练。检查：

1. 最后 3 cm 接近阶段，方块与指尖是否持续可见；
2. scene 近似相同的 hold 帧，wrist 是否提供明显几何差异；
3. 两路 RGB 与 state/action 的帧级同步；
4. wrist 遮挡率、运动模糊、目标出画率；
5. 增加相机后的 profiler latency 是否仍满足 queue runtime 预算。

决策：

- 信息增益 Pass → v3 使用 scene+wrist；
- 信息增益不足或延迟代价过大 → v3 保持 scene-only；
- 不允许为了“多模态看起来更先进”默认增加相机。

---

## 5. Phase 2：参考官方规模的数据方案

### 5.1 目标规模

总计 50 accepted episodes：

| 位置 | 数量 | 用途 |
|---|---:|---|
| P0–P3 | 每位置 9 train + 1 validation | 36 train + 4 ID validation |
| P4（held-out） | 10 | OOD-position benchmark |

总 split：

```text
train=36
validation=4
benchmark=10
```

每个位置必须有明确坐标/seed 记录，禁止只换随机 seed 却没有可审计的位置变化。

### 5.2 示范时序

不再采用 6–7 秒静态 hold 来“强迫晚关爪”。改为几何事件驱动：

```text
approach：gripper=open
xy_error <= 0.02 m 且 z_gap <= 0.03 m
stabilize：0.3–0.5 s
close：0.5–1.0 s 单调 ramp
grasp settle：0.5 s
lift
```

理由：

- 当前 `n_obs_steps=1` 下，长时间几乎静态的画面对应不同“距关爪时间”，形成观测别名；
- 3 秒长 ramp 产生大量中间 gripper 值，不利于稳定单次阶段转换；
- 几何触发比绝对等待秒数更容易跨位置复现。

QA 新增：

- expert binary transition count = 1；
- close onset 几何条件；
- reopen count = 0；
- gripper 全程 `[0,1]`；
- close ramp 5–10 source frames；
- action smoothness；
- scene/wrist 可见性（若启用 wrist）；
- 每位置 accepted 数；
- train/val/benchmark ref 零交集。

### 5.3 新 release

根据 Phase 1 相机决策，二选一：

```text
smolvla_s3_panda_abs_eef_scene_v3_phaseaware50
smolvla_s3_panda_abs_eef_scene_wrist_v3_phaseaware50
```

禁止覆盖 v0/v1/v2。release 必须记录：

- state[15] 字段定义；
- action absolute EEF[7] + gripper[1]；
- camera keys；
- position IDs；
- split policy；
- source hashes；
- physical validation；
- `grasp_assist_enabled=false`。

---

## 6. Phase 3：一次正式 Recovery LoRA

### 6.1 冻结配置方向

```yaml
base: lerobot/smolvla_base@exact_commit
precision: bf16
peft:
  method: LORA
  r: 64
  alpha: 64
  dropout: 0.05
  targets: <Phase 0 resolved q/v + state/action projections>
vision_encoder: frozen
base_vlm: frozen
chunk_size: 10
inference_action_steps_initial: 5
optimizer_lr: 1.0e-3
```

`chunk_size=10` 的依据：

- 官方论文中 10–50 为较合理区间；
- 当前任务 10 Hz，chunk50 覆盖 5 秒，跨越多个 FSM 阶段；
- chunk10 只覆盖 1 秒，更符合 approach/close 的局部条件；
- runtime 执行 K=5，可用约 0.5 秒窗口异步生成下一 chunk。

### 6.2 训练预算按 epoch，不按固定 1000 steps

设 train root 有 `N` frames，batch 为 `B`：

```text
steps_per_epoch = ceil(N / B)
initial_budget = 5 effective epochs
maximum_budget = 10 effective epochs
```

执行规则：

1. RTX 4090 preflight 只测试 batch 8/16 的 OOM 与吞吐，选择最大稳定 batch；这不是精度扫参。
2. 每个 effective epoch 保存 checkpoint。
3. validation 使用严格 held-out 4 episodes。
4. 连续 2 epoch validation compound score 不改善则停止。
5. 5 epoch 后只有在 EE/grip 不退化且 timing/smooth/sat 持续改善时，才允许同一 run 延长到 10 epoch。
6. 不以 train loss 最低作为 checkpoint 选择标准。

官方 20k-step 示例作为预算量级参考，不直接硬套；最终 steps 由 v3 train frames 和 batch 计算。

### 6.3 Checkpoint 选择

每个 epoch 的快速 validation 报告：

- EE RMSE；
- gripper balanced accuracy / closed F1；
- signed close offset；
- binary transition count；
- smoothness p90；
- raw gripper OOB；
- latency；
- train/validation gap。

只选择 compound gate 最优 checkpoint。禁止默认使用最后一步。

---

## 7. Phase 3.5：离线评测门禁

### 7.1 快速诊断

- validation 全 episode，允许 stride 5；
- 只用于 checkpoint 排序；
- `temporal_metrics_gate_eligible=false`；
- 不得据此进入 Isaac。

### 7.2 Canonical held-out

最终候选在 validation + benchmark 上：

```text
stride=1
max_frames=0
train episode overlap=0
```

保留现有门槛，并新增：

| 指标 | Pass |
|---|---:|
| EE RMSE | ≤0.10 m |
| gripper balanced accuracy | ≥0.70 |
| close timing error | ≤5 frames |
| smoothness p90 | ≤0.05 m |
| raw gripper OOB | ≤0.10 |
| predicted binary transitions | 每 episode ≤5 |
| full coverage | true |
| train/eval overlap | 0 |

评测优化：

- 固定 base 预测只算一次并缓存；
- checkpoint 只跑 LoRA 部分；
- 增加 episode 进度日志；
- 离线 batch inference 可作为实现优化，但必须证明与 batch1 数值等价。

### 7.3 2026-07-23 Recovery v3 结果与 gripper 审计

Recovery v3 已完成 5,705-step formal LoRA 与 14 条 / 3,413 帧
canonical first-action open-loop。checkpoint config audit Pass；canonical
在 `eval_gate_v1` 下仍为 **Hold**，唯一 Pass failure 是
`raw_gripper_oob_ratio=0.336068`（`sat`）。其余关键指标为：

- EE RMSE `0.037900 m`；
- gripper balanced accuracy `0.993587`；
- close timing error `2.142857 frames`；
- smoothness p90 `0.026814 m`；
- full episode coverage `true`。

K5 queued diagnostic 也为 Hold；它消费 action queue，但
`temporal_metrics_gate_eligible=false`，不得作为 canonical Pass。

本地 CPU saved-prediction audit 进一步确认：

- checkpoint/release 的 action `MEAN_STD` mean/std 一致；
- postprocessor 只反归一化、不 clamp；
- `_map_native8` 执行映射对 gripper clamp `[0,1]`；
- canonical 仅 `0.7032%` 帧超出边界超过 `0.05`，clip MAE
  `0.004358`；
- clip 不改变开/关分类或 3-frame debounce 关爪时序。

据此形成的 `eval_gate_v2` 已获用户批准并冻结为
`configs/smolvla_s3/eval_gate_v2.yaml`，threshold lock 为
`configs/smolvla_s3/eval_gate_v2.lock.json`。evaluator v3 已实现：

- 计算 exact OOB、epsilon OOB、clip MAE/max、raw range；
- 强制 mapped command 范围及 `mapped==clip(raw)`；
- 强制 clip 前后分类与关爪时序不变；
- Pass 前校验 gate/splits SHA、精确 eval refs、零 train/design overlap、
  canonical 全帧采样和 run-specific 人工授权 manifest；
- canonical v2 缺失/无效 manifest 时在 policy inference 前 fail closed；
- saved historical report 明确不可 prospective Pass。

Recovery v3 历史报告用冻结 v2 复核仍为 Hold，唯一失败项为
`prospective_eligibility`，因此 v1 Hold 未被追溯改判。新的独立 held-out
canonical prospective evaluation 尚未执行，也未授权 Isaac。详见
`docs/SMOLVLA_S3_GRIPPER_RANGE_CLIP_AUDIT.md`。

---

## 8. Phase 4：有界 action-queue runtime（另批）

只有 canonical open-loop Pass 后才能执行。

初始 runtime：

```text
control_rate = 10 Hz
chunk_size = 10
execute K = 5
async double buffer = on
replan_period = 0.5 s
safety clamp / E-stop = on
```

过程：

1. 推理线程生成 10-action chunk；
2. 控制线程以 10 Hz 执行前 5 个动作；
3. 执行期间异步生成下一 chunk；
4. 新 chunk 到达后丢弃旧 chunk 剩余动作；
5. 超时、NaN、OOB 或风险门禁触发 Hold/E-stop。

必须分别报告：

- policy inference latency；
- command publish jitter；
- queue underrun；
- dropped stale actions；
- close timing；
- bounded task success。

先在下游/仿真有界 1–5 seeds 验证；未获批准不得进入 Isaac S4。

---

## 9. 三仓职责

| 工作 | 仓库 |
|---|---|
| scene/wrist 采集、几何事件示范、上游 validation | `ros2-arm-teleoperation-suite` |
| split 物化、feature/PEFT audit、release、训练、open-loop | `robot-arm-episode-data-lab` |
| action queue loader、风险门禁、有界 replay/执行 | `ros2-moveit-pybullet-bridge` |

禁止把 training split、action schema 转换或 LoRA 逻辑复制到下游；禁止把运行时风险职责塞回中游 evaluator。

---

## 10. 资源与止损

### 10.1 建议预算

| 项 | 数量 |
|---|---:|
| Phase 0 GPU probe | 1 次，≤30 min |
| camera smoke | 2–4 episodes，不训练 |
| formal data | 50 accepted |
| formal train | 1 run，5 epoch 起步，最多同 run 10 epoch |
| canonical full eval | 1 个最终 checkpoint |
| Isaac | 默认 0；Pass 后另批 |

### 10.2 硬停止

- Phase 0 任一契约未解释；
- train/eval episode overlap 非零；
- state/action projection 未按预期训练；
- 50 条数据 QA 未过；
- validation transition count 仍为几十/上百；
- 5 epoch 后 timing/smooth/sat 无方向性改善；
- canonical gate 非 Pass；
- 试图用更多数据或更多 steps 掩盖 schema/输入错误。

停止后保留诊断产物，不再开启第四轮“再试一次”。

---

## 11. 实施顺序

推荐按以下独立变更交付：

1. **PR/变更 A**：train split materialization + tests。
2. **PR/变更 B**：policy input/PEFT/camera profiler + golden report。
3. **人工审计点**：确认 state[15]、camera variant、resolved PEFT targets。
4. **PR/变更 C**：v3 release schema、QA 和采集配置；不采数据。
5. **人工批准点**：批准 50 条采集。
6. **数据产物**：50 accepted + immutable v3 release。
7. **人工批准点**：批准一次 Recovery LoRA。
8. **训练/评测产物**：epoch checkpoints + held-out canonical report。
9. **只有 Pass**：申请 action-queue bounded runtime / Isaac。

这一路线把“别人成功时拥有的数据规模与训练预算”引入本项目，同时优先修复本项目独有的 split、state/action 适配和时序问题；不是简单照抄 20k steps。
