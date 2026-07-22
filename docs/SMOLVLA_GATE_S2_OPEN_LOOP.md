# SmolVLA Gate S2：Panda absolute-EEF open-loop

**日期**：2026-07-21T17:19:08Z  
**Interface**：`pass`  
**H-3 pretrained vs absolute EEF**：`no_go`  
**H-4 upstream v2.1 loader**：`pass`  
**约束**：未训练；未跑 Isaac；`claims_task_success=false`。

## 结论

| 门禁 | 结果 | 含义 |
|---|---|---|
| S2 接口（Panda RGB + abs EEF 专家 + 推理） | **pass** | 可离线跑通 open-loop 管线 |
| H-4 上游 LeRobot v2.1 加载 | **pass** | parquet + scene mp4（OpenCV，无 `av`）可读 |
| H-3 预训练先验 ≈ Panda `absolute_eef_gripper_v0` | **no_go** | EE RMSE ≈ **0.27 m**，gripper accuracy **0.0** |

映射假设（**仅诊断**）：`libero6d_pred012_as_xyz_pred5_as_gripper_quat_unmapped`  
— SmolVLA-base 输出 **6-D（libero）**，**不是** Panda absolute EEF[8]；quat 在此假设下 **未映射**。

| 指标 | 值 |
|---|---|
| EE xyz RMSE | 0.273 m |
| Gripper accuracy | 0.0 |
| Quat angular error | null |
| Latency mean | ~241 ms |
| Infer peak VRAM | 926 MiB |

**不宣称**：任务成功、Sim2Real、可直接控臂。  
**禁止**：把 6-D 输出当 `ee_delta_gripper[7]`；与 ACT delta 指标同表混比。

## 复现

```bash
source ~/miniforge3/etc/profile.d/conda.sh && conda activate lerobot
cd ~/robot-sim-lab/robot-arm-episode-data-lab
python training/scripts/run_smolvla_gate_s2_open_loop.py --max-frames 8 --stride 20
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q tests/test_smolvla_gate_s2.py
```

## 证据

- [`evaluation/examples/smolvla_gate_s2_report.json`](../evaluation/examples/smolvla_gate_s2_report.json)
- [`evaluation/examples/smolvla_gate_s2_open_loop_report.json`](../evaluation/examples/smolvla_gate_s2_open_loop_report.json)
- [`configs/robot_schemas/smolvla_panda_s2.yaml`](../configs/robot_schemas/smolvla_panda_s2.yaml)
- Episode：上游 `e2_red_500hz_seed52_closelift5_20260720` ep0 frames `[0,20,…,140]`
- 测试：`tests/test_smolvla_gate_s2.py`

## 下一步（未批准不执行正式训练）

- **S3 Ready**：本地已冻结 — 见 [`SMOLVLA_GATE_S3_READY.md`](SMOLVLA_GATE_S3_READY.md) 与 [`SMOLVLA_S3_AUTODL_RUNBOOK.md`](SMOLVLA_S3_AUTODL_RUNBOOK.md)
- **S3 LoRA 执行**：需 ≥16GB / 人工批准；本机 6GB 仍 **No-Go**
- **S4 Isaac**：须 S3 open-loop **Pass** 后另批；禁止因 S2 接口 Pass 或 S3 Ready 直接进 Isaac
