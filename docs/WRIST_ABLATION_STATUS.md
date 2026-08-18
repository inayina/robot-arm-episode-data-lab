# Wrist Ablation Status — `smolvla_wrist_ablation_v1`

Date: 2026-08-18  
Scope executed: Stage 0 + Stage A + Stage B + matched 50-ep collection + **immutable parent release**  
Not executed: A/B LoRA, open-loop A/B, Isaac  
Historical Recovery v3 remains immutable.

Visual variable is fail-closed:

| Arm | Policy input | `number_of_policy_cameras` |
|---|---|---|
| A_scene_only | `state[15]` + scene RGB | 1 |
| B_scene_wrist | `state[15]` + scene RGB + `H_knuckle_z05` wrist RGB | 2 |

Forbidden as policy input: tactile / GelSight / fingertip / gripper camera / depth / segmentation / `camera3` / any third `observation.images.*`. Gripper/fingers *inside* wrist RGB are expected eye-in-hand content, not a third camera.

---

## 历史 scene-only 为什么成立

**已实现（工程决策，不是“wrist 无价值”的证明）。**

2026-07-23 Phase-1 wrist smoke 在当时的腕部安装下：

- 原始 4 条：最后 3 cm 看不到红块 → Hold
- 仅翻转视轴的 P0 重试仍看不到红块 → Hold
- 于是停止 camera tuning，Recovery v3 冻结为 `scene_only`

证据：

- 中游 `configs/smolvla_s3/recovery_decisions.yaml` → `phase1_wrist_smoke`
- `runs/smolvla_s3/phase1_wrist_smoke_20260723/wrist_smoke_reaudit_target_visibility.json`
- `runs/smolvla_s3/phase1_wrist_flip_smoke1_20260723/p0_audit.json`

当时的安装后来被证伪为 **inside-palm `B_look_fingers`**（RGB 灰盘，红像素 0/4）。那次 Hold 不允许直接继承到现在。

---

## 为什么现在需要重新打开

2026-08-14 腕部相机已 remount 为 **`H_knuckle_z05`**（`pos="0 0 0.05"` look +Z_hand）。静态验收：

- GT projection 4/4
- actual RGB red pixels 4/4
- `T_hand_camera` stable
- renderer / TF consistency
- portfolio wrist default on

那只是 **idle / static RGB**，不是动态 approach/close/lift smoke，也不是训练授权。本轮重新做动态 Phase-1。

HEAD XML（已确认）：

```xml
<camera name="wrist_camera" pos="0.0 0.0 0.05" xyaxes="1 0 0 0 -1 0" fovy="70.0" />
```

无 `B_look_fingers` / orientation-flip override。`camera_bridge` 与 `mujoco_sim` 加载同一 `config/models/franka_panda.xml`；Phase-1 YAML 把 scene/wrist pose noise 都置零；`enable_tactile=false`；`publish_depth=false`。

---

## Current wrist smoke：PASS

| 项 | 结果 |
|---|---|
| Gate | **`phase1_wrist_smoke_pass`** |
| Accepted episodes | **4 / 4**（P0 seed58 `0.38,-0.10` ×2；P1 seed59 `0.42,0.10` ×2） |
| Cameras | scene + wrist only，320×240 @ 10 Hz |
| `grasp_assist` | false |
| Action | `teleop_command`（batch expert）；**无** `hold_from_ee` |
| Trajectory | 动态：EE travel ≈ 0.39–0.40 m，gripper range = 1.0 |
| Sync | scene == wrist == parquet（291–324 帧） |
| Geometry | `H_knuckle_z05` PASS；非 `B_look_fingers` |
| Third camera | none；`unexpected_visual_keys: []` |
| Idle Aug-14 portfolio | **未使用** |

产物：

- 上游 `data/e2_red_500hz_seed58_wrist_ablation_v1_p1_20260818`
- 上游 `data/e2_red_500hz_seed59_wrist_ablation_v1_p1_20260818`
- 中游 `runs/smolvla_s3/phase1_wrist_ablation_v1_p1_20260818/wrist_smoke_audit.json`
- 中游 `runs/smolvla_wrist_ablation_v1/phase1_wrist_ablation_v1_p1_20260818/`

---

## Wrist vs scene：最后 5 cm / 3 cm visibility

HSV 红像素 proxy（不是 semantic segmentation）。4 条全部 wrist last-3cm **visible fraction = 1.0**。

