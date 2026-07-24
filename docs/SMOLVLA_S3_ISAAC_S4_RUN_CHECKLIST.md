# SmolVLA S3 Recovery — Isaac S4 有界 runtime 运行清单

**状态（2026-07-24）**：人工已批准有界 S4（作品集口径）；**本机 RTX PRO 500（~6GB）已实际跑完 seeds 1–5**。  
**前置**：`eval_gate_v3` prospective canonical **Pass**  
（`runs/smolvla_s3/openloop_recovery_v3_prospective_eval10_gate_v3_20260724T065300Z`）  
**明确**：open-loop Pass ≠ 任务成功；本轮 Isaac **`ran_isaac=true`**，lift **0/5** → **Hold**（不扩种子、不声称 Sim2Real）。

## 1. 已具备的资产

| 项 | 路径 / 事实 |
|---|---|
| Recovery LoRA | `runs/smolvla_s3/recovery_v3_lora_20260723T125632Z/lerobot_run/checkpoints/005705/pretrained_model` |
| Gate | `configs/smolvla_s3/eval_gate_v3.yaml`（执行语义；开爪边 diagnostic） |
| Prospective Pass | EE `0.0253 m`、grip BA `0.9943`、close-edge beyond-ε `0.386%`、clip MAE `0.00692`、分类/时序变化 `0` |
| E3.5 Isaac harness | scripted oracle v2b lift 5/5：`evidence/e3p5_isaac_scripted_oracle_5x_lift_v2b_20260720` |
| abs-EEF 执行夹紧 | 上游 `policy_control.bound_absolute_eef_gripper` + 中游 `training/smolvla_s3/runtime_s4.py` |
| Online S4 runner | 上游 `scripts/run_isaac_smolvla_s4.sh` + `isaac_sim_adapter.smolvla_policy_inference_node`；中游薄封装 `scripts/run_smolvla_s4_bounded_isaac.sh` |
| Runtime 合同 | Recovery §8；**P2 单源**：`configs/smolvla_s3/s4_runtime_contract.{yaml,json}`（中游权威）+ 上游包内字节相同副本；CPU 契约测试 `tests/test_smolvla_s3_runtime_s4.py` / 上游 `tests/test_scene_smolvla_runtime_helpers.py` |

## 2. 批准的有界 runtime（首批）

```text
control_rate        = 10 Hz
chunk_size          = 10
execute_K           = 5
async_double_buffer = on
replan_period       = 0.5 s
gripper_command     = clip(raw, 0, 1)   # 与 gate v3 执行语义一致
safety              = clamp + E-stop / Hold on NaN|timeout|risk
cameras             = scene-only
state               = observation.state[15]
seeds               = 1–5（有界；禁止一上来 20-seed）
success_metric      = bounded lift task success（连续 GT；沿用 E3.5 v2b）
```

## 3. 勾选项（2026-07-24 用户批准）

- [x] 批准在 Isaac（或现有 E3.5 仿真栈）跑 **最多 5 seeds** 有界 rollout
- [x] 批准范围：**作品集就绪**（不扩种子、不上真机、不声称 Sim2Real）
- [x] 成功判据：lift 高度 / place 容差沿用 E3.5 v2b
- [x] 失败即停：任一种子 E-stop 过多或 success=0/5 时默认 Hold，不自动扩种子
- [x] 明确 **不** 声称 Sim2Real / 真机部署

## 4. 首批有界结果（诚实）

| 项 | 结果 |
|---|---|
| Evidence | `evidence/smolvla_s4_bounded5_20260724T203700Z/` |
| Gate | `s4_gate.json`：`ran_isaac=true`，`gate_pass=false` |
| Policy interface | 5/5 PASS（各 150 actions；latency p50 ≈ 9–11 ms after warmup） |
| Continuous GT | reach **3/5**，grasp **1/5**，lift **0/5**，outcome_success **0/5** |
| Host | local RTX PRO 500 Blackwell laptop GPU ~6GB；`RECORD_SCENE_VIDEO=false`；local Franka USD |
| Interpretation | **Hold** — online path wired and executed；not task success |

```bash
export ISAAC_FRANKA_USD=$HOME/isaac_assets/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd
export ISAAC_REQUIRE_LOCAL_FRANKA=1
export RECORD_SCENE_VIDEO=false
export SEEDS="1 2 3 4 5"
./scripts/run_smolvla_s4_bounded_isaac.sh
# or upstream:
# bash /home/ina/dev/ros2-arm-teleoperation-suite/scripts/run_isaac_smolvla_s4.sh
```

**本地资产 / 离线模式（上游）**：地面为本地 `FixedCuboid`。Franka 需：

```bash
export ISAAC_FRANKA_USD=$HOME/isaac_assets/Isaac/Robots/FrankaRobotics/FrankaPanda/franka.usd
export ISAAC_REQUIRE_LOCAL_FRANKA=1
```

## 5. 明确不做（除非另批）

- 不因本轮 lift 0/5 自动扩种子 / 重训 / 进真机
- 不改回 eval_gate_v2 追溯改判
- 不把 interface Pass 或 reach 写成任务成功 / Sim2Real
- 不上真机