| Window | Wrist red pixel ratio | Scene red pixel ratio | Wrist visible fraction |
|---|---|---|---|
| Approach（远场抽样） | ≈ 0.0042 | ≈ 0.0019 | 1.0 |
| Last 5 cm | ≈ 0.540 | ≈ 0.00151 | 1.0 |
| Last 3 cm | ≈ 0.545 | ≈ 0.00150 | 1.0 |
| Close window | ≈ 0.607 | ≈ 0.00138 | 1.0 |

读法：

- 近场 wrist 红像素约占画面 **54–61%**；同帧 scene 只有 **~0.15%**。
- Wrist 不是 scene 的拷贝（identical pixels 0 / last-3cm frames）。
- Occlusion proxy（lower-third 灰像素，非分割）last-3cm = **0.0**。
- Wrist 非 near-black（brightness ≈ 55–58）。
- Last-3cm 窗口很大（~180–195 / ~300 帧），因为 scripted expert 在 grasp volume 里 close/hold/lift 停留很久。这不否定近场对比：close window 同样是 wrist ≫ scene。

这支持假设的 **observability** 前提：当前 `H_knuckle_z05` 在接近后提供比 scene 强得多的红块像素。这 **不等于** 已证明闭环 grasp/lift 会改善。

---

## Dual-camera input contract：可行

LeRobot 0.5.x SmolVLA **可以合法消费两路 image features**。本实验合同：

| 层 | A | B |
|---|---|---|
| Dataset keys | `observation.images.scene` | `scene` + `wrist` |
| Policy keys | `observation.images.camera1` | `camera1` + `camera2` |
| Rename | scene→camera1 | scene→camera1，wrist→camera2 |
| `empty_cameras` | 0 | 0 |
| `camera3` / tactile | **FAIL** | **FAIL** |

Stage B no-train preflight：**PASS**（`dual_camera_preflight_pass`）

- draccus merge 会留下 base `camera3`；**replace** 合同会剥掉，B 恰好 camera1+camera2
- `empty_cameras=0` 时缺 wrist **不会**静默补空图
- 两张合成图像素不同；`prepare_images` 得到 2 张、无 empty mask
- 把 wrist 换成 scene 拷贝时两路张量相同；真正不同的 wrist 时两路张量不同
- 触觉 key 被 allowlist 拒绝
- Live `prepare_images`：CPU **PASS**，CUDA **PASS**
- 未跑 formal LoRA，未跑 Isaac
- 本地 editable LeRobot 是 **0.5.2**；历史 v3 训练钉的是 **0.5.1**。正式 A/B train 仍必须走 pinned Recovery stack，不能用这次 live-forward 环境顶替

产物：

- `runs/smolvla_wrist_ablation_v1/preflight_lerobot/preflight_report.json`
- `runs/smolvla_wrist_ablation_v1/preflight_lerobot/policy_visual_input_audit.json`
- `runs/smolvla_wrist_ablation_v1/phase1_wrist_ablation_v1_p1_20260818/policy_visual_input_audit.json`

v3 Isaac runtime `SceneSmolVLARuntime` 仍只吃 scene。B 的匹配 runtime **还没接**；那是后续 closed-loop 的授权项，不是现在可以偷偷拿 v3 checkpoint 多塞 wrist。

---

## Matched 50-ep collection + parent release

授权项已执行：50 accepted dual-camera episodes，再按 10 Hz 量化把 `close_ramp_frames_min` 从 5 调到 **4**（只改 wrist-ablation YAML，**未改**历史 `v3_phaseaware50.yaml`），然后建 **一个** immutable parent release。未重采。未训练。未进 Isaac。

| 项 | 结果 |
|---|---|
| Lift gate | 50/50 accepted；`grasp_assist=false` |
| Cameras | 仅 `observation.images.scene` + `observation.images.wrist` |
| Third camera / tactile / depth | **none** |
| Visual QA | **`phase1_wrist_smoke_pass`**（50/50） |
| Last-3cm wrist red ratio | mean **0.549**（min 0.545 / max 0.553）；visible fraction **1.0** |
| Last-3cm scene red ratio | mean **0.0016** |
| Scene vs wrist identical pixels | **0 / 4920** |
| Geometry | `H_knuckle_z05` PASS |
| Phaseaware QA | **`phaseaware50_pass`**（50/50，min=4） |
| Parent release | **built** / validate **go** |
| Train / Isaac | **未跑** |

`close_ramp_frames` 直方图仍是 `{4:15, 5:32, 6:2, 7:1}`。min=4 只接受 10 Hz 上 0.4 s 的量化边；不等于 close 时序已经更好。历史 v3 `20260723b` 同口径仍有 5/50 条是 4 帧（其 YAML 仍是 min=5）。

Release：

- id: `smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50`
- 路径: `data/releases/smolvla_wrist_ablation_v1_panda_abs_eef_scene_wrist_phaseaware50`
- 50 episodes / 12,005 frames / split 36/4/10
- `cameras: [scene, wrist]`，`visual_allowlist_variant: B_scene_wrist`，`number_of_policy_cameras: 2`
- `compose_state15: true`，wrist hash 50/50，`wrist_rgb_complete_rate: 1.0`
- `trained: false`，`ran_isaac: false`，`claims_task_success: false`
- `release_content_sha256`: `258cfd7cb4a90c5caed15e717a83e6be435a716ac0a4f2d78acf084d03af5221`

上游树未改。历史 v3 release 未覆盖。

---

## AutoDL / Seetacloud env（2026-08-18）

目标：先在当前实例装 Recovery-qualified 栈（CPU-only），租 ≥16 GB GPU 后再做 VRAM 门禁与 B REAL preflight。本次 **未** 正式 LoRA、**未** 跑 Isaac、**未** 下 LingBot 6B、**未** 下 `smolvla_base`、**未** 拷 50-ep 数据集。

| 项 | 结果 |
|---|---|
| Host | `root@connect.nmb2.seetacloud.com:46922`（Seetacloud nmb2） |
| SSH BatchMode | **Pass** (`/home/ina/.ssh/autodl_s3`) |
| GPU / VRAM | **not attached** (`/dev/nvidia*` missing; `nvidia-smi` 0-byte stub; `cuda_available=false`) |
| Train No-Go gate | VRAM **not yet evaluable**; runbook No-Go if VRAM &lt;15 GB after GPU attach |
| Env path | `/root/autodl-tmp/conda/envs/smolvla_s3` (`conda activate smolvla_s3`) |
| python / lerobot / torch / peft | **3.12.13 / 0.5.1 / 2.6.0+cu124 / 0.19.1** (qualified match) |
| torchvision / transformers / accelerate / safetensors | **0.21.0+cu124 / 4.57.6 / 1.14.0 / 0.8.0** |
| `smolvla_base` | **not downloaded** |
| `authorized_to_train` | still **false** until REAL preflight Pass |
| Formal train / Isaac | **not started** |
| Versions file | `/root/autodl-tmp/smolvla_s3/env_versions.json` |

Notes:

- Aliyun `lerobot==0.5.1` metadata currently wants `torch>=2.7`; Recovery pin is `torch==2.6.0+cu124`. Installed with `--no-deps` then remaining extras. Do **not** pip-upgrade torch to satisfy Aliyun metadata.
- `environment.lock.txt` `datasets` range corrected to `>=4.0,<5.0` (lerobot 0.5.1 rejects datasets 5).
- Keep this instance's `autodl-tmp` when changing GPU SKU. A brand-new machine will need a reinstall.

Ready vs not:

- **Ready:** SSH, conda env, Recovery-qualified package pins, SmolVLAPolicy/PEFT import.
- **Not ready:** GPU ≥16 GB, `nvidia-smi` VRAM gate, `smolvla_base` 40-hex pin, dual-camera REAL preflight, formal B LoRA.
- Unblock next: rent/attach a ≥16 GB GPU on **this** instance, then `nvidia-smi`. Do **not** set `SMOLVLA_S3_EXECUTE_TRAIN=1` until REAL preflight Pass.

This is **not** task success and does **not** authorize train.

---

## 下一步需要你明确授权什么

当前 **STOP**：不自动 A/B 训练，不进 Isaac。

2. **A/B formal LoRA**（必须另批）：同一 parent release / split / PEFT / seed / epochs；A 忽略 wrist，B 用 camera1+camera2。先在 pinned LeRobot 0.5.1 上再跑 dual-camera no-train preflight。
3. **Open-loop A/B**（必须另批）
4. **Bounded Isaac A/B ≤5 seeds**（必须另批；B 需要双相机 runtime，禁止把 wrist 塞进 A 的 checkpoint）

